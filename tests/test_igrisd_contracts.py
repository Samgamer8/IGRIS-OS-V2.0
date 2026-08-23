"""Paso 2 / N — contratos cableados a la frontera pública de IgrisDaemon.

Verifica que ``handle(Request) -> Response`` normaliza entrada/salida a los
contratos del núcleo y emite Eventos de ciclo de vida, sin cambiar la lógica
interna de los daemons (los métodos de ruteo directo siguen intactos).
"""

from __future__ import annotations

from igris_os.core.contracts import (
    ErrorCode,
    Event,
    EventType,
    Request,
    Response,
)
from igris_os.core.igrisd import IgrisDaemon


# --- Mock subsystems (locales para no acoplar a test_igrisd) ---------------

class MockConversationDaemon:
    def __init__(self) -> None:
        self._turns = 0

    def health(self) -> dict:
        return {"ok": True, "engine": "mock-conv", "turns": self._turns, "latency_ms": 0.1}

    def chat(self, objective, context=()):
        self._turns += 1
        return {"ok": True, "text": f"Conv: {objective}", "model": "mock", "tokens": 5, "latency_ms": 1.0}

    def reset(self):
        self._turns = 0
        return {"ok": True, "latency_ms": 0.1}

    def close(self):
        pass


class MockMemoryDaemon:
    def __init__(self) -> None:
        self._memories: dict[str, list] = {}

    def health(self) -> dict:
        return {"ok": True, "db_path": ":memory:", "total_bytes": 0, "latency_ms": 0.1}

    def remember(self, category, content, *, verified=False):
        self._memories.setdefault(category, []).append(content)
        return {"ok": True, "memory_id": len(self._memories[category]), "category": category, "latency_ms": 0.1}

    def recall(self, category, *, limit=20, verified_only=True):
        memories = self._memories.get(category, [])[:limit]
        return {"ok": True, "memories": [{"content": m} for m in memories], "count": len(memories), "category": category, "latency_ms": 0.1}

    def close(self):
        pass


class MockAIDaemon:
    def health(self) -> dict:
        return {"ok": True, "engine": "mock-ai", "latency_ms": 0.1}

    def generate(self, prompt, model=""):
        return {"ok": True, "text": f"AI: {prompt[:50]}", "model": model or "mock", "tokens": 5, "latency_ms": 1.0}

    def close(self):
        pass


def _daemon_with(conv=True, memory=True, ai=True) -> IgrisDaemon:
    d = IgrisDaemon()
    if conv:
        d._conversation_class = MockConversationDaemon  # type: ignore[assignment]
    if memory:
        d._memory_class = MockMemoryDaemon  # type: ignore[assignment]
    if ai:
        d._ai_class = MockAIDaemon  # type: ignore[assignment]
    return d


# --- Tests ---------------------------------------------------------------

class TestHandleRoundTrip:
    """handle(Request) -> Response normaliza la ida y la vuelta."""

    def test_handle_exists(self):
        d = IgrisDaemon()
        assert callable(d.handle)
        assert callable(d.set_event_sink)
        d.close()

    def test_chat_roundtrip(self):
        d = _daemon_with()
        req = Request(method="chat", payload={"objective": "hola"})
        resp = d.handle(req)
        assert isinstance(resp, Response)
        assert resp.ok is True
        assert resp.request_id == req.id
        assert resp.data["text"] == "Conv: hola"
        assert resp.data["model"] == "mock"
        assert resp.latency_ms >= 0
        d.close()

    def test_remember_roundtrip(self):
        d = _daemon_with()
        req = Request(method="remember", payload={"category": "fact", "content": {"k": "v"}})
        resp = d.handle(req)
        assert resp.ok is True
        assert resp.request_id == req.id
        assert resp.latency_ms >= 0
        d.close()

    def test_execute_roundtrip(self):
        d = _daemon_with()
        req = Request(method="execute", payload={"prompt": "¿qué es Python?"})
        resp = d.handle(req)
        assert resp.ok is True
        assert resp.data["text"].startswith("AI:")
        assert resp.data["model"] == "mock"
        d.close()

    def test_health_all_roundtrip(self):
        d = _daemon_with()
        req = Request(method="health_all", payload={})
        resp = d.handle(req)
        assert resp.ok is True
        assert "subsystems" in resp.data
        assert resp.data["subsystems"]["conversation"]["ok"] is True
        d.close()

    def test_reset_roundtrip(self):
        d = _daemon_with()
        assert d.handle(Request(method="chat", payload={"objective": "a"})).ok
        resp = d.handle(Request(method="reset", payload={}))
        assert resp.ok is True
        d.close()

    def test_error_is_normalized(self):
        d = _daemon_with()
        req = Request(method="chat", payload={"objective": ""})
        resp = d.handle(req)
        assert resp.ok is False
        assert resp.error is not None
        assert resp.request_id == req.id
        d.close()


class TestHandleErrors:
    """Casos de frontera mal formados."""

    def test_unknown_method_is_bad_request(self):
        d = _daemon_with()
        req = Request(method="no_existe", payload={})
        resp = d.handle(req)
        assert resp.ok is False
        assert resp.error is not None
        assert resp.error.code == ErrorCode.BAD_REQUEST
        d.close()

    def test_non_request_is_bad_request(self):
        d = _daemon_with()
        resp = d.handle("hola")  # type: ignore[arg-type]
        assert resp.ok is False
        assert resp.error is not None
        assert resp.error.code == ErrorCode.BAD_REQUEST
        d.close()


class TestEventEmission:
    """Los Eventos de ciclo de vida llegan al sumidero."""

    def test_received_then_completed_in_order(self):
        d = _daemon_with()
        events: list[Event] = []
        d.set_event_sink(events.append)
        req = Request(method="chat", payload={"objective": "hola"}, trace_id="trace-1")
        resp = d.handle(req)
        assert resp.ok is True
        assert [e.type for e in events] == [EventType.RECEIVED, EventType.COMPLETED]
        assert all(e.job_id == req.id for e in events)
        assert all(e.trace_id == "trace-1" for e in events)
        d.close()

    def test_failure_emits_failed(self):
        d = _daemon_with()
        events: list[Event] = []
        d.set_event_sink(events.append)
        req = Request(method="no_existe", payload={})
        resp = d.handle(req)
        assert resp.ok is False
        assert [e.type for e in events] == [EventType.RECEIVED, EventType.FAILED]
        d.close()

    def test_sink_error_does_not_break_handle(self):
        d = _daemon_with()
        def _exploding(_e: Event) -> None:
            raise RuntimeError("sink roto")
        d.set_event_sink(_exploding)
        resp = d.handle(Request(method="chat", payload={"objective": "hola"}))
        assert resp.ok is True
        d.close()

    def test_set_event_sink_replaces(self):
        d = _daemon_with()
        first: list[Event] = []
        d.set_event_sink(first.append)
        d.set_event_sink(None)  # elimina el sumidero
        d.handle(Request(method="chat", payload={"objective": "hola"}))
        assert first == []
        d.close()
