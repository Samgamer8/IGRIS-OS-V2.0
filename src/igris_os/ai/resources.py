"""Medicion y estimaciones conservadoras para seleccionar modelos locales."""
from __future__ import annotations

import subprocess


RAM_RESERVE_GB = 2.0
VRAM_RESERVE_GB = 1.0
KV_CONTEXT_RESERVE_GB = 1.5

def get_system_resources() -> dict:
    """Mide RAM y VRAM libre real."""
    resources = {
        "ram_free_gb": None, "vram_free_gb": None,
        "ram_reserve_gb": RAM_RESERVE_GB,
        "vram_reserve_gb": VRAM_RESERVE_GB,
        "uncertain": False,
    }
    try:
        import psutil
        mem = psutil.virtual_memory()
        resources["ram_free_gb"] = mem.available / (1024**3)
    except Exception:
        resources["uncertain"] = True

    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=2, check=False
        )
        if result.returncode == 0:
            free_mib = [int(line.strip()) for line in result.stdout.strip().split("\n") if line.strip().isdigit()]
            if free_mib:
                # No se suman GPU: el backend no garantiza que un modelo
                # distribuya capas entre ellas.
                resources["vram_devices_free_gb"] = [value / 1024 for value in free_mib]
                resources["vram_free_gb"] = max(free_mib) / 1024
            else:
                resources["uncertain"] = True
        else:
            resources["vram_error"] = "nvidia-smi devolvió un error"
            resources["uncertain"] = True
    except Exception:
        # Sin una medicion fiable de NVIDIA no se asume VRAM disponible.
        resources["vram_error"] = "nvidia-smi no disponible"
        resources["uncertain"] = True

    return resources

def estimate_model_requirement(params_b: float) -> float:
    """Estimacion conservadora de pesos Q4 y memoria de contexto/KV, en GiB."""
    return (params_b * 0.8) + KV_CONTEXT_RESERVE_GB


def govern_server_process(pid: int, priority: str = "normal",
                          affinity_cores: list[int] | None = None) -> dict:
    """Aplica gobernanza de recursos a un proceso (p.ej. llama-server).

    - ``priority``: 'normal' | 'high' | 'below_normal'. Subir la prioridad del
      servidor nativo evita que el sistema lo interrumpa durante la inferencia,
      pero nunca se usa 'realtime' para no degradar el resto del equipo.
    - ``affinity_cores``: lista explicita de CPUs; si se omite, se fijan los
      nucleos fisicos disponibles (mejora la localidad de cache frente a la
      migracion de hilos por el planificador de Windows).

    Devuelve un dict con lo aplicado y cualquier error (nunca lanza).
    """
    import psutil

    report: dict[str, object] = {"pid": pid, "priority": None,
                                 "affinity_cores": None, "errors": []}
    try:
        process = psutil.Process(pid)
    except psutil.Error as exc:
        report["errors"].append(f"proceso inaccesible: {exc}")
        return report

    priorities = {"normal": psutil.NORMAL_PRIORITY_CLASS,
                  "high": psutil.HIGH_PRIORITY_CLASS,
                  "below_normal": psutil.BELOW_NORMAL_PRIORITY_CLASS}
    if priority in priorities:
        try:
            process.nice(priorities[priority])
            report["priority"] = priority
        except psutil.Error as exc:
            report["errors"].append(f"prioridad: {exc}")

    if affinity_cores:
        try:
            process.cpu_affinity(list(affinity_cores))
            report["affinity_cores"] = list(affinity_cores)
        except psutil.Error as exc:
            report["errors"].append(f"afinidad: {exc}")
    return report


def resource_fit(requirement_gb: float, resources: dict) -> tuple[bool, str]:
    """Un modelo debe caber en un tipo de memoria con su margen reservado.

    No suma RAM y VRAM: el enrutador no conoce el plan de offload del backend.
    Si el peso cabe por completo en alguno de los dos pools medidos, hay una
    ruta conservadora disponible; la capacidad de offload mixto queda incierta.
    """
    ram = resources.get("ram_free_gb")
    vram = resources.get("vram_free_gb")
    ram_reserve = resources.get("ram_reserve_gb", RAM_RESERVE_GB)
    vram_reserve = resources.get("vram_reserve_gb", VRAM_RESERVE_GB)
    ram_safe = isinstance(ram, (int, float)) and ram >= requirement_gb + ram_reserve
    vram_safe = isinstance(vram, (int, float)) and vram >= requirement_gb + vram_reserve
    if vram_safe:
        return True, "VRAM suficiente con margen"
    if ram_safe:
        return True, "RAM suficiente con margen; uso de CPU/offload depende del backend"
    return False, "memoria disponible insuficiente o desconocida"
