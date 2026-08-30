from task_manager.cli import main
from task_manager.service import TaskService


def test_task_lifecycle(tmp_path, capsys):
    database = tmp_path / "tasks.json"
    assert main(["--db", str(database), "add", "Entregar V5"]) == 0
    assert main(["--db", str(database), "complete", "1"]) == 0
    tasks = TaskService(database).list()
    assert [(task.title, task.completed) for task in tasks] == [("Entregar V5", True)]
    assert "Completada #1" in capsys.readouterr().out


def test_rejects_empty_title(tmp_path):
    service = TaskService(tmp_path / "tasks.json")
    try:
        service.add("  ")
    except ValueError as exc:
        assert "vacío" in str(exc)
    else:
        raise AssertionError("Debió rechazar un título vacío")
