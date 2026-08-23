# -*- coding: utf-8 -*-
"""Localizacion y ejecucion del runtime Godot.

Busca Godot en este orden y usa el primero que exista:

1. variable de entorno ``IGRIS_GODOT``;
2. el Godot portable incluido en ``.tools/godot/`` (relativo a la raiz del
   proyecto, que es el directorio de trabajo de IGRIS OS);
3. ``godot`` / ``godot4`` en el PATH.

Nunca descarga ni instala nada: solo localiza y ejecuta.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class GodotRun:
    ok: bool
    returncode: int
    output: str
    command: tuple[str, ...] = ()


class GodotRuntime:
    def __init__(self, executable: str | Path | None = None,
                 timeout: int = 120) -> None:
        self.timeout = timeout
        self.executable = self._resolve(executable)

    @staticmethod
    def _resolve(explicit: str | Path | None) -> Path | None:
        candidates: list[Path] = []
        if explicit:
            candidates.append(Path(explicit))
        env = os.environ.get("IGRIS_GODOT")
        if env:
            candidates.append(Path(env))
        bundled = Path(".tools", "godot")
        if bundled.is_dir():
            candidates.extend(sorted(bundled.glob("Godot_*_win64.exe")))
            candidates.extend(sorted(bundled.glob("Godot_*_win64_console.exe")))
        for name in ("godot", "godot4"):
            found = shutil.which(name)
            if found:
                candidates.append(Path(found))
        for candidate in candidates:
            if candidate.is_file():
                return candidate.resolve()
        return None

    @property
    def available(self) -> bool:
        return self.executable is not None

    def version(self) -> str:
        if not self.executable:
            return ""
        run = self._run("--version")
        return run.output.strip().splitlines()[0] if run.ok else ""

    def import_project(self, project: Path) -> GodotRun:
        """Importa/compila los recursos de un proyecto en modo headless."""
        return self._run("--headless", "--path", str(project), "--import")

    def run(self, project: Path, *, frames: int = 60,
            headless: bool = True,
            extra: tuple[str, ...] = ()) -> GodotRun:
        """Ejecuta el juego un numero fijo de fotogramas y sale.

        ``headless=True`` valida arranque/logica sin render; ``False`` renderiza
        en una ventana real (necesario para capturar un fotograma).
        """
        args = [] if not headless else ["--headless"]
        args += ["--path", str(project), "--quit-after", str(frames), *extra]
        return self._run(*args)

    def capture(self, project: Path, output: Path, *,
                frames: int = 10, headless: bool = False) -> GodotRun:
        """Ejecuta el juego y guarda una captura en ``output``.

        Por defecto usa una ventana real, porque en modo headless Godot no
        renderiza y el fotograma saldria vacio.
        """
        output.parent.mkdir(parents=True, exist_ok=True)
        return self.run(project, frames=frames, headless=headless,
                        extra=("--", f"--igris-capture={output}"))

    def _run(self, *args: str) -> GodotRun:
        if not self.executable:
            return GodotRun(False, -1, "Godot no esta disponible")
        command = (str(self.executable), *args)
        try:
            run = subprocess.run(command, capture_output=True, text=True,
                                 timeout=self.timeout)
        except subprocess.TimeoutExpired:
            return GodotRun(False, -1, "Godot agoto el tiempo", command)
        output = (run.stdout or "") + (run.stderr or "")
        return GodotRun(run.returncode == 0, run.returncode, output, command)
