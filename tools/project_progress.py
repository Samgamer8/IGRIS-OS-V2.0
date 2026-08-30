from __future__ import annotations

import argparse
import json
from pathlib import Path

from igris_os.application.project_workspace import ProjectWorkspace


def main() -> int:
    parser = argparse.ArgumentParser(description="Consulta y ejecuta el progreso de proyectos IGRIS")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--project")
    parser.add_argument("--run-task", metavar="TASK_ID")
    args = parser.parse_args()
    workspace = ProjectWorkspace(args.root)
    if args.run_task:
        if not args.project:
            parser.error("--run-task necesita --project")
        task = workspace.run_task(args.project, args.run_task)
        print(json.dumps({"task": task.__dict__ if hasattr(task, "__dict__") else {
            "task_id": task.task_id, "title": task.title, "command": task.command,
            "status": task.status, "duration_seconds": task.duration_seconds,
            "output": task.output,
        }}, ensure_ascii=False, indent=2))
        return 0 if task.status == "passed" else 1
    print(json.dumps(workspace.report(args.project), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())