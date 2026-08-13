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
