"""Instala el hook de pre-commit que ejecuta el quality gate de IGRIS.

Uso:
    py -3.12 tools/install_hooks.py

Escribe ``.git/hooks/pre-commit`` (no se versiona, por eso existe este
instalador). Al commitear ejecuta ``py -3.12 tools/quality_gate.py``; si no
hay launcher ``py``, usa ``python``.

Atajos:
- Saltar el gate puntualmente:  ``git commit --no-verify``
- Chequeo rapido en el commit: ``IGRIS_FAST_GATE=1 git commit``
"""
from __future__ import annotations

import stat
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK_PATH = ROOT / ".git" / "hooks" / "pre-commit"

HOOK = r'''#!/bin/sh
# IGRIS OS V2.0 - pre-commit: quality gate automatico.
# Saltar con: git commit --no-verify
# Chequeo rapido: IGRIS_FAST_GATE=1 git commit
set -e

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

find_py() {
    if command -v py >/dev/null 2>&1 && py -3.12 --version >/dev/null 2>&1; then
        printf '%s\n' "py -3.12"
    elif command -v python >/dev/null 2>&1; then
        printf '%s\n' "python"
    else
        printf '%s\n' ""
    fi
}

PY="$(find_py)"
if [ -z "$PY" ]; then
    echo "IGRIS pre-commit: no se encontro Python en PATH" >&2
    exit 1
fi

if [ "$IGRIS_FAST_GATE" = "1" ]; then
    echo "== IGRIS pre-commit: chequeo rapido =="
    $PY -c "import compileall, sys; sys.exit(0 if compileall.compile_dir('src', quiet=1) else 1)"
    $PY -m pytest tests/test_entry_point.py -q
else
    echo "== IGRIS pre-commit: quality gate completo =="
    $PY tools/quality_gate.py
fi
'''


def main() -> int:
    hooks_dir = HOOK_PATH.parent
    if not hooks_dir.is_dir():
        print(f"No se encontro {hooks_dir} (¿es un repositorio git?)")
        return 1
    HOOK_PATH.write_text(HOOK, encoding="utf-8")
    try:
        HOOK_PATH.chmod(HOOK_PATH.stat().st_mode | stat.S_IEXEC)
    except OSError:
        pass
    print(f"Hook instalado: {HOOK_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
