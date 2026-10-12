"""Reverse engineering local y de solo lectura, con evidencia.

Dos capacidades, ambas READ_ONLY (no modifican nada del equipo):

* ``reverse.inspect``  analiza un artefacto (``.exe``/``.dll``/``.zip``/APK...)
  sin su codigo fuente: tipo por magic bytes, cabecera PE (arquitectura,
  .NET), empaquetado (PyInstaller/Electron/UPX/NSIS/Inno...), URLs y strings,
  y contenido de ZIPs. Ver ``files.artifact.ArtifactAnalyzer``.

* ``reverse.project``  mapea el codigo fuente de CUALQUIER carpeta del equipo
  (lenguajes, simbolos, imports, tests, matches por consulta) reutilizando el
  ``RepositoryAnalyzer`` ya existente. A diferencia de ``repository.analyze``,
  esta acepta rutas arbitrarias de C: y esta pensada para inspeccionar apps de
  terceros que tienes instaladas o descargadas.

Veracidad: la fuente de la verdad son los bytes/archivos reales. El LLM solo
formatea. Cuando algo no se puede determinar, se declara en las limitaciones
en lugar de inventarlo. Pensado para software propio o autorizado.
"""
from __future__ import annotations

from pathlib import Path

from igris_os.domain import ActionRisk, CapabilitySpec, ExecutionResult
from igris_os.files import ArtifactAnalyzer, RepositoryAnalyzer


def register_reverse_engineering(registry) -> None:
    registry.register(
        CapabilitySpec("reverse.inspect",
                       "Analiza un binario o artefacto sin su codigo fuente "
                       "(tipo, arquitectura, empaquetado, URLs, contenido ZIP)",
                       ActionRisk.READ_ONLY, timeout_seconds=120),
        _reverse_inspect)
    registry.register(
        CapabilitySpec("reverse.project",
                       "Mapea el codigo fuente de cualquier carpeta del equipo "
                       "(lenguajes, simbolos, imports, tests, contexto)",
                       ActionRisk.READ_ONLY, timeout_seconds=300),
        _reverse_project)


def _absolute(value) -> Path:
    raw = str(value or "").strip().strip('"')
    if not raw or "\x00" in raw:
        raise ValueError("Indica una ruta absoluta del equipo")
    path = Path(raw).expanduser()
    if not path.is_absolute():
        raise ValueError("Se necesita una ruta absoluta: " + raw)
    return path.resolve()


def _reverse_inspect(payload):
    try:
        report = ArtifactAnalyzer().analyze(_absolute(payload.get("path")))
    except (ValueError, OSError, PermissionError) as exc:
        return ExecutionResult.failure(str(exc), "REVERSE_INSPECT_FAILED")
    return ExecutionResult.success(
        "Artefacto analizado con evidencia", reverse_inspect={
            "path": report.path, "size": report.size, "sha256": report.sha256,
            "kind": report.kind, "kind_description": report.kind_description,
            "architecture": report.architecture, "bitness": report.bitness,
            "timestamp": report.timestamp, "sections": report.sections,
            "is_dotnet": report.is_dotnet, "packer": report.packer,
            "framework": report.framework, "urls": list(report.urls),
            "notable_strings": list(report.notable_strings),
            "zip_entries": list(report.zip_entries), "notes": list(report.notes),
            "limitations": list(report.limitations), "error": report.error,
        })


def _reverse_project(payload):
    workspace = Path(payload["workspace"])
    try:
        report = RepositoryAnalyzer(workspace).analyze(
            _absolute(payload.get("root")), str(payload.get("query", "")),
            on_progress=payload.get("on_progress"))
    except (ValueError, OSError, PermissionError) as exc:
        return ExecutionResult.failure(str(exc), "REVERSE_PROJECT_INVALID")
    records = [{"path": item["path"], "symbols": item.get("symbols", []),
                "text": item.get("text", "")[:600]} for item in report.records]
    return ExecutionResult.success(
        "Proyecto mapeado con evidencia", reverse_project={
            "files": report.files, "bytes_read": report.bytes_read,
            "languages": report.languages, "symbols": len(report.symbols),
            "imports": len(report.imports), "tests": len(report.tests),
            "matches": report.matches, "manifest": report.manifest,
            "truncated": report.truncated, "records": records,
        })
