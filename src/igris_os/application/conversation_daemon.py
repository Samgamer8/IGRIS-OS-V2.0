"""ConversationDaemon — facade for AssistantService (step 4 / N process separation).

Exposes the surface that any IPC boundary will need:

    health()                                    -> {ok, model, latency_ms}
    chat(objective, context)                    -> {ok, text, model, tokens, latency_ms}
    chat_agentic(objective, context)            -> {ok, text, model, tokens, tool_calls, latency_ms}
    state()                                     -> {ok, turns, tools_used}
    reset()                                     -> {ok}

No side-effects on import.  All methods return dicts (no raises).
"""

from __future__ import annotations

import time
import logging
from typing import Any

logger = logging.getLogger(__name__)


class ConversationDaemon:
    """Thin facade over AssistantService for eventual process isolation."""

    def __init__(self) -> None:
        self._assistant: Any = None
        self._assistant_class: Any = None
        self._model_router_class: Any = None
        # Lazy import — no side effects on module load
        try:
            from igris_os.application.assistant import AssistantService
            self._assistant_class = AssistantService
        except Exception as exc:
            logger.debug("AssistantService import deferred: %s", exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def health(self) -> dict[str, Any]:
        """Check conversation system readiness."""
        t0 = time.monotonic()
        try:
            assistant = self._ensure_assistant()
            # Check if LLM client is reachable
            client = getattr(assistant, "client", None)
            model_ok = False
            model_name = ""
            if client:
                try:
                    models = client.list_models() if hasattr(client, "list_models") else []
                    model_ok = bool(models)
                    model_name = models[0] if models else "unknown"
                except Exception:
                    pass
            latency = round((time.monotonic() - t0) * 1000, 1)
            return {
                "ok": True,
                "engine": "AssistantService",
                "model": model_name,
                "llm_available": model_ok,
                "turns": len(getattr(assistant.state, "turns", [])),
                "latency_ms": latency,
            }
        except Exception as exc:
            latency = round((time.monotonic() - t0) * 1000, 1)
            return {
                "ok": False,
                "reason": str(exc),
                "latency_ms": latency,
            }

    def chat(self, objective: str, context: tuple[str, ...] = ()) -> dict[str, Any]:
        """Single-turn chat response."""
        if not objective or not objective.strip():
            return {"ok": False, "reason": "empty objective", "latency_ms": 0}
        t0 = time.monotonic()
        try:
            assistant = self._ensure_assistant()
            reply = assistant.respond(objective.strip(), context)
            latency = round((time.monotonic() - t0) * 1000, 1)
            return {
                "ok": reply.ok,
                "text": reply.text,
                "model": reply.model,
                "tokens": reply.tokens,
                "latency_ms": latency,
            }
        except Exception as exc:
            latency = round((time.monotonic() - t0) * 1000, 1)
            return {
                "ok": False,
                "text": str(exc),
                "reason": str(exc),
                "latency_ms": latency,
            }

    def chat_agentic(self, objective: str, context: tuple[str, ...] = ()) -> dict[str, Any]:
        """Multi-turn agentic response with tool calls."""
        if not objective or not objective.strip():
            return {"ok": False, "reason": "empty objective", "latency_ms": 0}
        t0 = time.monotonic()
        try:
            assistant = self._ensure_assistant()
            reply = assistant.respond_agentic(objective.strip(), context)
            # Extract tool calls from conversation state
            tool_calls = []
            if assistant.state.turns:
                last_turn = assistant.state.turns[-1]
                if hasattr(last_turn, "tool_calls"):
                    tool_calls = [
                        {"tool": tc.tool_name, "ok": tc.ok}
                        for tc in last_turn.tool_calls
                    ]
            latency = round((time.monotonic() - t0) * 1000, 1)
            return {
                "ok": reply.ok,
                "text": reply.text,
                "model": reply.model,
                "tokens": reply.tokens,
                "tool_calls": tool_calls,
                "latency_ms": latency,
            }
        except Exception as exc:
            latency = round((time.monotonic() - t0) * 1000, 1)
            return {
                "ok": False,
                "text": str(exc),
                "reason": str(exc),
                "latency_ms": latency,
            }

    def state(self) -> dict[str, Any]:
        """Get current conversation state."""
        t0 = time.monotonic()
        try:
            assistant = self._ensure_assistant()
            turns = assistant.state.turns
            tools_used = set()
            for turn in turns:
                if hasattr(turn, "tool_calls"):
                    for tc in turn.tool_calls:
                        tools_used.add(tc.tool_name)
            latency = round((time.monotonic() - t0) * 1000, 1)
            return {
                "ok": True,
                "turns": len(turns),
                "tools_used": sorted(tools_used),
                "max_tool_rounds": getattr(assistant.state, "max_tool_rounds", 5),
                "latency_ms": latency,
            }
        except Exception as exc:
            latency = round((time.monotonic() - t0) * 1000, 1)
            return {
                "ok": False,
                "reason": str(exc),
                "latency_ms": latency,
            }

    def reset(self) -> dict[str, Any]:
        """Clear conversation history."""
        t0 = time.monotonic()
        try:
            assistant = self._ensure_assistant()
            assistant.state.turns.clear()
            latency = round((time.monotonic() - t0) * 1000, 1)
            return {"ok": True, "latency_ms": latency}
        except Exception as exc:
            latency = round((time.monotonic() - t0) * 1000, 1)
            return {"ok": False, "reason": str(exc), "latency_ms": latency}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _ensure_assistant(self) -> Any:
        """Lazy-instantiate AssistantService (no LLM call until first chat)."""
        if self._assistant is None:
            if self._assistant_class is None:
                raise RuntimeError("AssistantService not importable")
            self._assistant = self._assistant_class()
        return self._assistant

    def close(self) -> None:
        """Release conversation resources."""
        if self._assistant is not None:
            try:
                sandbox = getattr(self._assistant, "sandbox", None)
                if sandbox and hasattr(sandbox, "close"):
                    sandbox.close()
            except Exception:
                pass
            self._assistant = None
