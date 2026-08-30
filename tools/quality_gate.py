"""Puerta de calidad V5 estable, acotada y honesta."""

from __future__ import annotations

import argparse
import compileall
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CRITICAL_TESTS = [
    "tests/test_approval.py",
    "tests/test_delivery_verifier.py",
    "tests/test_cli_delivery.py",
    "tests/test_security.py",
    "tests/test_sandbox.py",
    "tests/test_entry_point.py",
    "tests/test_bootstrap.py",
    "tests/test_kernel.py",
    "tests/test_game_developer.py",
    "tests/test_games_verifier.py",
    "tests/test_creation_readiness.py",
]


def run_phase(name: str, command: list[str], timeout: int,
              env: dict[str, str]) -> dict[str, object]:
    started = time.monotonic()
    try:
        completed = subprocess.run(command, cwd=ROOT, env=env,
                                   stdin=subprocess.DEVNULL,
                                   capture_output=True, text=True,
                                   timeout=timeout)
        return {"ok": completed.returncode == 0, "name": name,
                "returncode": completed.returncode, "timed_out": False,
                "duration_seconds": round(time.monotonic() - started, 3),
                "output": (completed.stdout + completed.stderr)[-12000:]}
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + (exc.stderr or "")
        return {"ok": False, "name": name, "returncode": 124,
                "timed_out": True,
                "duration_seconds": round(time.monotonic() - started, 3),
                "output": str(output)[-12000:]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Valida IGRIS OS")
    parser.add_argument("--full", action="store_true",
                        help="ejecuta toda la suite de pruebas")
    args = parser.parse_args(argv)
    temp_root = Path(os.environ.get("TEMP", ROOT / "runtime")) / "igris_v5_quality"
    temp_root.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"),
           "PYTHONDONTWRITEBYTECODE": "1",
           "IGRIS_PYTEST_BASETEMP": str(temp_root / f"run-{os.getpid()}")}
    tests = ["tests"] if args.full else CRITICAL_TESTS
    suite_name = "full_suite" if args.full else "critical_suite"
    report: dict[str, object] = {
        "compile": {"ok": compileall.compile_dir(ROOT / "src", quiet=1)},
        suite_name: run_phase(
            suite_name,
            [sys.executable, "-m", "pytest", "-q", *tests],
            900 if args.full else 180, env),
        "health": run_phase(
            "health", [sys.executable, "main.py", "health"], 30, env),
    }
    blocking = (report["compile"], report[suite_name], report["health"])
    report["passed"] = all(bool(item.get("ok")) for item in blocking)
    audit = ROOT / "runtime" / "audit" / "quality_gate_latest.json"
    audit.parent.mkdir(parents=True, exist_ok=True)
    audit.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("QUALITY GATE: " + ("APROBADO" if report["passed"] else "NO APROBADO"))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
