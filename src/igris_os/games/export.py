# -*- coding: utf-8 -*-
"""Exportacion de proyectos Godot a ejecutable Windows verificable.

Flujo:

1. comprueba que Godot y las plantillas de exportacion estan instaladas;
2. escribe un preset de exportacion Windows (pck embebido, un solo .exe);
3. exporta con ``godot --headless --export-release``;
4. verifica el .exe: cabecera PE, tamano y lanzamiento real (arranca y
   permanece vivo unos segundos sin crashear).

Las plantillas se buscan en el directorio estandar de Godot
(``%APPDATA%/Godot/export_templates``).
"""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from igris_os.games.runtime import GodotRuntime

PRESET_NAME = "Windows Desktop"

EXPORT_PRESET = """[preset.0]

name="Windows Desktop"
platform="Windows Desktop"
runnable=true
advanced_options=true
dedicated_server=false
custom_features=""
export_filter="all_resources"
include_filter=""
exclude_filter=""
export_path=""
encryption_include_filters=""
encryption_exclude_filters=""
encrypt_pck=false
encrypt_directory=false
script_export_mode=2

[preset.0.options]

custom_template/debug=""
custom_template/release=""
debug/export_console_wrapper=1
binary_format/embed_pck=true
texture_format/bptc=true
texture_format/s3tc=true
texture_format/etc=false
texture_format/etc2=false
binary_format/architecture="x86_64"
codesign/enable=false
application/modify_resources=false
application/icon=""
application/console_wrapper_icon=""
application/icon_interpolation=4
application/file_version=""
application/product_version=""
application/company_name="IGRIS OS"
application/product_name="IGRIS Game"
application/file_description=""
application/copyright=""
application/trademarks=""
application/export_angle=0
application/export_d3d12=0
application/d3d12_agility_sdk_multiarch=true
"""


@dataclass(frozen=True, slots=True)
class ExportResult:
    ok: bool
    message: str
    executable: str = ""
    size: int = 0
    verified: bool = False
    verification: str = ""


class GodotExporter:
    def __init__(self, runtime: GodotRuntime | None = None) -> None:
        self.runtime = runtime or GodotRuntime()

    def templates_dir(self) -> Path | None:
        """Directorio de plantillas con plantilla Windows release x86_64."""
        appdata = os.environ.get("APPDATA", "")
        root = Path(appdata) / "Godot" / "export_templates"
        if not root.is_dir():
            return None
        for pattern in ("*/windows_release_x86_64.exe",
                        "*/templates/windows_release_x86_64.exe"):
            matches = sorted(root.glob(pattern))
            if matches:
                return matches[-1].parent
        return None

    def templates_available(self) -> bool:
        return self.templates_dir() is not None

    def export(self, project: Path, output: Path, *,
               confirmed: bool = False, launch_check: bool = True) -> ExportResult:
        if not confirmed:
            return ExportResult(False, "Se necesita confirmacion")
        project = Path(project)
        if not (project / "project.godot").is_file():
            return ExportResult(False, "Proyecto Godot no disponible")
        if not self.runtime.available:
            return ExportResult(False, "Godot no esta disponible")
        if not self.templates_available():
            return ExportResult(False, "Plantillas de exportacion no instaladas")
        self._write_preset(project)
        output = Path(output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        run = self.runtime._run("--headless", "--path", str(project),
                                "--export-release", PRESET_NAME, str(output))
        if not run.ok or not output.is_file():
            return ExportResult(False, "Exportacion fallida: " + run.output[-400:])
        size = output.stat().st_size
        verified, verification = self.verify_exe(output)
        if verified and launch_check:
            booted, boot_message = self.launch_check(output)
            verified = booted
            verification = (verification + "; " + boot_message)
        return ExportResult(
            verified, "Exportacion completada", str(output), size,
            verified, verification)

    @staticmethod
    def _write_preset(project: Path) -> None:
        (project / "export_presets.cfg").write_text(
            EXPORT_PRESET, encoding="utf-8")

    @staticmethod
    def verify_exe(path: Path | str) -> tuple[bool, str]:
        """Comprueba que es un ejecutable PE con tamano plausible."""
        target = Path(path)
        if not target.is_file() or target.is_symlink():
            return False, "ejecutable no disponible"
        size = target.stat().st_size
        if size < 1_000_000:
            return False, f"tamano sospechoso ({size} bytes)"
        with target.open("rb") as handle:
            if handle.read(2) != b"MZ":
                return False, "no es un ejecutable PE"
        return True, f"PE valido ({size} bytes)"

    @staticmethod
    def launch_check(path: Path | str, seconds: int = 4) -> tuple[bool, str]:
        """Lanza el .exe y confirma que arranca y no crashea en seguida."""
        target = Path(path)
        try:
            process = subprocess.Popen([str(target)])
        except OSError as exc:
            return False, f"no arranca: {exc}"
        try:
            time.sleep(seconds)
            code = process.poll()
            if code is not None:
                return False, f"termino al arrancar (codigo {code})"
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            return True, "arranca y permanece estable"
        except Exception:
            process.kill()
            raise
