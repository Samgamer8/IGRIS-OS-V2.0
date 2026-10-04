import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
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
    import re
    text = objective.casefold()
    for language, pattern in (
        ("typescript", r"\b(typescript|tsx)\b"),
        ("javascript", r"\b(javascript|node|react)\b"),
        ("rust", r"\brust\b"),
        ("cpp", r"c\+\+|\bcpp\b"),
        ("java", r"\b(java|spring|servlet)\b"),
        ("go", r"\b(golang|go)\b"),
        ("python", r"\b(python|fastapi)\b"),
        ("web", r"\b(html|css|web|frontend)\b"),
    ):
        if re.search(pattern, text):
            return language
    return "python"


def _run_programming_mission(objective: str, *, approved: bool = False) -> int:
    if not approved:
        print(json.dumps({
            "ok": False, "code": "PERMISSION_REQUIRED",
            "message": "La generación ejecuta código y requiere --approve-execution",
        }, ensure_ascii=False, indent=2))
        return 2
    try:
        kernel = build_igris()
        mission = Mission(objective)
        capability = "programming.mission"
        from igris_os.application.programming_intent import is_improvement_request
        token = kernel.issue_approval(mission.objective, capability)
        result = kernel.execute(
            mission, capability,
            {"objective": objective, "requires_existing": is_improvement_request(objective)},
            approval=token, on_progress=_report_progress)
    except Exception as exc:
        print(json.dumps({"ok": False, "message": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"ok": result.ok, "code": result.code, "message": result.message,
                      **result.data}, ensure_ascii=False, indent=2))
    return 0 if result.ok else 1


def _run_debate(topic: str | None, *, max_turns: int | None,
                stop_file: Path | None, log_output: Path | None) -> int:
    from igris_os.ai.ollama import OllamaClient
    from igris_os.evolution.dual_debate import DualDebateSession

    default_topic = (
        "Disenar una interfaz eficiente y de programacion rapida, con "
        "todas sus funciones, para IGRIS OS en Windows 11, considerando "
        "las caracteristicas de este PC.")
    final_topic = topic or default_topic
    runtime = Path("runtime")
    stop_file = stop_file or (runtime / "debate.stop")
    log_path = log_output or (
        runtime / "debates" /
        f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_debate.jsonl")
    if stop_file.exists():
        stop_file.unlink()
    session = DualDebateSession(OllamaClient(), final_topic, log_path=log_path)

    def should_stop() -> bool:
        if stop_file.exists():
            stop_file.unlink(missing_ok=True)
            return True
        return False

    print(f"Debate iniciado sobre: {final_topic}", file=sys.stderr)
    print(f"Transcripcion en vivo: {log_path}", file=sys.stderr)
    print(f"Para detenerlo: crea el archivo {stop_file} o pulsa Ctrl+C",
          file=sys.stderr)
    try:
        session.run(should_stop, max_turns=max_turns)
    except KeyboardInterrupt:
        print("\nDebate interrumpido por el usuario.", file=sys.stderr)
    markdown_path = log_path.with_suffix(".md")
    markdown_path.write_text(session.render_markdown(), encoding="utf-8")
    print(json.dumps({
        "ok": True, "turns": len(session.turns),
        "log": str(log_path), "transcript": str(markdown_path),
    }, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="igris", description="IGRIS OS")
    parser.add_argument("command", choices=("health", "capabilities", "plan",
                                            "providers", "inventory", "panel",
                                            "probe", "ai", "program", "create",
                                            "verify", "org", "work", "work-deliver",
                                            "debate"))
    parser.add_argument("value", nargs="?")
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--output", default="runtime/inventory/sources.json")
    parser.add_argument("--project", type=Path)
    parser.add_argument("--kind", choices=("software", "game"), default="software")
    parser.add_argument("--approve-execution", action="store_true")
    parser.add_argument("--allow-downloads", action="store_true")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--answer", action="append", default=[])
    parser.add_argument("--resume-report", type=Path)
    parser.add_argument("--max-turns", type=int, default=None)
    parser.add_argument("--stop-file", type=Path, default=None)
    parser.add_argument("--log", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.command == "debate":
        return _run_debate(args.value, max_turns=args.max_turns,
                           stop_file=args.stop_file, log_output=args.log)
    if args.command in {'work', 'work-deliver'}:
        if not args.approve_execution:
            print(json.dumps({'ok': False, 'code': 'PERMISSION_REQUIRED',
                'message': 'Este encargo requiere --approve-execution'}, ensure_ascii=False))
            return 2
        if args.command == 'work' and not args.value:
            parser.error('work necesita un encargo')
        if args.command == 'work-deliver' and not args.report:
            parser.error('work-deliver necesita --report')
        objective = args.value or 'Entregar el resultado programado'
        capability = 'programming.mission' if args.command == 'work' else 'programming.deliver'
        payload = {'objective': objective, 'root': str(args.project.resolve()) if args.project else '',
            'report': str(args.report.resolve()) if args.report else '',
            'resume_report': str(args.resume_report.resolve()) if args.resume_report else '',
            'destination': str(args.destination.resolve()) if args.destination else '',
            'clarifications': args.answer, 'allow_downloads': args.allow_downloads,
            'user_accepted': False}
        if args.command == 'work':
            from igris_os.application.programming_intent import is_improvement_request
            payload['requires_existing'] = is_improvement_request(objective)
        kernel = build_igris()
        token = kernel.issue_approval(objective, capability)
        result = kernel.execute(Mission(objective), capability, payload,
                                approval=token, on_progress=_report_progress)
        print(json.dumps({'ok': result.ok, 'code': result.code, 'message': result.message,
                          **result.data}, ensure_ascii=False, indent=2))
        return 0 if result.ok else 1
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
