import os
import tempfile
import time
from pathlib import Path


def _resolve_pytest_basetemp() -> str:
    configured = os.environ.get("IGRIS_PYTEST_BASETEMP")
    candidates = ([Path(configured).expanduser()] if configured else []) + [
        Path(tempfile.gettempdir()) / "igris_v5_pytest",
    ]
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            run_dir = candidate / f"run-{os.getpid()}-{time.time_ns()}"
            run_dir.mkdir()
            return str(run_dir)
        except OSError:
            continue
    raise RuntimeError("No existe un directorio temporal escribible fuera del repositorio")


def pytest_configure(config):
    if not config.getoption("--basetemp"):
        config.option.basetemp = _resolve_pytest_basetemp()
