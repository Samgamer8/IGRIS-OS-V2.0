from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(slots=True)
class Task:
    id: int
    title: str
    completed: bool = False


class TaskService:
    def __init__(self, database: Path) -> None:
        self.database = Path(database)

    def list(self) -> list[Task]:
        if not self.database.exists():
            return []
        data = json.loads(self.database.read_text(encoding="utf-8"))
        return [Task(**item) for item in data]

    def add(self, title: str) -> Task:
        clean = title.strip()
        if not clean:
            raise ValueError("El título no puede estar vacío")
        tasks = self.list()
        task = Task(max((item.id for item in tasks), default=0) + 1, clean)
        tasks.append(task)
        self._save(tasks)
        return task

    def complete(self, task_id: int) -> Task:
        tasks = self.list()
        for task in tasks:
            if task.id == task_id:
                task.completed = True
                self._save(tasks)
                return task
        raise KeyError(f"No existe la tarea {task_id}")

    def _save(self, tasks: list[Task]) -> None:
        self.database.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.database.with_suffix(self.database.suffix + ".tmp")
        temporary.write_text(json.dumps([asdict(task) for task in tasks],
                                        ensure_ascii=False, indent=2),
                             encoding="utf-8")
        temporary.replace(self.database)
