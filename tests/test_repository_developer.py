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
    assert not (tmp_path / "workspace" / "escape.py").exists()
