from __future__ import annotations

import argparse
from pathlib import Path

from .service import TaskService


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Gestor de tareas IGRIS")
    root.add_argument("--db", type=Path, default=Path("tasks.json"))
    commands = root.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add")
    add.add_argument("title")
    commands.add_parser("list")
    complete = commands.add_parser("complete")
    complete.add_argument("id", type=int)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    service = TaskService(args.db)
    if args.command == "add":
        task = service.add(args.title)
        print(f"Creada #{task.id}: {task.title}")
    elif args.command == "complete":
        task = service.complete(args.id)
        print(f"Completada #{task.id}: {task.title}")
    else:
        for task in service.list():
            print(f"[{'x' if task.completed else ' '}] {task.id}: {task.title}")
    return 0
