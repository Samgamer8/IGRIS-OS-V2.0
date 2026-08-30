import argparse
import json
import shutil
import sys
from pathlib import Path

from igris_os.application import MissionDirector, RuntimeProbe
from igris_os.bootstrap import build_igris
from igris_os.domain import Mission
from igris_os.models import default_providers
from igris_os.storage.source_inventory import write_inventory


def _report_progress(percent: int, message: str) -> None:
    sys.stderr.write(f"\r[{percent:3d}%] {message}")
    sys.stderr.flush()


def _detect_language(objective: str) -> str:
    text = objective.lower()
    if any(word in text for word in ("python", "script", "api", "cli", "fastapi")):
        return "python"
    if any(word in text for word in ("javascript", "react", "node", "frontend", "web")):
        return "javascript"
    if any(word in text for word in ("java", "spring", "servlet")):
        return "java"
    if any(word in text for word in ("html", "css", "web")):
        return "web"
    return "python"


def _run_programming_mission(objective: str, *, approved: bool = False) -> int:
    if not approved:
        print(json.dumps({
            "ok": False, "code": "PERMISSION_REQUIRED",
            "message": "La generación ejecuta código y requiere --approve-execution",
        }, ensure_ascii=False, indent=2))
        return 2
    from pathlib import Path

    from igris_os.ai import OllamaClient
    from igris_os.programming.coordinator import AutonomousProgrammingCoordinator

    workspace = Path.cwd() / "workspace" / "generated" / "mission"
    workspace.mkdir(parents=True, exist_ok=True)
    target_dir = workspace / "output"
    shutil.rmtree(target_dir, ignore_errors=True)

    try:
        client = OllamaClient()
        coordinator = AutonomousProgrammingCoordinator(client, workspace)
        result = coordinator.execute(
            objective,
            confirmed=True,
            language=_detect_language(objective),
            on_progress=_report_progress,
        )
    except Exception as exc:
        print(json.dumps({"ok": False, "message": f"No se pudo arrancar la mision de programacion: {exc}"}, ensure_ascii=False, indent=2))
        return 1

    if not result.ok or result.proposal is None:
        print(json.dumps({
            "ok": False,
            "message": result.message if result else "Fallo en la mision de programacion",
            "plan": result.plan.plan if result and result.plan else "",
            "diagnostics": list(result.diagnostics) if result else [],
        }, ensure_ascii=False, indent=2))
        return 1

    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "solution.py").write_text(result.proposal.source, encoding="utf-8")
    (target_dir / "test_solution.py").write_text(result.proposal.tests, encoding="utf-8")
    (target_dir / "README.md").write_text(
        f"# Resultado generado\n\nObjetivo: {objective}\n\n{result.proposal.explanation}\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "ok": True,
        "message": result.message,
        "workspace": str(target_dir),
        "plan": result.plan.plan if result.plan else "",
        "review": {
            "approved": bool(result.review.approved) if result.review else False,
            "score": float(result.review.score) if result.review else 0.0,
            "issues": list(result.review.issues) if result.review else [],
        },
        "files": ["solution.py", "test_solution.py", "README.md"],
    }, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="igris", description="IGRIS OS")
    parser.add_argument("command", choices=("health", "capabilities", "plan",
                                            "providers", "inventory", "panel",
                                            "probe", "ai", "program", "create",
                                            "verify", "org"))
    parser.add_argument("value", nargs="?")
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--output", default="runtime/inventory/sources.json")
    parser.add_argument("--project", type=Path)
    parser.add_argument("--kind", choices=("software", "game"), default="software")
    parser.add_argument("--approve-execution", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "panel":
        from igris_os.ui import run_panel
        return run_panel()
    if args.command == "health":
        from igris_os.capabilities.system_health import health
        result = health({})
        print(json.dumps({"ok": result.ok, "message": result.message, **result.data},
                         ensure_ascii=False, indent=2))
        return 0 if result.ok else 1
    if args.command == "verify":
        if args.project is None:
            parser.error("verify necesita --project")
        if not args.approve_execution:
            print(json.dumps({
                "ok": False, "code": "PERMISSION_REQUIRED",
                "message": "Revisa el proyecto y repite con --approve-execution",
                "project": str(args.project.resolve()),
            }, ensure_ascii=False, indent=2))
            return 2
        from dataclasses import asdict
        from igris_os.application import ApprovalAuthority
        from igris_os.delivery import DeliveryVerifier
        from igris_os.delivery.verifier import EXECUTE_CAPABILITY
        project = args.project.resolve()
        authority = ApprovalAuthority(ttl_seconds=120)
        token = authority.issue(str(project), EXECUTE_CAPABILITY)
        verifier = DeliveryVerifier(authority)
        report = verifier.verify_python(
            project, token, kind=args.kind)
        evidence = project / "IGRIS_DELIVERY_REPORT.json"
        report.write(evidence)
        print(json.dumps({**asdict(report), "evidence": str(evidence)},
                         ensure_ascii=False, indent=2))
        return 0 if report.ok else 1
    kernel = build_igris()
    if args.command == "probe":
        probe = RuntimeProbe(Path.cwd())
        statuses = probe.probe()
        print(json.dumps({
            name: {"state": status.state, "path": status.path}
            for name, status in statuses.items()
        }, ensure_ascii=False, indent=2))
        return 0
    if args.command == "plan":
        if not args.value:
            parser.error("plan necesita un objetivo")
        plan = MissionDirector().plan(Mission(args.value))
        print(json.dumps({"mission_id": plan.mission_id, "branch": plan.branch.value,
                          "deliverables": plan.deliverables,
                          "acceptance_criteria": plan.acceptance_criteria,
                          "needs_clarification": plan.needs_clarification},
                         ensure_ascii=False, indent=2))
        return 0
    if args.command == "org":
        from igris_os.application import build_igris_org_chart

        chart = build_igris_org_chart()
        print(json.dumps({
            "ceo": chart.ceo,
            "director": chart.director,
            "mission": chart.mission,
            "control_rules": list(chart.control_rules),
            "escalation": chart.escalation,
            "units": [{
                "name": unit.name,
                "role": unit.role,
                "owner": unit.owner,
                "priority": unit.priority,
                "dependencies": list(unit.dependencies),
                "responsibilities": list(unit.responsibilities),
            } for unit in chart.units],
        }, ensure_ascii=False, indent=2))
        return 0
    if args.command == "providers":
        print(json.dumps([{"name": p.name, "kind": p.kind.value,
                           "endpoint": p.endpoint}
                          for p in default_providers().available()], indent=2))
        return 0
    if args.command in {"program", "create"}:
        if not args.value:
            parser.error("program necesita un objetivo")
        return _run_programming_mission(
            args.value, approved=args.approve_execution)
    if args.command == "inventory":
        if not args.source:
            parser.error("inventory necesita --source")
        result = write_inventory([Path(item) for item in args.source],
                                 Path(args.output),
                                 on_progress=_report_progress)
        sys.stderr.write("\n")
        print(json.dumps({"sources": len(result["sources"]),
                          "files": sum(s["file_count"] for s in result["sources"]),
                          "output": args.output}, ensure_ascii=False, indent=2))
        return 0
    if args.command == "capabilities":
        print(json.dumps([{"name": s.name, "risk": s.risk.value} for s in kernel.registry.specs()], indent=2))
        return 0
    if args.command == "ai":
        from igris_os.ai.server import OllamaServer, server_status
        action = args.value or "status"
        if action == "status":
            print(json.dumps(server_status(), ensure_ascii=False, indent=2))
            return 0 if server_status()["running"] else 1
        if action == "start":
            ok = OllamaServer().ensure_running()
            print(json.dumps({"running": ok, **server_status()},
                             ensure_ascii=False, indent=2))
            return 0 if ok else 1
        if action == "stop":
            server = OllamaServer()
            server.stop()
            print(json.dumps({"stopped": not server.is_running()},
                             ensure_ascii=False, indent=2))
            return 0
        parser.error(f"ai necesita status|start|stop, got {action}")
    result = kernel.execute(Mission("Comprobar estado local"), "system.health")
    print(json.dumps({"ok": result.ok, "message": result.message, **result.data}, ensure_ascii=False, indent=2))
    return 0 if result.ok else 1
