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
    """Ejecuta pytest con coverage si esta disponible y exige un umbral."""
    if shutil.which("coverage") is None and not _coverage_module_available():
        print("WARNING: coverage no instalado; se omite el umbral de cobertura")
        return
    env = os.environ.copy()
    env["IGRIS_MIN_COVERAGE"] = str(MIN_COVERAGE)
    completed = run(
        [sys.executable, "-m", "pytest",
         f"--cov=igris_os", "--cov-report=term:skip-covered"],
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
    print("QUALITY GATE: APROBADO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
