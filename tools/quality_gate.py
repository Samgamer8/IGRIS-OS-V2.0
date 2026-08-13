import compileall
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def run(command, env=None):
    completed = subprocess.run(command, cwd=ROOT, env=env)
    if completed.returncode:
        raise SystemExit(completed.returncode)


def main() -> int:
    if not compileall.compile_dir(ROOT / "src", quiet=1):
        return 1
    run([sys.executable, "-m", "pytest"])
    env = os.environ.copy()
    env.update({"PYTHONPATH": "src", "QT_QPA_PLATFORM": "offscreen",
                "IGRIS_TEST_GUI": "1", "PYTHONDONTWRITEBYTECODE": "1"})
    run([sys.executable, "-m", "igris_os", "panel"], env)
    print("QUALITY GATE: APROBADO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
