import pytest

from igris_os.memory import MemoryStore


def test_unverified_memory_is_silent(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    memory_id = store.remember("lesson", {"error": "x"})
    assert store.recall("lesson") == []
    store.verify(memory_id)
    assert store.recall("lesson")[0]["content"]["error"] == "x"


def test_empty_memory_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        MemoryStore(tmp_path / "memory.db").remember("", {})


def test_recent_memory_is_limited_and_verified(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    store.remember("chat", {"text": "oculto"})
    store.remember("chat", {"text": "uno"}, verified=True)
    store.remember("chat", {"text": "dos"}, verified=True)
    rows = store.recent("chat", limit=1)
    assert len(rows) == 1
    assert rows[0]["content"]["text"] == "dos"
