from igris_os.retrieval import RepositoryContextStore


def _sample_records():
    return [
        {"path": "src/core.py", "symbols": ["execute_mission"],
         "text": "def execute_mission(): ejecuta las misiones del sistema"},
        {"path": "README.md", "symbols": [], "text": "instrucciones de instalacion"},
    ]


def test_retrieve_empty_when_no_index(tmp_path):
    store = RepositoryContextStore(tmp_path)
    assert store.retrieve("ejecuta misiones") == []


def test_remember_and_retrieve_semantically(tmp_path):
    store = RepositoryContextStore(tmp_path)
    store.remember(tmp_path / "repo", _sample_records())
    hits = store.retrieve("ejecuta misiones del sistema")
    assert hits
    assert hits[0]["path"] == "src/core.py"
    assert "ejecuta" in hits[0]["excerpt"]


def test_retrieve_ranks_relevant_higher(tmp_path):
    store = RepositoryContextStore(tmp_path)
    store.remember(tmp_path / "repo", _sample_records())
    hits = store.retrieve("instrucciones de instalacion del producto")
    assert hits[0]["path"] == "README.md"


def test_retrieve_caps_results(tmp_path):
    store = RepositoryContextStore(tmp_path)
    records = [{"path": f"f{i}.py", "symbols": [], "text": "pruebas"} for i in range(20)]
    store.remember(tmp_path / "repo", records)
    assert len(store.retrieve("pruebas", limit=5)) <= 5


def test_retrieve_tolerates_corrupt_index(tmp_path):
    store = RepositoryContextStore(tmp_path)
    store.index_path.write_text("{not json", encoding="utf-8")
    assert store.retrieve("cualquier cosa") == []
