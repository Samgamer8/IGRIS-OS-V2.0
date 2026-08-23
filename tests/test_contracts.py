"""Tests de los contratos formales del núcleo (Paso 1)."""

from __future__ import annotations

import importlib
import time

import pytest

from igris_os.core.contracts import (
    Error, ErrorCode, Event, EventType, Health, JobState, JobStatus,
    Request, Response, response_from_payload,
)


class TestImport:
    """El módulo debe importarse sin efectos secundarios."""

    def test_import_creates_no_subprocesses(self):
        import subprocess as _sp

        _orig = _sp.Popen
        spawned: list[str] = []

        def _track(*args, **kwargs):
            spawned.append(str(args[0] if args else "?"))
            return _orig(*args, **kwargs)

        _sp.Popen = _track  # type: ignore[assignment]
        try:
            # Import directo (sin reload: el reload re-crea las clases Enum
            # y rompe la identidad de isinstance para el resto de la sesion).
            importlib.import_module("igris_os.core.contracts")
            assert spawned == [], f"Import lanzo subprocesos: {spawned}"
        finally:
            _sp.Popen = _orig  # type: ignore[assignment]


class TestRequest:
    """Request debe validar method y timeout."""

    def test_defaults_are_filled(self):
        req = Request(method="chat")
        assert req.id
        assert req.timeout_ms == 30_000
        assert req.payload == {}

    def test_empty_method_raises(self):
        with pytest.raises(ValueError):
            Request(method="")

    def test_negative_timeout_raises(self):
        with pytest.raises(ValueError):
            Request(method="chat", timeout_ms=-1)


class TestResponse:
    """Response debe ser autoconsistente (ok ↔ error)."""

    def test_ok_with_error_raises(self):
        error = Error(code=ErrorCode.INTERNAL, message="boom")
        with pytest.raises(ValueError):
            Response(ok=True, error=error)

    def test_failed_without_error_raises(self):
        with pytest.raises(ValueError):
            Response(ok=False)

    def test_ok_factory(self):
        resp = Response.ok_response(request_id="r1", data={"text": "hola"})
        assert resp.ok is True
        assert resp.error is None
        assert resp.data["text"] == "hola"

    def test_error_factory(self):
        resp = Response.error_response(ErrorCode.TIMEOUT, "se acabo",
                                       request_id="r2", recoverable=True)
        assert resp.ok is False
        assert resp.error is not None
        assert resp.error.code is ErrorCode.TIMEOUT
        assert resp.error.recoverable is True

    def test_to_dict_roundtrip_fields(self):
        resp = Response.ok_response(request_id="r3", data={"tokens": 5})
        d = resp.to_dict()
        assert d["ok"] is True
        assert d["request_id"] == "r3"
        assert d["data"]["tokens"] == 5
        assert d["error"] is None

    def test_to_dict_includes_error(self):
        resp = Response.error_response(ErrorCode.DENIED, "no")
        d = resp.to_dict()
        assert d["error"]["code"] == "denied"
        assert d["error"]["message"] == "no"


class TestError:
    """Error debe validar código y mensaje."""

    def test_invalid_code_raises(self):
        with pytest.raises(ValueError):
            Error(code="internal", message="boom")  # type: ignore[arg-type]

    def test_empty_message_raises(self):
        with pytest.raises(ValueError):
            Error(code=ErrorCode.INTERNAL, message="   ")


class TestHealth:
    """Health agrega checks de forma correcta."""

    def test_aggregate_all_ok(self):
        h = Health.aggregate("core", {
            "ai": {"ok": True},
            "voice": {"ok": True},
            "memory": {"ok": True},
        })
        assert h.ok is True
        assert h.all_ok is True
        assert h.checks["ai"] is True

    def test_aggregate_any_failure(self):
        h = Health.aggregate("core", {
            "ai": {"ok": True},
            "voice": {"ok": False},
        })
        assert h.ok is False
        assert h.all_ok is False

    def test_aggregate_empty(self):
        h = Health.aggregate("core", {})
        assert h.ok is False  # sin componentes no se declara salud

    def test_to_dict(self):
        h = Health.aggregate("core", {"ai": {"ok": True}})
        d = h.to_dict()
        assert d["component"] == "core"
        assert d["checks"]["ai"] is True


class TestEvent:
    """Event debe ser serializable y validado."""

    def test_defaults(self):
        ev = Event(type=EventType.STARTED, job_id="j1")
        assert ev.job_id == "j1"
        assert ev.payload == {}
        assert ev.occurred_at > 0

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError):
            Event(type="started")  # type: ignore[arg-type]

    def test_to_dict(self):
        ev = Event(type=EventType.PROGRESS, job_id="j2", payload={"pct": 50})
        d = ev.to_dict()
        assert d["type"] == "progress"
        assert d["job_id"] == "j2"
        assert d["payload"]["pct"] == 50


class TestJobState:
    """La máquina de estados debe impedir transiciones inválidas."""

    def test_valid_transition(self):
        assert JobState.RECEIVED.can_transition_to(JobState.UNDERSTANDING)
        assert JobState.EXECUTING.can_transition_to(JobState.VERIFYING)
        assert JobState.VERIFYING.can_transition_to(JobState.COMPLETED)

    def test_invalid_transition(self):
        assert not JobState.COMPLETED.can_transition_to(JobState.EXECUTING)
        assert not JobState.RECEIVED.can_transition_to(JobState.COMPLETED)
        assert not JobState.FAILED.can_transition_to(JobState.RECEIVED)

    def test_terminal_states_are_terminal(self):
        for state in (JobState.COMPLETED, JobState.FAILED,
                      JobState.CANCELLED, JobState.ROLLED_BACK):
            assert state.can_transition_to(JobState.RECEIVED) is False


class TestJobStatus:
    """JobStatus valida estado y progreso."""

    def test_valid(self):
        st = JobStatus(job_id="j1", state=JobState.EXECUTING, progress=40)
        assert st.progress == 40

    def test_progress_out_of_range_raises(self):
        with pytest.raises(ValueError):
            JobStatus(job_id="j1", state=JobState.EXECUTING, progress=101)

    def test_empty_job_id_raises(self):
        with pytest.raises(ValueError):
            JobStatus(job_id="", state=JobState.RECEIVED)

    def test_invalid_state_raises(self):
        with pytest.raises(ValueError):
            JobStatus(job_id="j1", state="executing")  # type: ignore[arg-type]


class TestPayloadBridge:
    """response_from_payload normaliza el dict heredado de los daemons."""

    def test_ok_payload(self):
        resp = response_from_payload(
            {"ok": True, "text": "respuesta", "model": "m1", "tokens": 5})
        assert resp.ok is True
        assert resp.data["text"] == "respuesta"
        assert resp.data["model"] == "m1"

    def test_error_with_reason(self):
        resp = response_from_payload({"ok": False, "reason": "sin modelos"})
        assert resp.ok is False
        assert resp.error is not None
        assert resp.error.message == "sin modelos"

    def test_error_with_error_field(self):
        resp = response_from_payload({"ok": False, "error": "timeout"})
        assert resp.ok is False
        assert resp.error is not None
        assert resp.error.message == "timeout"

    def test_failure_without_detail(self):
        resp = response_from_payload({"ok": False})
        assert resp.ok is False
        assert resp.error is not None
        assert resp.error.message == "Fallo sin detalle"

    def test_health_payload_bridges(self):
        resp = response_from_payload(
            {"ok": True, "subsystems": {"ai": {"ok": True}}})
        assert resp.ok is True
        assert resp.data["subsystems"]["ai"]["ok"] is True

    def test_new_fields_are_preserved_no_whitelist(self):
        """Regresion: el whitelist perdia campos nuevos (p. ej. ``models``)
        al cruzar el IPC contractual. Todo lo no-envoltura se conserva."""
        resp = response_from_payload({
            "ok": True, "models": ["gemma4:26b", "qwen2.5-coder:7b"],
            "latency_ms": 3, "reason": None})
        assert resp.ok is True
        assert resp.data["models"] == ["gemma4:26b", "qwen2.5-coder:7b"]
        assert "latency_ms" not in resp.data
        assert "reason" not in resp.data

    def test_envelope_keys_never_leak_into_data(self):
        resp = response_from_payload(
            {"ok": True, "text": "x", "error": None, "request_id": "r"})
        assert resp.data == {"text": "x"}
