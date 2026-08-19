import compileall
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]

MIN_COVERAGE = float(os.environ.get("IGRIS_MIN_COVERAGE", "55"))


def run(command, env=None, capture=False):
    if capture:
        completed = subprocess.run(command, cwd=ROOT, env=env,
                                   capture_output=True, text=True)
    else:
        completed = subprocess.run(command, cwd=ROOT, env=env)
    if completed.returncode:
        raise SystemExit(completed.returncode)
    return completed


def check_coverage() -> None:
    """Ejecuta pytest con coverage si esta disponible y exige un umbral.

    Usa la CLI ``coverage`` (declarada en las dependencias dev) en vez de
    ``pytest --cov``, que requiere el plugin ``pytest-cov`` y no esta en el
    proyecto.
    """
    if shutil.which("coverage") is None and not _coverage_module_available():
        print("WARNING: coverage no instalado; se omite el umbral de cobertura")
        return
    env = os.environ.copy()
    env["IGRIS_MIN_COVERAGE"] = str(MIN_COVERAGE)
    run([sys.executable, "-m", "coverage", "run", "--source=igris_os",
         "-m", "pytest"], env=env, capture=True)
    completed = run([sys.executable, "-m", "coverage", "report"],
                    env=env, capture=True)
    match = re.search(r"TOTAL\s+.*?(\d+)%", completed.stdout)
    if not match:
        raise SystemExit("No se pudo leer el total de cobertura")
    total = float(match.group(1))
    print(f"COBERTURA: {total:.0f}% (minimo {MIN_COVERAGE:.0f}%)")
    if total < MIN_COVERAGE:
        raise SystemExit(f"COBERTURA BAJA: {total:.0f}% < {MIN_COVERAGE:.0f}%")


def _coverage_module_available() -> bool:
    try:
        import coverage  # noqa: F401
        return True
    except ImportError:
        return False


def check_entry_point_startup() -> None:
    """Lanza el entry point real tal como lo arranca el usuario.

    El launcher windowed y el acceso directo ejecutan ``main.py`` (pyw/pythonw),
    no el modulo ``-m igris_os``. Esta prueba reproduce ese camino exacto:
    - ``main.py`` sin argumentos abre el panel offscreen y se cierra solo
      (IGRIS_TEST_GUI=1), asi que un import roto en cualquier capa rompe la
      prueba con un codigo de salida distinto de cero.
    - ``main.py health`` valida el modo CLI y exige ``"ok": true``.

    No se fija PYTHONPATH a proposito: ``main.py`` debe ser auto-contenido
    (inyecta ``src`` en sys.path), igual que cuando lo lanza el acceso directo.
    """
    env = os.environ.copy()
    env.update({
        "QT_QPA_PLATFORM": "offscreen",
        "IGRIS_TEST_GUI": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    print("ENTRY POINT: main.py (panel offscreen)")
    run([sys.executable, "main.py"], env)
    print("ENTRY POINT: main.py health")
    completed = run([sys.executable, "main.py", "health"], env, capture=True)
    if '"ok": true' not in completed.stdout:
        raise SystemExit("main.py health no devolvio 'ok':\n" + completed.stdout)


def main() -> int:
    if not compileall.compile_dir(ROOT / "src", quiet=1):
        return 1
    run([sys.executable, "-m", "pytest"])
    check_coverage()
    run([sys.executable, "tools/release_check.py"])
    env = os.environ.copy()
    env.update({"PYTHONPATH": "src", "QT_QPA_PLATFORM": "offscreen",
                "IGRIS_TEST_GUI": "1", "PYTHONDONTWRITEBYTECODE": "1"})
    run([sys.executable, "-m", "igris_os", "panel"], env)
    check_entry_point_startup()
    print("QUALITY GATE: APROBADO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
