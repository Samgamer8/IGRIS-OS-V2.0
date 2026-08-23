"""Watcher del quality gate: reacciona al guardar cambios.

Uso:
    py -3.12 tools/watch.py            # chequeo rapido en cada guardado (~3s)
    py -3.12 tools/watch.py --full     # quality gate completo (~6 min)
    py -3.12 tools/watch.py --once     # una sola pasada y salir

Observa ``src/``, ``tests/``, ``main.py`` y ``tools/``. Por defecto corre el
chequeo rapido (compileall + arranque del entry point) porque el gate completo
tarda varios minutos y no es viable por cada guardado.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WATCH_ROOTS = [ROOT / "src", ROOT / "tests", ROOT / "tools"]
WATCH_FILES = [ROOT / "main.py"]
IGNORED_PARTS = {"__pycache__", ".git", ".pytest_cache", ".freebuff", "runtime"}

DEBOUNCE_SECONDS = 1.5


def snapshot() -> dict[str, tuple[int, int]]:
    """Firma (mtime_ns, size) de todos los .py observados."""
    sigs: dict[str, tuple[int, int]] = {}
    for base in WATCH_ROOTS:
        if not base.is_dir():
            continue
        for path in base.rglob("*.py"):
            if any(part in IGNORED_PARTS for part in path.parts):
                continue
            try:
                st = path.stat()
            except OSError:
                continue
            sigs[str(path)] = (st.st_mtime_ns, st.st_size)
    for path in WATCH_FILES:
        try:
            st = path.stat()
        except OSError:
            continue
        sigs[str(path)] = (st.st_mtime_ns, st.st_size)
    return sigs


def run_fast() -> int:
    import compileall
    if not compileall.compile_dir(ROOT / "src", quiet=1):
        return 1
    env = os.environ.copy()
    env.update({
        "QT_QPA_PLATFORM": "offscreen",
        "IGRIS_TEST_GUI": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    return subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_entry_point.py", "-q"],
        cwd=ROOT, env=env,
    ).returncode


def run_full() -> int:
    return subprocess.run(
        [sys.executable, "tools/quality_gate.py"],
        cwd=ROOT,
    ).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Watcher del quality gate de IGRIS")
    parser.add_argument("--full", action="store_true",
                        help="corre el quality gate completo en vez del chequeo rapido")
    parser.add_argument("--once", action="store_true",
                        help="una sola pasada y salir")
    args = parser.parse_args()

    run = run_full if args.full else run_fast
    label = "GATE COMPLETO" if args.full else "CHEQUEO RAPIDO"

    def execute(trigger: str) -> int:
        stamp = time.strftime("%H:%M:%S")
        print(f"\n[{stamp}] {label} — {trigger}")
        code = run()
        print(f"[{time.strftime('%H:%M:%S')}] "
              f"{'OK' if code == 0 else f'FALLO (exit {code})'}")
        return code

    if args.once:
        return execute("arranque manual")

    watched = ", ".join(str(ROOT / name) for name in ("src", "tests", "tools"))
    print(f"Observando cambios en: {watched} y {ROOT / 'main.py'}")
    print(f"Modo: {label}. Ctrl+C para salir.\n")

    last = snapshot()
    pending_since: float | None = None
    while True:
        time.sleep(0.5)
        current = snapshot()
        if current != last:
            last = current
            pending_since = time.monotonic()
        if pending_since is not None and time.monotonic() - pending_since >= DEBOUNCE_SECONDS:
            pending_since = None
            execute("cambio detectado")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nWatcher detenido.")
        raise SystemExit(0)
