"""Prueba reproducible de entregas reales de IGRIS OS."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from igris_os.application import ApprovalAuthority
from igris_os.delivery import DeliveryVerifier
from igris_os.delivery.verifier import EXECUTE_CAPABILITY


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--approve-execution", action="store_true",
                        help="Confirma la ejecución confinada de los proyectos")
    args = parser.parse_args(argv)
    if not args.approve_execution:
        print("PERMISO REQUERIDO: usa --approve-execution tras revisar los proyectos")
        return 2
    authority = ApprovalAuthority(ttl_seconds=120)
    verifier = DeliveryVerifier(authority)
    projects = ROOT / "benchmarks" / "real_projects"
    reports = []
    for name, kind in (("task_manager", "software"), ("tic_tac_toe", "game")):
        project = (projects / name).resolve()
        token = authority.issue(str(project), EXECUTE_CAPABILITY)
        report = verifier.verify_python(project, token, kind=kind)
        reports.append(asdict(report))
    payload = {"ok": all(report["ok"] for report in reports), "reports": reports}
    output = ROOT / "runtime" / "audit" / "v5_acceptance_latest.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
