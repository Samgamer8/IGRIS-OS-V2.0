"""Prueba de arranque del entry point real (``main.py``).

Replica lo que ejecutan el acceso directo del escritorio y
``launch_igris.vbs`` (``pythonw main.py``):

- ``main.py`` sin argumentos abre el panel offscreen y se cierra solo
  (``IGRIS_TEST_GUI=1``); un import roto en cualquier capa rompe la prueba.
- ``main.py health`` valida el modo CLI y exige ``"ok": true``.

No se fija ``PYTHONPATH`` a proposito: ``main.py`` debe ser auto-contenido
(inyecta ``src`` en ``sys.path``), igual que cuando lo lanza el acceso
directo.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAIN_PY = ROOT / "main.py"


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env.update({
        "QT_QPA_PLATFORM": "offscreen",
        "IGRIS_TEST_GUI": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    return env


def _run(*args: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(MAIN_PY), *args],
        cwd=ROOT,
        env=_env(),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def test_entry_point_panel_starts_offscreen() -> None:
    """El panel real arranca y se cierra solo sin import roto."""
    pytest.importorskip("PyQt6")
    completed = _run()
    assert completed.returncode == 0, (
        f"main.py (panel offscreen) fallo con exit {completed.returncode}\n"
        f"STDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
    )


def test_entry_point_health_reports_ok() -> None:
    """El modo CLI health devuelve el nucleo operativo (no solo exit 0)."""
    completed = _run("health")
    assert completed.returncode == 0, (
        f"main.py health fallo con exit {completed.returncode}\n"
        f"STDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
    )
    assert '"ok": true' in completed.stdout, (
        f"main.py health no devolvio 'ok':\n{completed.stdout}"
    )
