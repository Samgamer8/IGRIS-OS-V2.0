"""
Benchmark de latencia del flujo principal de IGRIS OS.

Mide el tiempo de respuesta desde la orden hasta el resultado verificable,
identificando cuellos de botella en el flujo de programación autonoma.

Este benchmark es evidencia productiva: mejora la capacidad de diagnostico
y optimizacion del flujo principal de IGRIS como programador.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from igris_os.application import MissionDirector
from igris_os.domain import Mission
from igris_os.programming.coordinator import AutonomousProgrammingCoordinator


class LatencyProfiler:
    """Captura tiempos de latencia en cada etapa del flujo principal."""

    def __init__(self):
        self.stages: dict[str, float] = {}
        self.total_start: float | None = None

    def start(self, stage: str) -> None:
        """Marca el inicio de una etapa."""
        self.stages[f"{stage}_start"] = time.perf_counter()

    def end(self, stage: str) -> float:
        """Marca el fin de una etapa y devuelve la latencia en ms."""
        end_time = time.perf_counter()
        start_key = f"{stage}_start"
        if start_key not in self.stages:
            return 0.0
        latency_ms = (end_time - self.stages[start_key]) * 1000
        self.stages[stage] = latency_ms
        del self.stages[start_key]
        return latency_ms

    def report(self) -> dict[str, float]:
        """Devuelve el reporte de latencias sin los marcadores de inicio."""
        return {k: v for k, v in self.stages.items() if not k.endswith("_start")}

    def slowest_stage(self) -> tuple[str, float] | None:
        """Devuelve la etapa mas lenta."""
        report = self.report()
        if not report:
            return None
        return max(report.items(), key=lambda x: x[1])


@pytest.fixture
def profiler():
    """Proporciona un profiler de latencia."""
    return LatencyProfiler()


def test_latency_mission_planning(profiler: LatencyProfiler):
    """Mide latencia de planificacion de mision."""
    profiler.start("mission_planning")

    director = MissionDirector()
    mission = Mission("crear una funcion que valide emails")
    plan = director.plan(mission)

    latency_ms = profiler.end("mission_planning")

    # Verificacion de resultado
    assert plan.mission_id is not None
    assert plan.branch is not None
    assert len(plan.deliverables) > 0

    # El plan debe completarse en menos de 10 segundos (generoso para LLM local)
    assert latency_ms < 10000, f"Plan tardo {latency_ms:.1f}ms, esperado < 10000ms"

    # Registrar resultado
    print(f"\n[LATENCY] Mission Planning: {latency_ms:.1f}ms")


def test_latency_health_check(profiler: LatencyProfiler):
    """Mide latencia de verificacion de salud del entorno."""
    profiler.start("health_check")

    from igris_os.application import RuntimeProbe
    probe = RuntimeProbe(Path.cwd())
    statuses = probe.probe()

    latency_ms = profiler.end("health_check")

    # Verificacion de resultado
    assert isinstance(statuses, dict)
    assert len(statuses) > 0

    # El health check debe ser rapido (< 2 segundos)
    assert latency_ms < 2000, f"Health check tardo {latency_ms:.1f}ms, esperado < 2000ms"

    print(f"\n[LATENCY] Health Check: {latency_ms:.1f}ms")


def test_latency_cli_parsing(profiler: LatencyProfiler):
    """Mide latencia de parsing de argumentos CLI."""
    profiler.start("cli_parsing")

    from igris_os.cli import main as cli_main
    # Mock para capturar salida sin ejecutar realmente
    with patch("sys.exit", side_effect=SystemExit(0)):
        try:
            cli_main(["health"])
        except SystemExit:
            pass

    latency_ms = profiler.end("cli_parsing")

    # El parsing debe ser inmediato (< 500ms)
    assert latency_ms < 500, f"CLI parsing tardo {latency_ms:.1f}ms, esperado < 500ms"

    print(f"\n[LATENCY] CLI Parsing: {latency_ms:.1f}ms")


def test_latency_bootstrap(profiler: LatencyProfiler):
    """Mide latencia de inicializacion del kernel IGRIS."""
    profiler.start("bootstrap")

    from igris_os.bootstrap import build_igris
    kernel = build_igris()

    latency_ms = profiler.end("bootstrap")

    # Verificacion de resultado
    assert kernel is not None

    # El bootstrap debe completarse en tiempo razonable (< 5 segundos)
    assert latency_ms < 5000, f"Bootstrap tardo {latency_ms:.1f}ms, esperado < 5000ms"

    print(f"\n[LATENCY] Bootstrap: {latency_ms:.1f}ms")


def test_latency_profile_summary(profiler: LatencyProfiler):
    """Ejecuta todos los tests de latencia y genera un reporte consolidado."""
    all_latencies = {}

    # Ejecutar cada etapa
    print("\n" + "="*60)
    print("BENCHMARK DE LATENCIA DEL FLUJO PRINCIPAL - IGRIS OS")
    print("="*60)

    # 1. Bootstrap
    profiler.start("bootstrap")
    from igris_os.bootstrap import build_igris
    kernel = build_igris()
    all_latencies["bootstrap"] = profiler.end("bootstrap")

    # 2. Mission Planning
    profiler.start("mission_planning")
    director = MissionDirector()
    mission = Mission("crear funcion de validacion")
    plan = director.plan(mission)
    all_latencies["mission_planning"] = profiler.end("mission_planning")

    # 3. Health Check
    profiler.start("health_check")
    from igris_os.application import RuntimeProbe
    probe = RuntimeProbe(Path.cwd())
    statuses = probe.probe()
    all_latencies["health_check"] = profiler.end("health_check")

    # Generar reporte
    total_ms = sum(all_latencies.values())
    report = {
        "timestamp": time.time(),
        "stages": all_latencies,
        "total_ms": total_ms,
        "slowest_stage": max(all_latencies.items(), key=lambda x: x[1])[0],
        "fastest_stage": min(all_latencies.items(), key=lambda x: x[1])[0],
    }

    print("\nRESULTADOS:")
    print("-" * 60)
    for stage, latency_ms in all_latencies.items():
        pct = (latency_ms / total_ms * 100) if total_ms > 0 else 0
        print(f"  {stage:.<30} {latency_ms:>8.1f}ms ({pct:>5.1f}%)")
    print("-" * 60)
    print(f"  {'TOTAL':.<30} {total_ms:>8.1f}ms (100.0%)")
    print("-" * 60)

    # Guardar reporte en archivo de auditoria
    audit_dir = Path("runtime/audit")
    audit_dir.mkdir(parents=True, exist_ok=True)
    audit_file = audit_dir / "latency_profile_2026-08-26.json"
    audit_file.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nReporte guardado en: {audit_file}")
    print("="*60)

    # Aserciones de calidad
    assert total_ms > 0, "No se capturó latencia"
    assert len(all_latencies) == 3, "Faltaron etapas"
    # El flujo principal completo debe ser razonable (< 30 segundos para LLM local)
    assert total_ms < 30000, f"Flujo principal tardo {total_ms:.1f}ms, esperado < 30000ms"
