# -*- coding: utf-8 -*-
"""Verificacion de un juego Godot: arranque + render + referencia.

Comprueba en cadena:

1. que Godot esta disponible;
2. que el juego arranca y corre sin errores (headless);
3. que renderiza un fotograma visible (captura real);
4. opcionalmente, que el fotograma coincide con una referencia.

El punto 3 usa una ventana real porque Godot en modo headless no renderiza
y la captura saldria vacia.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from igris_os.games.runtime import GodotRuntime
from igris_os.multimedia import VisualVerifier


@dataclass(frozen=True, slots=True)
class GamePlaytest:
    ok: bool
    message: str
    version: str = ""
    boot_ok: bool = False
    capture_path: str = ""
    visual_ok: bool = False
    reference_ok: bool | None = None
    reference_path: str = ""
    similarity: float = 0.0


class GameVerifier:
    def __init__(self, runtime: GodotRuntime | None = None) -> None:
        self.runtime = runtime or GodotRuntime()
        self.visual = VisualVerifier()

    def playtest(self, project: Path, capture_dir: Path | None = None,
                 reference: Path | None = None,
                 frames: int = 20) -> GamePlaytest:
        project = Path(project)
        if not (project / "project.godot").is_file():
            return GamePlaytest(False, "Proyecto Godot no disponible")
        if not self.runtime.available:
            return GamePlaytest(False, "Godot no esta disponible")
        version = self.runtime.version()
        boot = self.runtime.run(project, frames=frames, headless=True)
        capture_dir = Path(capture_dir) if capture_dir else project
        capture_path = capture_dir / "igris_playtest.png"
        self.runtime.capture(project, capture_path, frames=frames)
        visual_ok = False
        if capture_path.is_file():
            visual_ok = self.visual.verify_image(capture_path).ok
        reference_ok = None
        similarity = 0.0
        reference_path = ""
        if reference and Path(reference).is_file() and capture_path.is_file():
            comparison = self.visual.compare_reference(capture_path, reference)
            reference_ok = comparison.ok
            similarity = comparison.similarity
            reference_path = str(reference)
        ok = boot.ok and visual_ok and reference_ok is not False
        problems = []
        if not boot.ok:
            problems.append("el juego no arranca sin errores")
        if not visual_ok:
            problems.append("la captura no es visible")
        if reference_ok is False:
            problems.append("no coincide con la referencia")
        if ok:
            message = "Juego verificado: arranca y renderiza"
            if reference_ok:
                message += f" (referencia {similarity:.2f})"
        else:
            message = "Verificacion fallida: " + "; ".join(problems)
        return GamePlaytest(
            ok, message, version, boot.ok,
            str(capture_path) if capture_path.is_file() else "",
            visual_ok, reference_ok, reference_path, similarity)
