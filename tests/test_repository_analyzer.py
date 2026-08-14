import json

from igris_os.files import RepositoryAnalyzer


def test_repository_map_extracts_structure_and_search(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "app.py").write_text(
        "import json\nclass MissionService:\n    def execute_mission(self): return True\n",
        encoding="utf-8")
    (root / "test_app.py").write_text(
        "from app import MissionService\ndef test_execute(): assert MissionService()\n",
        encoding="utf-8")
    (root / "web.js").write_text(
        "export function renderMission() { return true; }\n", encoding="utf-8")
    ignored = root / "node_modules"
    ignored.mkdir()
    (ignored / "huge.js").write_text("function ignore() {}", encoding="utf-8")
    report = RepositoryAnalyzer(tmp_path / "workspace").analyze(
        root, "donde se ejecuta mission")
    assert report.files == 3
    assert report.languages["python"] == 2
    assert any(item["name"] == "MissionService" for item in report.symbols)
    assert "test_app.py" in report.tests
    assert report.matches[0]["path"] == "app.py"
    manifest = json.loads(
        __import__("pathlib").Path(report.manifest).read_text(encoding="utf-8"))
    assert manifest["files"] == 3


def test_repository_limits_are_reported(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    for index in range(4):
        (root / f"{index}.py").write_text("value = 1", encoding="utf-8")
    report = RepositoryAnalyzer(
        tmp_path / "workspace", max_files=2).analyze(root)
    assert report.files == 2
    assert report.truncated
