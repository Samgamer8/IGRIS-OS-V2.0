import json
from pathlib import Path

from igris_os.ai import ModelReply
from igris_os.programming import RepositoryDeveloper


class FakeClient:
    def __init__(self, package):
        self.package = package

    def generate(self, prompt, model):
        return ModelReply(True, json.dumps(self.package), model)


def _source(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    (root / "app.py").write_text(
        "def add(a, b):\n    return a + b\n", encoding="utf-8")
    return root


def test_repository_changes_only_isolated_copy(tmp_path):
    source = _source(tmp_path)
    package = {"summary": "añadida resta", "changes": [{
        "path": "app.py",
        "content": "def add(a, b):\n    return a + b\n\ndef sub(a, b):\n    return a - b\n"}]}
    result = RepositoryDeveloper(
        FakeClient(package), tmp_path / "workspace", "coder").propose(
            source, "añade resta", confirmed=True)
    assert result.ok
    assert "def sub" not in (source / "app.py").read_text(encoding="utf-8")
    assert "def sub" in (Path(result.staged_root) / "app.py").read_text(
        encoding="utf-8")
    assert "+++ b/app.py" in Path(result.report).read_text(encoding="utf-8")


def test_invalid_change_rolls_back_staged_file(tmp_path):
    source = _source(tmp_path)
    package = {"changes": [{"path": "app.py", "content": "def broken(:"}]}
    result = RepositoryDeveloper(
        FakeClient(package), tmp_path / "workspace", "coder").propose(
            source, "rompe", confirmed=True)
    assert not result.ok
    assert (Path(result.staged_root) / "app.py").read_text(
        encoding="utf-8").startswith("def add")


def test_path_escape_is_rejected(tmp_path):
    source = _source(tmp_path)
    package = {"changes": [{"path": "../escape.py", "content": "value=1"}]}
    result = RepositoryDeveloper(
        FakeClient(package), tmp_path / "workspace", "coder").propose(
            source, "escape", confirmed=True)
    assert not result.ok


def test_repository_developer_blocks_critical_preflight(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "broken.py").write_text("def broken(:\n", encoding="utf-8")

    result = RepositoryDeveloper(
        FakeClient({}), tmp_path / "workspace", "fake").propose(
        source, "corrige el proyecto", confirmed=True)

    assert not result.ok
    assert result.diagnostics == ("preflight_critical",)
    assert "Preflight bloqueado" in result.message
    assert not (tmp_path / "workspace" / "escape.py").exists()


def test_verify_staged_runs_tests_in_sandbox(tmp_path):
    root = tmp_path / "staged"
    root.mkdir()
    (root / "app.py").write_text("value = 2\n", encoding="utf-8")
    (root / "test_app.py").write_text(
        "def test_value():\n    assert 2 == 2\n", encoding="utf-8")

    result = RepositoryDeveloper(
        FakeClient({}), tmp_path / "workspace", "fake").verify_staged(root)

    assert result.ok
    assert result.diagnostics == ("tests_passed",)
    assert (root / "verification_report.txt").is_file()


def test_verify_staged_rejects_failing_tests(tmp_path):
    root = tmp_path / "staged"
    root.mkdir()
    (root / "test_app.py").write_text(
        "def test_failure():\n    assert False\n", encoding="utf-8")

    result = RepositoryDeveloper(
        FakeClient({}), tmp_path / "workspace", "fake").verify_staged(root)

    assert not result.ok
    assert result.diagnostics == ("tests_failed",)


def test_repair_until_verified_rolls_back_unverified_change(tmp_path):
    root = tmp_path / "staged"
    root.mkdir()
    source = root / "app.py"
    source.write_text("value = 1\n", encoding="utf-8")
    (root / "test_app.py").write_text(
        "def test_value():\n    assert False\n", encoding="utf-8")

    result = RepositoryDeveloper(
        FakeClient({}), tmp_path / "workspace", "fake").repair_until_verified(
        root, "corrige el test", "assertion fallida", max_attempts=1)

    assert not result.ok
    assert result.diagnostics[0] == "rollback"
    assert source.read_text(encoding="utf-8") == "value = 1\n"


def test_repair_until_verified_accepts_passing_fix(tmp_path):
    root = tmp_path / "staged"
    root.mkdir()
    (root / "app.py").write_text("value = 1\n", encoding="utf-8")
    (root / "test_app.py").write_text(
        "def test_value():\n    assert False\n", encoding="utf-8")

    class RepairClient:
        def generate(self, prompt, model):
            return ModelReply(True, json.dumps({
                "path": "test_app.py",
                "content": "def test_value():\n    assert True\n",
            }), model)

    result = RepositoryDeveloper(
        RepairClient(), tmp_path / "workspace", "fake").repair_until_verified(
        root, "corrige el test", "assertion fallida", max_attempts=1)

    assert result.ok
    assert result.diagnostics == ("tests_passed",)
