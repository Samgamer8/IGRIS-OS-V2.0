import argparse
import json
from pathlib import Path

from igris_os.application import MissionDirector
from igris_os.bootstrap import build_igris
from igris_os.domain import Mission
from igris_os.models import default_providers
from igris_os.storage.source_inventory import write_inventory


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="igris", description="IGRIS OS V2.O")
    parser.add_argument("command", choices=("health", "capabilities", "plan",
                                            "providers", "inventory", "panel"))
    parser.add_argument("value", nargs="?")
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--output", default="runtime/inventory/sources.json")
    args = parser.parse_args(argv)
    kernel = build_igris()
    if args.command == "panel":
        from igris_os.ui import run_panel
        return run_panel()
    if args.command == "plan":
        if not args.value:
            parser.error("plan necesita un objetivo")
        plan = MissionDirector().plan(Mission(args.value))
        print(json.dumps({"mission_id": plan.mission_id, "branch": plan.branch.value,
                          "steps": plan.steps, "acceptance": plan.acceptance,
                          "needs_clarification": plan.needs_clarification},
                         ensure_ascii=False, indent=2))
        return 0
    if args.command == "providers":
        print(json.dumps([{"name": p.name, "kind": p.kind.value,
                           "endpoint": p.endpoint}
                          for p in default_providers().available()], indent=2))
        return 0
    if args.command == "inventory":
        if not args.source:
            parser.error("inventory necesita --source")
        result = write_inventory([Path(item) for item in args.source], Path(args.output))
        print(json.dumps({"sources": len(result["sources"]),
                          "files": sum(s["file_count"] for s in result["sources"]),
                          "output": args.output}, ensure_ascii=False, indent=2))
        return 0
    if args.command == "capabilities":
        print(json.dumps([{"name": s.name, "risk": s.risk.value} for s in kernel.registry.specs()], indent=2))
        return 0
    result = kernel.execute(Mission("Comprobar estado local"), "system.health")
    print(json.dumps({"ok": result.ok, "message": result.message, **result.data}, ensure_ascii=False, indent=2))
    return 0 if result.ok else 1
