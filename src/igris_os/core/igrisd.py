"""IgrisDaemon — central orchestrator for IGRIS OS (step 5 / N process separation).

Routes requests to the 4 subsystem facades:

    igris-ai            → AIDaemon (LLM communication)
    igris-voice         → VoiceDaemon (TTS/STT)
    igris-memory        → MemoryDaemon (persistent storage)
    igris-conversation  → ConversationDaemon (multi-turn chat + tools)

Unified API:

    health_all()                         → {ok, subsystems: {ai, voice, memory, conversation}}
    chat(objective)                      → routes to conversation or ai depending on complexity
    speak(text)                          → routes to voice
    remember(category, content)          → routes to memory
    recall(category)                     → routes to memory
    execute(prompt)                      → routes to ai (single LLM call)
    reset()                              → resets conversation state
    close()                              → releases all subsystems

Contract boundary (step 2 / N):

    handle(Request) -> Response           → accepts contract requests, returns
                                             contract responses, emits Events
    set_event_sink(on_event)              → subscribes to lifecycle Events

The internal routing methods above are unchanged; ``handle`` is a thin
contract layer over them.

No side-effects on import.  All methods return dicts (no raises).
"""

from __future__ import annotations

import time
import logging
from dataclasses import replace
from typing import Any, Callable

from igris_os.core.contracts import (
    ErrorCode,
    Event,
    EventType,
    Request,
    Response,
    response_from_payload,
)

logger = logging.getLogger(__name__)


# Ruta contractual → operación interna existente.  Cada adaptador lee los
# kwargs del payload y delega en el método del orquestador sin tocarlo.
_ROUTES: dict[str, Callable[[Any, dict[str, Any]], dict[str, Any]]] = {
    "chat": lambda self, p: self.chat(
        p.get("objective", ""), tuple(p.get("context") or ())),
    "chat_agentic": lambda self, p: self.chat_agentic(
        p.get("objective", ""), tuple(p.get("context") or ())),
    "speak": lambda self, p: self.speak(p.get("text", ""), p.get("voice_name")),
    "list_voices": lambda self, p: self.list_voices(),
    "remember": lambda self, p: self.remember(
        p.get("category", ""), p.get("content") or {},
        verified=bool(p.get("verified", False))),
    "recall": lambda self, p: self.recall(
        p.get("category", ""), limit=int(p.get("limit", 20))),
    "memory_stats": lambda self, p: self.memory_stats(),
    "execute": lambda self, p: self.execute(
        p.get("prompt", ""), model=p.get("model", "")),
    "conversation_state": lambda self, p: self.conversation_state(),
    "reset": lambda self, p: self.reset(),
    "health_all": lambda self, p: self.health_all(),
}


class IgrisDaemon:
    """Central orchestrator — the conductor of the IGRIS orchestra."""

    def __init__(
        self,
        ai_runner: Any | None = None,
        on_event: Callable[[Event], None] | None = None,
    ) -> None:
        self._ai: Any = None
        self._ai_runner: Any = ai_runner  # optional AIProcessRunner for subprocess AI
        self._voice: Any = None
        self._memory: Any = None
        self._conversation: Any = None
        self._event_sink: Callable[[Event], None] | None = on_event

        # Lazy import classes — no side effects on module load
        self._ai_class: type | None = None
        self._voice_class: type | None = None
        self._memory_class: type | None = None
        self._conversation_class: type | None = None

        try:
            from igris_os.ai.daemon import AIDaemon
            self._ai_class = AIDaemon
        except Exception as exc:
            logger.debug("AIDaemon import deferred: %s", exc)

        try:
            from igris_os.voice.daemon import VoiceDaemon
            self._voice_class = VoiceDaemon
        except Exception as exc:
            logger.debug("VoiceDaemon import deferred: %s", exc)

        try:
            from igris_os.memory.daemon import MemoryDaemon
            self._memory_class = MemoryDaemon
        except Exception as exc:
            logger.debug("MemoryDaemon import deferred: %s", exc)

        try:
            from igris_os.application.conversation_daemon import ConversationDaemon
            self._conversation_class = ConversationDaemon
        except Exception as exc:
            logger.debug("ConversationDaemon import deferred: %s", exc)

    # ------------------------------------------------------------------
    # Unified health
    # ------------------------------------------------------------------

    def health_all(self) -> dict[str, Any]:
        """Health check for all subsystems."""
        t0 = time.monotonic()
        subsystems: dict[str, dict] = {}

        # AI
        try:
            ai = self._ensure_ai()
            subsystems["ai"] = ai.health()
        except Exception as exc:
            subsystems["ai"] = {"ok": False, "reason": str(exc)}

        # Voice
        try:
            voice = self._ensure_voice()
            subsystems["voice"] = voice.health()
        except Exception as exc:
            subsystems["voice"] = {"ok": False, "reason": str(exc)}

        # Memory
        try:
            memory = self._ensure_memory()
            subsystems["memory"] = memory.health()
        except Exception as exc:
            subsystems["memory"] = {"ok": False, "reason": str(exc)}

        # Conversation
        try:
            conv = self._ensure_conversation()
            subsystems["conversation"] = conv.health()
        except Exception as exc:
            subsystems["conversation"] = {"ok": False, "reason": str(exc)}

        all_ok = all(s.get("ok", False) for s in subsystems.values())
        latency = round((time.monotonic() - t0) * 1000, 1)

        return {
            "ok": all_ok,
            "subsystems": subsystems,
            "healthy_count": sum(1 for s in subsystems.values() if s.get("ok")),
            "total_count": len(subsystems),
            "latency_ms": latency,
        }

    # ------------------------------------------------------------------
    # Contract boundary (step 2 / N)
    # ------------------------------------------------------------------

    def handle(self, request: Request) -> Response:
        """Frontera contractual: procesa un ``Request`` y devuelve un ``Response``.

        Emite ``Event`` de ciclo de vida (RECEIVED → COMPLETED/FAILED) al
        sumidero configurado.  No cambia la lógica interna de los daemons:
        normaliza entrada y salida a los contratos del núcleo.
        """
        if not isinstance(request, Request):
            return Response.error_response(
                ErrorCode.BAD_REQUEST,
                "handle espera un Request contractual",
            )

        t0 = time.monotonic()
        self._emit(EventType.RECEIVED, request, {"method": request.method})

        route = _ROUTES.get(request.method)
        if route is None:
            self._emit(EventType.FAILED, request, {
                "method": request.method,
                "error": f"método no soportado: {request.method}",
            })
            return Response.error_response(
                ErrorCode.BAD_REQUEST,
                f"método no soportado: {request.method}",
                request_id=request.id,
            )

        try:
            raw = route(self, request.payload)
            latency_ms = round((time.monotonic() - t0) * 1000, 1)
            response = replace(
                response_from_payload(raw, request_id=request.id),
                latency_ms=latency_ms,
            )
            self._emit(
                EventType.COMPLETED if response.ok else EventType.FAILED,
                request,
                {
                    "method": request.method,
                    "latency_ms": latency_ms,
                    "error": None if response.error is None
                    else response.error.to_dict(),
                },
            )
            return response
        except Exception as exc:
            latency_ms = round((time.monotonic() - t0) * 1000, 1)
            self._emit(EventType.FAILED, request, {
                "method": request.method,
                "latency_ms": latency_ms,
                "error": str(exc),
            })
            return Response.error_response(
                ErrorCode.INTERNAL, str(exc), request_id=request.id)

    def set_event_sink(self, on_event: Callable[[Event], None] | None) -> None:
        """Sustituye (o elimina) el sumidero de eventos del orquestador."""
        self._event_sink = on_event

    def _emit(self, etype: EventType, request: Request,
              payload: dict[str, Any]) -> None:
        """Emite un Event si hay sumidero configurado; nunca lanza."""
        if self._event_sink is None:
            return
        try:
            self._event_sink(Event(
                type=etype,
                job_id=request.id,
                trace_id=request.trace_id,
                payload=payload,
            ))
        except Exception:
            logger.debug("event sink falló; se ignora", exc_info=True)

    # ------------------------------------------------------------------
    # Conversation routing
    # ------------------------------------------------------------------

    def chat(self, objective: str, context: tuple[str, ...] = ()) -> dict[str, Any]:
        """Route a chat message. Uses conversation daemon for multi-turn."""
        if not objective or not objective.strip():
            return {"ok": False, "reason": "empty objective", "latency_ms": 0}
        try:
            conv = self._ensure_conversation()
            return conv.chat(objective.strip(), context)
        except Exception as exc:
            return {"ok": False, "reason": str(exc), "latency_ms": 0}

    def chat_agentic(self, objective: str, context: tuple[str, ...] = ()) -> dict[str, Any]:
        """Route an agentic chat with tool calls."""
        if not objective or not objective.strip():
            return {"ok": False, "reason": "empty objective", "latency_ms": 0}
        try:
            conv = self._ensure_conversation()
            return conv.chat_agentic(objective.strip(), context)
        except Exception as exc:
            return {"ok": False, "reason": str(exc), "latency_ms": 0}

    # ------------------------------------------------------------------
    # Voice routing
    # ------------------------------------------------------------------

    def speak(self, text: str, voice_name: str | None = None) -> dict[str, Any]:
        """Route TTS request to voice daemon."""
        if not text or not text.strip():
            return {"ok": False, "reason": "empty text", "latency_ms": 0}
        try:
            voice = self._ensure_voice()
            return voice.speak(text, voice_name)
        except Exception as exc:
            return {"ok": False, "reason": str(exc), "latency_ms": 0}

    def list_voices(self) -> dict[str, Any]:
        """List available TTS voices."""
        try:
            voice = self._ensure_voice()
            return voice.list_voices()
        except Exception as exc:
            return {"ok": False, "reason": str(exc), "latency_ms": 0}

    # ------------------------------------------------------------------
    # Memory routing
    # ------------------------------------------------------------------

    def remember(self, category: str, content: dict, *, verified: bool = False) -> dict[str, Any]:
        """Store a memory."""
        if not category or not category.strip():
            return {"ok": False, "reason": "empty category", "latency_ms": 0}
        if not content:
            return {"ok": False, "reason": "empty content", "latency_ms": 0}
        try:
            memory = self._ensure_memory()
            return memory.remember(category, content, verified=verified)
        except Exception as exc:
            return {"ok": False, "reason": str(exc), "latency_ms": 0}

    def recall(self, category: str, *, limit: int = 20) -> dict[str, Any]:
        """Recall memories from a category."""
        if not category or not category.strip():
            return {"ok": False, "reason": "empty category", "latency_ms": 0}
        try:
            memory = self._ensure_memory()
            return memory.recall(category, limit=limit)
        except Exception as exc:
            return {"ok": False, "reason": str(exc), "latency_ms": 0}

    def memory_stats(self) -> dict[str, Any]:
        """Get memory store statistics."""
        try:
            memory = self._ensure_memory()
            return memory.stats()
        except Exception as exc:
            return {"ok": False, "reason": str(exc), "latency_ms": 0}

    # ------------------------------------------------------------------
    # AI routing (direct LLM call, no conversation context)
    # ------------------------------------------------------------------

    def execute(self, prompt: str, model: str = "") -> dict[str, Any]:
        """Direct LLM execution without conversation context."""
        if not prompt or not prompt.strip():
            return {"ok": False, "reason": "empty prompt", "latency_ms": 0}
        try:
            ai = self._ensure_ai()
            return ai.generate(prompt.strip(), model=model)
        except Exception as exc:
            return {"ok": False, "reason": str(exc), "latency_ms": 0}

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def conversation_state(self) -> dict[str, Any]:
        """Get conversation state."""
        try:
            conv = self._ensure_conversation()
            return conv.state()
        except Exception as exc:
            return {"ok": False, "reason": str(exc), "latency_ms": 0}

    def reset(self) -> dict[str, Any]:
        """Reset conversation state."""
        try:
            conv = self._ensure_conversation()
            return conv.reset()
        except Exception as exc:
            return {"ok": False, "reason": str(exc), "latency_ms": 0}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Release all subsystem resources."""
        for name in ("_ai", "_voice", "_memory", "_conversation"):
            obj = getattr(self, name, None)
            if obj is not None:
                try:
                    obj.close()
                except Exception:
                    pass
                setattr(self, name, None)
        # Stop subprocess runner if present
        if self._ai_runner is not None:
            try:
                self._ai_runner.stop()
            except Exception:
                pass
            self._ai_runner = None

    # ------------------------------------------------------------------
    # Internal lazy instantiation
    # ------------------------------------------------------------------

    def _ensure_ai(self) -> Any:
        """Return AI runner — subprocess if available, else in-process AIDaemon."""
        if self._ai_runner is not None:
            return self._ai_runner
        if self._ai is None:
            if self._ai_class is None:
                raise RuntimeError("AIDaemon not importable")
            self._ai = self._ai_class()
        return self._ai

    def _ensure_voice(self) -> Any:
        if self._voice is None:
            if self._voice_class is None:
                raise RuntimeError("VoiceDaemon not importable")
            self._voice = self._voice_class()
        return self._voice

    def _ensure_memory(self) -> Any:
        if self._memory is None:
            if self._memory_class is None:
                raise RuntimeError("MemoryDaemon not importable")
            self._memory = self._memory_class()
        return self._memory

    def _ensure_conversation(self) -> Any:
        if self._conversation is None:
            if self._conversation_class is None:
                raise RuntimeError("ConversationDaemon not importable")
            if self._ai_runner is not None:
                try:
                    self._conversation = self._conversation_class(
                        ai_runner=self._ai_runner)
                except TypeError:
                    # Preserve compatibility with simple test/dummy facades.
                    self._conversation = self._conversation_class()
            else:
                self._conversation = self._conversation_class()
        return self._conversation
