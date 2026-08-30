from __future__ import annotations

import json
import shlex
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True, slots=True)
class ProjectTask:
    task_id: str
    title: str
    command: tuple[str, ...] = ()
    status: str = "pending"
    duration_seconds: float = 0.0
    output: str = ""


class ProjectWorkspace:
    """Persiste proyectos, tareas y evidencia ejecutable en una carpeta controlada."""

    _ALLOWED_EXECUTABLES = frozenset({"python", "py", sys.executable.casefold()})

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self.projects = self.root / "proyectos"
        self.projects.mkdir(parents=True, exist_ok=True)

    def create_project(self, name: str, tasks: Iterable[str] = ()) -> Path:
        project = self.projects / self._safe_name(name)
        project.mkdir(parents=True, exist_ok=True)
        existing = self._read(project)
        if existing is None:
            data = {"name": project.name, "created_at": time.time(), "tasks": []}
        else:
            data = existing
        known = {item["title"] for item in data["tasks"]}
        for index, title in enumerate(tasks, start=len(data["tasks"]) + 1):
            clean = str(title).strip()
            if clean and clean not in known:
                data["tasks"].append(asdict(ProjectTask(f"task-{index:03d}", clean)))
                known.add(clean)
        self._write(project, data)
        return project

    def add_task(self, project: str, title: str, command: str = "") -> ProjectTask:
        path = self.create_project(project)
        data = self._read(path) or {"name": path.name, "created_at": time.time(), "tasks": []}
        task = ProjectTask(
            f"task-{len(data['tasks']) + 1:03d}", str(title).strip(),
            tuple(shlex.split(command)) if command.strip() else (),
        )
        if not task.title:
            raise ValueError("El titulo de la tarea no puede estar vacio")
        data["tasks"].append(asdict(task))
        self._write(path, data)
        return task

    def run_task(self, project: str, task_id: str, *, timeout: int = 120) -> ProjectTask:
        path = self.projects / self._safe_name(project)
        data = self._read(path)
        if data is None:
            raise FileNotFoundError("Proyecto no encontrado: " + project)
        tasks = data["tasks"]
        match = next((item for item in tasks if item["task_id"] == task_id), None)
        if match is None:
            raise KeyError("Tarea no encontrada: " + task_id)
        if not match["command"]:
            raise ValueError("La tarea no tiene comando ejecutable")
        executable = Path(match["command"][0]).name.casefold()
        if executable not in self._ALLOWED_EXECUTABLES:
            raise PermissionError("Ejecutable no permitido: " + executable)
        match["status"] = "running"
        self._write(path, data)
        started = time.monotonic()
        try:
            result = subprocess.run(
                list(match["command"]), cwd=path, capture_output=True, text=True,
                timeout=timeout, check=False,
            )
            match["status"] = "passed" if result.returncode == 0 else "failed"
            match["output"] = (result.stdout + result.stderr)[-4000:]
        except subprocess.TimeoutExpired as exc:
            match["status"] = "failed"
            match["output"] = f"timeout after {timeout}s: {exc}"
        finally:
            match["duration_seconds"] = round(time.monotonic() - started, 3)
            self._write(path, data)
        return ProjectTask(**match)

    def report(self, project: str | None = None) -> dict[str, object]:
        paths = [self.projects / self._safe_name(project)] if project else sorted(self.projects.iterdir())
        reports = []
        for path in paths:
            data = self._read(path)
            if data is not None:
                tasks = data["tasks"]
                reports.append({
                    "name": data["name"],
                    "created_at": data["created_at"],
                    "tasks": tasks,
                    "completed": sum(item["status"] == "passed" for item in tasks),
                    "total": len(tasks),
                })
        return {"projects_root": str(self.projects), "projects": reports}

    def _read(self, project: Path) -> dict[str, object] | None:
        target = project / "PROGRESS.json"
        return json.loads(target.read_text(encoding="utf-8")) if target.is_file() else None

    @staticmethod
    def _write(project: Path, data: dict[str, object]) -> None:
        (project / "PROGRESS.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _safe_name(value: str) -> str:
        name = "_".join(part for part in str(value).strip().split() if part)
        if not name or name in {".", ".."} or any(char in name for char in '\\/:*?"<>|'):
            raise ValueError("Nombre de proyecto no valido")
        return name[:80]
