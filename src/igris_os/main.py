# src/igris_os/main.py
from __future__ import annotations

import logging
import sys
import traceback
from pathlib import Path

# --------------------------------------------------------------------------- #
# 1️⃣ Configuración de rutas y sys.path (solo una vez)
# --------------------------------------------------------------------------- #
_ROOT = Path(__file__).resolve().parent.parent.parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# --------------------------------------------------------------------------- #
# 2️⃣ Logger global – evita duplicados y garantiza la carpeta de logs
# --------------------------------------------------------------------------- #
_LOG_FILE: Path = _ROOT / "runtime" / "logs" / "main.log"
_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(_LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    encoding="utf-8",
)
log = logging.getLogger("igris.main")

# --------------------------------------------------------------------------- #
# 3️⃣ Helpers de salida
# --------------------------------------------------------------------------- #
def _exit_code(code: object) -> int:
    return code if isinstance(code, int) else (0 if code is None else 1)

# --------------------------------------------------------------------------- #
# 4️⃣ Main – control de flujo y degradación segura
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv

    try:
        # Panel gráfico si no hay argumentos
        if not args:
            from igris_os.ui import run_panel  # lazy import
            return run_panel()

        # Comandos CLI
        from igris_os.cli import main as cli_main
        return cli_main(args)

    except SystemExit as exc:          # Propagamos códigos de salida explícitos
        return _exit_code(exc.code)
    except KeyboardInterrupt:
        log.info("Interrumpido por el usuario")
        print("\nInterrumpido por el usuario.", file=sys.stderr)
        return 130
    except Exception as exc:           # Degradación controlada
        log.exception("Error inesperado en punto de entrada")
        traceback.print_exc(file=sys.stderr)
        print(
            f"\nIGRIS OS se detuvo por un error inesperado: {exc}\n"
            f"Detalle registrado en {_LOG_FILE}",
            file=sys.stderr,
        )
        return 1

# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    raise SystemExit(main())