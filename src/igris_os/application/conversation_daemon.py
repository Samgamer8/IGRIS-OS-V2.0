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

from igris_os.ai.ollama import ModelReply

logger = logging.getLogger(__name__)


class _ProcessAIClient:
    """Adapt AIProcessRunner's dict contract to AssistantService's ModelReply."""

    def __init__(self, runner: Any) -> None:
        self._runner = runner

    def models(self) -> tuple[str, ...]:
        """Lista COMPLETA de modelos instalados via subprocess.

        Antes se derivaba de ``health().model`` (un solo modelo, el primero
        alfabetico), lo que hacia que el router creyera que solo existia
        p. ej. ``gemma4:26b`` y lo eligiera para chat general (~39s TTFT).
        """
        result = self._runner.models()
        models = result.get("models") if result.get("ok") else []
        return tuple(models or ())

    def list_models(self) -> list[str]:
        return list(self.models())

    def generate(self, prompt: str, model: str) -> ModelReply:
        options = {'model': model}
        limit = getattr(self._runner, 'output_token_limit', None)
        if limit is not None:
            options['output_limit'] = limit
        result = self._runner.generate(prompt, **options)
        return ModelReply(
            ok=bool(result.get("ok")),
            text=str(result.get("text") or ""),
            model=str(result.get("model") or model),
            error=str(result.get("error") or result.get("reason") or ""),
            backend=str(result.get("backend") or ""),
            reasoning=str(result.get("reasoning") or ""),
        )

    def generate_json(self, prompt: str, model: str, schema: dict) -> ModelReply:
        result = self._runner.generate_json(prompt, model=model, schema=schema)
        return ModelReply(
            ok=bool(result.get("ok")),
            text=str(result.get("text") or ""),
            model=str(result.get("model") or model),
            error=str(result.get("error") or result.get("reason") or ""),
            backend=str(result.get("backend") or ""),
            metadata=dict(result.get("metadata") or {}),
        )


class ConversationDaemon:
    """Thin facade over AssistantService for eventual process isolation."""

    def __init__(self, ai_runner: Any | None = None) -> None:
        self._assistant: Any = None
        self._assistant_class: Any = None
        self._ai_runner = ai_runner
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
                "backend": getattr(reply, "backend", ""),
                "reasoning": getattr(reply, "reasoning", ""),
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
                "backend": getattr(reply, "backend", ""),
                "reasoning": getattr(reply, "reasoning", ""),
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
            if self._ai_runner is not None:
                self._assistant = self._assistant_class(
                    client=_ProcessAIClient(self._ai_runner))
            else:
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
