import json

from igris_os.bootstrap import build_igris
from igris_os.domain import Mission
from igris_os.files import RepositoryAnalyzer
from igris_os.retrieval import RepositoryContextStore


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


def test_repository_analyze_reports_granular_progress(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "app.py").write_text("class A:\n    pass\n", encoding="utf-8")
    events = []
    RepositoryAnalyzer(tmp_path / "workspace").analyze(
        root, "app", on_progress=lambda pct, msg: events.append((pct, msg)))
    assert events
    first = events[0][0]
    assert first >= 1
    assert all(pct <= 100 for pct, _ in events)
    assert events[-1][0] >= 95


def test_repository_analyze_indexes_semantic_context(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "core.py").write_text(
        "def execute_mission():\n    return 'misiones del sistema'\n",
        encoding="utf-8")
    (root / "ui.py").write_text(
        "def paint_background():\n    pass\n", encoding="utf-8")
    runtime = tmp_path / "runtime"
    kernel = build_igris(runtime)
    mission = Mission("analiza el proyecto")
    token = kernel.issue_approval(mission.objective, "repository.analyze")
    result = kernel.execute(
        mission, "repository.analyze",
        {"root": str(root), "query": "donde se ejecutan las misiones"},
        approval=token)
    assert result.ok
    records = result.data["repository"]["records"]
    assert any(item["path"] == "core.py" for item in records)
    store = RepositoryContextStore(runtime)
    store.remember(root, records)
    hits = store.retrieve("donde se ejecutan las misiones", limit=4)
    assert hits
    assert hits[0]["path"] == "core.py"
