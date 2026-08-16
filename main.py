# -*- coding: utf-8 -*-
"""IGRIS OS V2.0 — punto de entrada unificado.

Sin argumentos lanza el panel grafico; con argumentos delega en la CLI
(p. ej. ``python main.py health``, ``python main.py plan "..."``).

Tolerancia a fallos: cualquier error inesperado se registra en
``runtime/logs/main.log`` y se devuelve un codigo de salida claro, en lugar
de terminar con un traceback crudo (degradacion controlada).
"""

from __future__ import annotations

import logging
import sys
import traceback
from pathlib import Path

# Asegura que el paquete `igris_os` sea importable al ejecutar desde la raiz.
_ROOT = Path(__file__).resolve().parent
_SRC = _ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

_LOG_FILE = _ROOT / "runtime" / "logs" / "main.log"


def _configure_logging() -> None:
    _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=_LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        encoding="utf-8",
    )


def _exit_code(code: object) -> int:
    if isinstance(code, int):
        return code
    return 0 if code is None else 1


def main(argv: list[str] | None = None) -> int:
    _configure_logging()
    logger = logging.getLogger("igris.main")
    arguments = sys.argv if argv is None else ["igris", *argv]
    try:
        if len(arguments) <= 1:
            from igris_os.ui import run_panel
            return run_panel()
        from igris_os.cli import main as cli_main
        return cli_main(arguments[1:])
    except SystemExit as exc:
        return _exit_code(exc.code)
    except KeyboardInterrupt:
        logger.info("Interrumpido por el usuario")
        print("\nInterrumpido por el usuario.", file=sys.stderr)
        return 130
    except Exception as exc:  # degradacion controlada, nunca silenciosa
        logger.exception("Error no controlado en el punto de entrada")
        traceback.print_exc(file=sys.stderr)
        print(f"\nIGRIS OS se detuvo por un error inesperado: {exc}\n"
              f"Detalle registrado en {_LOG_FILE}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
