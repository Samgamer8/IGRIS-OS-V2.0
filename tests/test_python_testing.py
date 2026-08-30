from pathlib import Path

from igris_os.application.project_development import StagedProject
from igris_os.application.python_testing import PythonPytestVerifierAdapter


def _mission(root: Path):
    return type("Developed", (), {
        "staging": StagedProject(root, ("app.py", "test_app.py")),
    })()


def test_python_verifier_executes_real_passing_pytest(tmp_path):
    root = tmp_path / "staging"
    root.mkdir()
    (root / "app.py").write_text(
        "def add(a, b):\n    return a + b\n", encoding="utf-8")
    (root / "test_app.py").write_text(
        "from app import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8")

    evidence = PythonPytestVerifierAdapter(timeout=20).verify(_mission(root))

    assert evidence.executed
    assert evidence.passed
    assert evidence.command == ("python", "-m", "pytest", "-q")
    assert "passed" in evidence.summary


def test_python_verifier_reports_real_failure(tmp_path):
    root = tmp_path / "staging"
    root.mkdir()
    (root / "test_app.py").write_text(
        "def test_bad():\n    assert False\n", encoding="utf-8")

    evidence = PythonPytestVerifierAdapter(timeout=20).verify(_mission(root))

    assert evidence.executed
    assert not evidence.passed
    assert "failed" in evidence.summary


def test_python_verifier_does_not_execute_without_tests(tmp_path):
    root = tmp_path / "staging"
    root.mkdir()
    (root / "app.py").write_text("value = 1\n", encoding="utf-8")

    evidence = PythonPytestVerifierAdapter(timeout=20).verify(_mission(root))

    assert not evidence.executed
    assert not evidence.passed
    assert not evidence.command
