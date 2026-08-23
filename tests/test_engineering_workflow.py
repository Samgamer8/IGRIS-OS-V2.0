import sys

from igris_os.programming import EngineeringWorkflow


def test_workflow_requires_confirmation_before_execution(tmp_path):
    (tmp_path / "app.py").write_text("print('ok')\n", encoding="utf-8")

    result = EngineeringWorkflow().run(
        tmp_path, [sys.executable, "-c", "print('no')"])

    assert result.preflight.ok
    assert not result.executed
    assert result.reason == "Se necesita confirmacion"


def test_workflow_runs_allowed_command_in_sandbox(tmp_path):
    (tmp_path / "app.py").write_text("print('ok')\n", encoding="utf-8")
    result = EngineeringWorkflow().run(
        tmp_path, [sys.executable, "-c", "print('ok')"], confirmed=True)

    assert result.executed
    assert result.allowed
    assert result.run is not None
    assert result.run.returncode == 0
    assert result.run.stdout.strip() == "ok"


def test_workflow_rejects_unapproved_executable(tmp_path):
    (tmp_path / "app.py").write_text("print('ok')\n", encoding="utf-8")
    result = EngineeringWorkflow().run(
        tmp_path, ["cmd.exe", "/c", "echo", "no"], confirmed=True)

    assert not result.executed
    assert result.reason == "Ejecutable no permitido"