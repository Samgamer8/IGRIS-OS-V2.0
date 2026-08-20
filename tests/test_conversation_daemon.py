"""Tests for ConversationDaemon facade (step 4 / N process separation)."""

from __future__ import annotations

import importlib
from unittest.mock import MagicMock, patch
from dataclasses import dataclass


# --- Mocks ---------------------------------------------------------------

@dataclass
class MockReply:
    ok: bool = True
    text: str = "mock response"
    model: str = "mock-model"
    tokens: int = 10


class MockAssistantService:
    """Minimal mock that satisfies ConversationDaemon._ensure_assistant."""

    def __init__(self):
        self.client = MagicMock()
        self.client.list_models.return_value = ["mock-model"]
        self.state = MagicMock()
        self.state.turns = []
        self.state.max_tool_rounds = 5
        self.sandbox = MagicMock()

    def respond(self, objective, context=()):
        return MockReply(ok=True, text=f"Response to: {objective}", model="mock-model", tokens=5)

    def respond_agentic(self, objective, context=()):
        self.state.turns.append(MagicMock(role="user", text=objective, tool_calls=[]))
        self.state.turns.append(MagicMock(role="assistant", text="agentic reply", tool_calls=[]))
        return MockReply(ok=True, text="agentic reply", model="mock-model", tokens=8)


class TestConversationDaemonImport:
    """Verify module imports cleanly with no side effects."""

    def test_import_creates_no_processes(self):
        """Import must not spawn subprocesses."""
        import subprocess as _sp
        _orig_popen = _sp.Popen
        spawned: list[str] = []
        def _track(*args, **kwargs):
            spawned.append(str(args[0] if args else "?"))
            return _orig_popen(*args, **kwargs)
        _sp.Popen = _track  # type: ignore[assignment]
        try:
            mod = importlib.import_module("igris_os.application.conversation_daemon")
            importlib.reload(mod)
            assert spawned == [], f"Import spawned: {spawned}"
        finally:
            _sp.Popen = _orig_popen  # type: ignore[assignment]

    def test_daemon_class_exists(self):
        from igris_os.application.conversation_daemon import ConversationDaemon
        assert ConversationDaemon is not None
        daemon = ConversationDaemon()
        for method in ("health", "chat", "chat_agentic", "state", "reset", "close"):
            assert hasattr(daemon, method), f"Missing method: {method}"


class TestConversationDaemonHealth:
    """health() must return a well-formed dict."""

    def test_health_without_assistant(self):
        from igris_os.application.conversation_daemon import ConversationDaemon
        daemon = ConversationDaemon()
        daemon._assistant_class = None  # type: ignore[assignment]
        result = daemon.health()
        assert result["ok"] is False
        assert "reason" in result
        daemon.close()

    def test_health_with_mock(self):
        from igris_os.application.conversation_daemon import ConversationDaemon
        daemon = ConversationDaemon()
        daemon._assistant_class = MockAssistantService  # type: ignore[assignment]
        result = daemon.health()
        assert result["ok"] is True
        assert result["latency_ms"] >= 0
        daemon.close()


class TestConversationDaemonChat:
    """chat() must return structured dict."""

    def test_chat_empty_returns_ok_false(self):
        from igris_os.application.conversation_daemon import ConversationDaemon
        daemon = ConversationDaemon()
        result = daemon.chat("")
        assert result["ok"] is False
        assert "reason" in result
        daemon.close()

    def test_chat_with_mock(self):
        from igris_os.application.conversation_daemon import ConversationDaemon
        daemon = ConversationDaemon()
        daemon._assistant_class = MockAssistantService  # type: ignore[assignment]
        result = daemon.chat("hola")
        assert result["ok"] is True
        assert "text" in result
        assert result["latency_ms"] >= 0
        daemon.close()

    def test_chat_agentic_with_mock(self):
        from igris_os.application.conversation_daemon import ConversationDaemon
        daemon = ConversationDaemon()
        daemon._assistant_class = MockAssistantService  # type: ignore[assignment]
        result = daemon.chat_agentic("di algo")
        assert result["ok"] is True
        assert "text" in result
        assert isinstance(result.get("tool_calls", []), list)
        daemon.close()


class TestConversationDaemonState:
    """state() and reset() must work."""

    def test_state_returns_dict(self):
        from igris_os.application.conversation_daemon import ConversationDaemon
        daemon = ConversationDaemon()
        daemon._assistant_class = MockAssistantService  # type: ignore[assignment]
        result = daemon.state()
        assert result["ok"] is True
        assert "turns" in result
        assert "tools_used" in result
        daemon.close()

    def test_reset_clears_state(self):
        from igris_os.application.conversation_daemon import ConversationDaemon
        daemon = ConversationDaemon()
        daemon._assistant_class = MockAssistantService  # type: ignore[assignment]
        result = daemon.reset()
        assert result["ok"] is True
        daemon.close()
