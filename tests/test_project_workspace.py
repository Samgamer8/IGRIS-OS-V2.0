import json
from pathlib import Path

import pytest

from igris_os.application.project_workspace import ProjectWorkspace


def test_creates_projects_and_persists_tasks(tmp_path: Path):
    workspace = ProjectWorkspace(tmp_path)
    project = workspace.create_project("demo", ["codigo", "pruebas"])

    data = json.loads((project / "PROGRESS.json").read_text(encoding="utf-8"))
    assert project == tmp_path / "proyectos" / "demo"
    assert [task["status"] for task in data["tasks"]] == ["pending", "pending"]


def test_runs_python_task_and_records_duration(tmp_path: Path):
    workspace = ProjectWorkspace(tmp_path)
    workspace.add_task("demo", "verificar", "python -c \"print('ok')\"")

    result = workspace.run_task("demo", "task-001")

    assert result.status == "passed"
    assert result.duration_seconds >= 0
    assert "ok" in result.output


def test_rejects_unapproved_executable(tmp_path: Path):
    workspace = ProjectWorkspace(tmp_path)
    workspace.add_task("demo", "peligrosa", "powershell -NoProfile")

    with pytest.raises(PermissionError):
        workspace.run_task("demo", "task-001")