"""Operaciones reales sobre el equipo, con los permisos del usuario de IGRIS."""
from __future__ import annotations

import ctypes
import fnmatch
import getpass
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import time
import tempfile

import psutil

from igris_os.domain import ActionRisk, CapabilitySpec, ExecutionResult


def register_host_capabilities(registry):
    for name, description, handler, changes in (
        ("inventory", "Consulta CPU, memoria, unidades, GPU y permisos reales", inventory, False),
        ("list", "Lista una carpeta del equipo", list_directory, False),
        ("find", "Busca archivos locales e informa limites y errores de acceso", find_files, False),
        ("read", "Lee un archivo de texto local", read_file, False),
        ("mkdir", "Crea una carpeta en la ruta autorizada del equipo", make_directory, True),
        ("copy", "Copia un archivo a la ruta autorizada sin sobrescribir", copy_file, True),
        ("open", "Abre un archivo, carpeta o programa con Windows", open_path, True),
        ("open_url", "Abre una URL HTTPS de github.com en el navegador (solo lectura, bajo permiso)", open_url, True),
    ):
        registry.register(CapabilitySpec(
            "host." + name, description,
            ActionRisk.EXTERNAL if changes else ActionRisk.READ_ONLY,
            timeout_seconds=60), handler)
    from igris_os.capabilities.windows_diagnostics import register_windows_diagnostic_capabilities
    register_windows_diagnostic_capabilities(registry)


def _path(value):
    raw = str(value or "").strip().strip('"')
    if not raw or "\x00" in raw:
        raise ValueError("Indica una ruta absoluta del equipo")
    path = Path(os.path.expandvars(raw)).expanduser()
    if not path.is_absolute():
        raise ValueError("Se necesita una ruta absoluta: " + raw)
    return path.resolve()


def _failure(exc):
    code = "HOST_ACCESS_DENIED" if isinstance(exc, PermissionError) else "HOST_OPERATION_FAILED"
    return ExecutionResult.failure(str(exc), code)


def inventory(payload):
    memory = psutil.virtual_memory()
    report = {
        "system": platform.platform(), "user": getpass.getuser(),
        "administrator": bool(ctypes.windll.shell32.IsUserAnAdmin()) if os.name == "nt"
        else os.geteuid() == 0,
        "cpu": platform.processor(), "logical_cpus": psutil.cpu_count(),
        "ram_total_gib": round(memory.total / 1024 ** 3, 2),
        "ram_available_gib": round(memory.available / 1024 ** 3, 2),
        "drives": [], "gpu": [], "diagnostics": [],
    }
    for part in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
            report["drives"].append({"path": part.mountpoint,
                                     "free_gib": round(usage.free / 1024 ** 3, 2)})
        except OSError as exc:
            report["diagnostics"].append(str(exc))
    if os.name == "nt":
        try:
            result = subprocess.run([
                "powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
                "@(Get-CimInstance Win32_VideoController | "
                "Select-Object Name,DriverVersion) | ConvertTo-Json -Compress"],
                capture_output=True, timeout=15, encoding="utf-8", errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode:
                report["diagnostics"].append(result.stderr[-1000:])
            elif result.stdout.strip():
                report["gpu"] = json.loads(result.stdout.lstrip("\ufeff"))
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            report["diagnostics"].append("GPU: " + str(exc))
    return ExecutionResult.success("Recursos locales consultados", host_report=report)


def list_directory(payload):
    try:
        root = _path(payload.get("path"))
        entries = []
        with os.scandir(root) as iterator:
            for entry in iterator:
                if len(entries) >= 500:
                    return ExecutionResult.success("Listado parcial: limite de 500 entradas",
                                                   host_report={"root": str(root), "entries": entries, "partial": True})
                entries.append({"path": entry.path, "directory": entry.is_dir(follow_symlinks=False)})
        return ExecutionResult.success("Carpeta consultada", host_report={"root": str(root), "entries": entries, "partial": False})
    except (OSError, ValueError) as exc:
        return _failure(exc)


def find_files(payload):
    try:
        root_value = payload.get("root")
        roots = [_path(root_value)] if root_value else [Path(p.mountpoint) for p in psutil.disk_partitions()
                                                        if "cdrom" not in p.opts]
        if not roots:
            roots = [Path.home()]
        for root in roots:
            if not root.is_dir():
                raise ValueError("La carpeta de busqueda no existe: " + str(root))
        pattern = str(payload.get("pattern", "")).strip()
        if not pattern or len(pattern) > 250 or any(c in pattern for c in "\\/\x00"):
            raise ValueError("Indica un nombre o patron de archivo, por ejemplo *.tpz")
        if not any(c in pattern for c in "*?["):
            pattern = "*" + pattern + "*"
        deadline = time.monotonic() + min(30, max(0.01, float(payload.get("seconds", 20))))
        matches, errors = [], []
        pending, visited, partial = list(roots), 0, False
        while pending:
            if time.monotonic() >= deadline or visited >= 100000 or len(matches) >= 200:
                partial = True
                break
            directory = pending.pop()
            try:
                with os.scandir(directory) as iterator:
                    for entry in iterator:
                        visited += 1
                        if time.monotonic() >= deadline or visited >= 100000 or len(matches) >= 200:
                            partial = True
                            break
                        if fnmatch.fnmatchcase(entry.name.casefold(), pattern.casefold()):
                            matches.append(entry.path)
                        # Junctions/symlinks can lead to loops or remote drives.
                        if (entry.is_dir(follow_symlinks=False) and not entry.is_symlink()
                                and not (getattr(os.path, "isjunction", lambda p: False)(entry.path))):
                            pending.append(Path(entry.path))
                if partial:
                    break
            except OSError as exc:
                if len(errors) < 100:
                    errors.append(str(exc))
        report = {"roots": [str(r) for r in roots], "pattern": pattern, "matches": matches,
                  "visited": visited, "partial": partial or bool(errors), "access_errors": errors}
        return ExecutionResult.success(
            "Busqueda parcial; acota la carpeta para continuar" if report["partial"] else "Busqueda terminada",
            host_report=report)
    except (OSError, ValueError) as exc:
        return _failure(exc)


def read_file(payload):
    try:
        path = _path(payload.get("path"))
        with path.open("rb") as stream:
            raw = stream.read(65537)
        partial = len(raw) > 65536
        raw = raw[:65536]
        if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
            content = raw.decode("utf-16", errors="replace")
        else:
            if b"\0" in raw:
                raise ValueError("Archivo binario; utiliza la inspeccion de adjuntos")
            content = raw.decode("utf-8-sig", errors="replace")
        return ExecutionResult.success("Archivo leido" + (" parcialmente" if partial else ""),
                                       host_report={"path": str(path), "content": content, "partial": partial})
    except (OSError, ValueError) as exc:
        return _failure(exc)


def make_directory(payload):
    try:
        path = _path(payload.get("path"))
        path.mkdir(parents=True, exist_ok=False)
        return ExecutionResult.success("Carpeta creada", host_report={"path": str(path)})
    except (OSError, ValueError) as exc:
        return _failure(exc)


def copy_file(payload):
    temporary = None
    try:
        source, target = _path(payload.get("source")), _path(payload.get("target"))
        if not source.is_file():
            raise ValueError("No existe el archivo origen: " + str(source))
        if target.exists():
            raise FileExistsError("El destino ya existe: " + str(target))
        with source.open("rb") as src, tempfile.NamedTemporaryFile(
                dir=target.parent, prefix="igris-copy-", suffix=".partial", delete=False) as dest:
            temporary = Path(dest.name)
            shutil.copyfileobj(src, dest)
        # Publish only a complete file. link() cannot overwrite an existing path.
        os.link(temporary, target)
        return ExecutionResult.success("Archivo copiado", host_report={"source": str(source), "target": str(target), "bytes": target.stat().st_size})
    except (OSError, ValueError) as exc:
        return _failure(exc)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def open_url(payload):
    """Abre una URL HTTPS (solo github.com) en el navegador por defecto.

    Solo lectura en el sentido de que no modifica nada local: delega la
    apertura al navegador del sistema mediante ``os.startfile`` en Windows.
    Como abre una aplicacion externa, queda marcada EXTERNAL y el panel pide
    permiso antes de ejecutarla.
    """
    try:
        from urllib.parse import urlparse
        raw = str(payload.get("url", "") or "").strip().strip('"')
        if not raw:
            raise ValueError("Indica una URL https://github.com/...")
        parsed = urlparse(raw)
        if parsed.scheme != "https" or parsed.hostname not in {"github.com", "www.github.com"}:
            raise ValueError("Solo se pueden abrir URLs HTTPS de github.com")
        if os.name != "nt":
            return ExecutionResult.failure("Abrir URLs requiere Windows", "HOST_WINDOWS_REQUIRED")
        os.startfile(raw)
        return ExecutionResult.success("Windows acepto la solicitud de apertura; no verifica el resultado del navegador",
                                       host_report={"url": raw, "opening_requested": True})
    except (OSError, ValueError) as exc:
        return _failure(exc)


def open_path(payload):
    try:
        path = _path(payload.get("path"))
        if not path.exists():
            raise ValueError("La ruta no existe: " + str(path))
        if os.name != "nt":
            return ExecutionResult.failure("Abrir programas del equipo requiere Windows", "HOST_WINDOWS_REQUIRED")
        os.startfile(str(path))
        return ExecutionResult.success("Windows acepto la solicitud de apertura; no verifica el resultado del programa",
                                       host_report={"path": str(path), "opening_requested": True})
    except (OSError, ValueError) as exc:
        return _failure(exc)
