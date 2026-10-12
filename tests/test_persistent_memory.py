"""Tests de la memoria persistente (journal + hechos a largo plazo)."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from igris_os.memory.persistent import (
    ConversationJournal, LongTermMemory, PersistentMemory,
)


def test_journal_roundtrip_and_order():
    with tempfile.TemporaryDirectory() as td:
        journal = ConversationJournal(Path(td) / "j.jsonl")
        journal.append("user", "hola")
        journal.append("assistant", "que tal")
        entries = journal.load()
        assert [e["role"] for e in entries] == ["user", "assistant"]
        assert entries[0]["text"] == "hola"
        assert journal.count() == 2


def test_journal_load_limit_and_clear():
    with tempfile.TemporaryDirectory() as td:
        journal = ConversationJournal(Path(td) / "j.jsonl")
        for i in range(10):
            journal.append("user", f"mensaje {i}")
        assert len(journal.load(limit=3)) == 3
        assert journal.load(limit=3)[0]["text"] == "mensaje 7"
        journal.clear()
        assert journal.count() == 0
        assert journal.load() == []


def test_journal_normalizes_newlines():
    with tempfile.TemporaryDirectory() as td:
        journal = ConversationJournal(Path(td) / "j.jsonl")
        journal.append("user", "linea1\n\n   linea2   ")
        assert journal.load()[0]["text"] == "linea1 linea2"


def test_long_term_remember_and_dedup():
    with tempfile.TemporaryDirectory() as td:
        mem = LongTermMemory(Path(td) / "f.jsonl")
        assert mem.remember("uso una RTX 5060 Ti") is True
        assert mem.remember("uso una rtx 5060 ti") is False  # dup case-insensitive
        assert mem.count() == 1
        assert mem.recall()[0].text == "uso una RTX 5060 Ti"


def test_long_term_recall_limit_and_forget():
    with tempfile.TemporaryDirectory() as td:
        mem = LongTermMemory(Path(td) / "f.jsonl")
        for i in range(5):
            mem.remember(f"hecho {i}")
        assert len(mem.recall(limit=2)) == 2
        assert mem.recall(limit=2)[0].text == "hecho 4"  # mas reciente primero
        assert mem.forget("hecho 3") == 1
        assert mem.forget("no existe") == 0
        assert mem.count() == 4


def test_long_term_rejects_empty_and_truncates():
    with tempfile.TemporaryDirectory() as td:
        mem = LongTermMemory(Path(td) / "f.jsonl")
        assert mem.remember("   ") is False
        huge = "x" * 5000
        mem.remember(huge)
        assert len(mem.recall()[0].text) == 280


def test_persistent_facade_together():
    with tempfile.TemporaryDirectory() as td:
        mem = PersistentMemory(Path(td) / "mem")
        mem.log_turn("user", "guardame esto")
        mem.remember("prefiero respuestas en espanol", created_at="2026-12-10")
        assert mem.recent_history()[0]["text"] == "guardame esto"
        assert mem.recall()[0].text == "prefiero respuestas en espanol"
        assert mem.recall()[0].created_at == "2026-12-10"
        mem.clear()
        assert mem.recent_history() == []
        assert mem.recall() == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
