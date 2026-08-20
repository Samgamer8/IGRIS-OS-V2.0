"""Tests for IgrisDaemon orchestrator (step 5 / N process separation)."""

from __future__ import annotations

import importlib
from unittest.mock import MagicMock


# --- Mock subsystems -----------------------------------------------------

class MockAIDaemon:
    def health(self):
        return {"ok": True, "engine": "mock-ai", "latency_ms": 0.1}

    def generate(self, prompt, model=""):
        return {"ok": True, "text": f"AI: {prompt[:50]}", "model": "mock", "tokens": 5, "latency_ms": 1.0}

    def close(self):
        pass


class MockVoiceDaemon:
    def health(self):
        return {"ok": True, "engine": "mock-voice", "voices": ["Pablo"], "latency_ms": 0.1}

    def speak(self, text, voice_name=None):
        return {"ok": True, "text": text[:50], "latency_ms": 0.5}

    def list_voices(self):
        return {"ok": True, "voices": ["Pablo"], "voice_count": 1, "latency_ms": 0.1}

    def close(self):
        pass


class MockMemoryDaemon:
    def __init__(self):
        self._memories: dict[str, list] = {}

    def health(self):
        return {"ok": True, "db_path": ":memory:", "total_bytes": 0, "latency_ms": 0.1}

    def remember(self, category, content, *, verified=False):
        self._memories.setdefault(category, []).append(content)
        return {"ok": True, "memory_id": len(self._memories[category]), "category": category, "latency_ms": 0.1}

    def recall(self, category, *, limit=20, verified_only=True):
        memories = self._memories.get(category, [])[:limit]
        return {"ok": True, "memories": [{"content": m} for m in memories], "count": len(memories), "category": category, "latency_ms": 0.1}

    def stats(self):
        return {"ok": True, "total_memories": sum(len(v) for v in self._memories.values()), "total_bytes": 0, "categories": {}, "latency_ms": 0.1}

    def close(self):
        pass


class MockConversationDaemon:
    def __init__(self):
        self._turns = 0

    def health(self):
        return {"ok": True, "engine": "mock-conv", "turns": self._turns, "latency_ms": 0.1}

    def chat(self, objective, context=()):
        self._turns += 1
        return {"ok": True, "text": f"Conv: {objective}", "model": "mock", "tokens": 5, "latency_ms": 1.0}

    def chat_agentic(self, objective, context=()):
        self._turns += 1
        return {"ok": True, "text": f"Agentic: {objective}", "model": "mock", "tokens": 8, "tool_calls": [], "latency_ms": 2.0}

    def state(self):
        return {"ok": True, "turns": self._turns, "tools_used": [], "max_tool_rounds": 5, "latency_ms": 0.1}

    def reset(self):
        self._turns = 0
        return {"ok": True, "latency_ms": 0.1}

    def close(self):
        pass


# --- Tests ---------------------------------------------------------------

class TestIgrisDaemonImport:
    """Verify module imports cleanly with no side effects."""

    def test_import_creates_no_subprocesses(self):
        import subprocess as _sp
        _orig = _sp.Popen
        spawned: list[str] = []
        def _track(*a, **kw):
            spawned.append(str(a[0] if a else "?"))
            return _orig(*a, **kw)
        _sp.Popen = _track  # type: ignore[assignment]
        try:
            mod = importlib.import_module("igris_os.core.igrisd")
            importlib.reload(mod)
            assert spawned == [], f"Import spawned: {spawned}"
        finally:
            _sp.Popen = _orig  # type: ignore[assignment]

    def test_daemon_class_exists(self):
        from igris_os.core.igrisd import IgrisDaemon
        d = IgrisDaemon()
        for method in ("health_all", "chat", "chat_agentic", "speak", "remember", "recall", "execute", "reset", "close"):
            assert hasattr(d, method), f"Missing: {method}"


class TestIgrisDaemonHealthAll:
    """health_all() aggregates subsystem health."""

    def test_health_all_with_mocks(self):
        from igris_os.core.igrisd import IgrisDaemon
        d = IgrisDaemon()
        d._ai_class = MockAIDaemon  # type: ignore[assignment]
        d._voice_class = MockVoiceDaemon  # type: ignore[assignment]
        d._memory_class = MockMemoryDaemon  # type: ignore[assignment]
        d._conversation_class = MockConversationDaemon  # type: ignore[assignment]
        result = d.health_all()
        assert result["ok"] is True
        assert result["healthy_count"] == 4
        assert result["total_count"] == 4
        assert all(result["subsystems"][k]["ok"] for k in ("ai", "voice", "memory", "conversation"))
        d.close()

    def test_health_all_partial_failure(self):
        """If one subsystem fails, overall ok=False but others still report."""
        from igris_os.core.igrisd import IgrisDaemon
        d = IgrisDaemon()
        d._ai_class = MockAIDaemon  # type: ignore[assignment]
        d._voice_class = None  # type: ignore[assignment]  # will fail
        d._memory_class = MockMemoryDaemon  # type: ignore[assignment]
        d._conversation_class = MockConversationDaemon  # type: ignore[assignment]
        result = d.health_all()
        assert result["ok"] is False  # voice failed
        assert result["healthy_count"] == 3
        assert result["subsystems"]["voice"]["ok"] is False
        assert result["subsystems"]["ai"]["ok"] is True
        d.close()


class TestIgrisDaemonRouting:
    """Verify requests route to the correct subsystem."""

    def test_chat_routes_to_conversation(self):
        from igris_os.core.igrisd import IgrisDaemon
        d = IgrisDaemon()
        d._conversation_class = MockConversationDaemon  # type: ignore[assignment]
        result = d.chat("hola")
        assert result["ok"] is True
        assert result["text"] == "Conv: hola"
        d.close()

    def test_chat_empty_returns_error(self):
        from igris_os.core.igrisd import IgrisDaemon
        d = IgrisDaemon()
        assert d.chat("")["ok"] is False
        assert d.chat("  ")["ok"] is False
        d.close()

    def test_speak_routes_to_voice(self):
        from igris_os.core.igrisd import IgrisDaemon
        d = IgrisDaemon()
        d._voice_class = MockVoiceDaemon  # type: ignore[assignment]
        result = d.speak("hola mundo")
        assert result["ok"] is True
        assert result["text"] == "hola mundo"
        d.close()

    def test_remember_routes_to_memory(self):
        from igris_os.core.igrisd import IgrisDaemon
        d = IgrisDaemon()
        d._memory_class = MockMemoryDaemon  # type: ignore[assignment]
        result = d.remember("fact", {"key": "value"})
        assert result["ok"] is True
        assert result["memory_id"] == 1
        d.close()

    def test_recall_routes_to_memory(self):
        from igris_os.core.igrisd import IgrisDaemon
        d = IgrisDaemon()
        mock_mem = MockMemoryDaemon()
        d._memory_class = lambda: mock_mem  # type: ignore[assignment]
        mock_mem.remember("fact", {"k": "v"})
        result = d.recall("fact")
        assert result["ok"] is True
        assert result["count"] == 1
        d.close()

    def test_execute_routes_to_ai(self):
        from igris_os.core.igrisd import IgrisDaemon
        d = IgrisDaemon()
        d._ai_class = MockAIDaemon  # type: ignore[assignment]
        result = d.execute("qué es Python?")
        assert result["ok"] is True
        assert "AI:" in result["text"]
        d.close()

    def test_reset_routes_to_conversation(self):
        from igris_os.core.igrisd import IgrisDaemon
        d = IgrisDaemon()
        d._conversation_class = MockConversationDaemon  # type: ignore[assignment]
        d.chat("primero")
        state1 = d.conversation_state()
        assert state1["turns"] >= 1
        d.reset()
        state2 = d.conversation_state()
        assert state2["turns"] == 0
        d.close()


class TestIgrisDaemonLifecycle:
    """close() releases all subsystems."""

    def test_close_resets_all(self):
        from igris_os.core.igrisd import IgrisDaemon
        d = IgrisDaemon()
        d._ai_class = MockAIDaemon  # type: ignore[assignment]
        d._voice_class = MockVoiceDaemon  # type: ignore[assignment]
        d._memory_class = MockMemoryDaemon  # type: ignore[assignment]
        d._conversation_class = MockConversationDaemon  # type: ignore[assignment]
        # Force instantiation
        d.health_all()
        assert d._ai is not None
        assert d._voice is not None
        d.close()
        assert d._ai is None
        assert d._voice is None
        assert d._memory is None
        assert d._conversation is None
