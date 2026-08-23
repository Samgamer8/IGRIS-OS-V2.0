"""Paso 3 / N — frontera contractual IPC de AIProcessRunner.

``AIProcessRunner.request(Request) -> Response`` permite que cualquier
proceso (UI, CLI) hable con la capa AI usando solo contratos del núcleo,
sin conocer el protocolo interno de colas.

Los tests de subproceso real requieren Ollama en localhost:11434
(consistentes con los de test_ai_daemon_process.py).
"""

from __future__ import annotations

from igris_os.ai.daemon_process import AIProcessRunner
from igris_os.core.contracts import ErrorCode, Request, Response


class TestRequestValidation:
    """Casos de frontera mal formados (sin subproceso)."""

    def test_non_request_returns_bad_request(self):
        r = AIProcessRunner()
        resp = r.request("hola")  # type: ignore[arg-type]
        assert isinstance(resp, Response)
        assert resp.ok is False
        assert resp.error is not None
        assert resp.error.code == ErrorCode.BAD_REQUEST

    def test_unknown_method_returns_bad_request(self):
        r = AIProcessRunner()
        req = Request(method="no_existe", payload={})
        resp = r.request(req)
        assert resp.ok is False
        assert resp.error is not None
        assert resp.error.code == ErrorCode.BAD_REQUEST
        assert resp.request_id == req.id


class TestRequestSubprocess:
    """request() habla con el subproceso real (requiere Ollama)."""

    def test_health_roundtrip(self):
        r = AIProcessRunner(timeout=15)
        r.start()
        req = Request(method="health", payload={})
        resp = r.request(req)
        assert isinstance(resp, Response)
        assert resp.ok is True
        assert resp.request_id == req.id
        assert resp.latency_ms >= 0
        r.stop()

    def test_generate_roundtrip(self):
        r = AIProcessRunner(timeout=30)
        r.start()
        req = Request(method="generate", payload={
            "prompt": "responde solo: ok", "model": "qwen2.5-coder:7b"})
        resp = r.request(req)
        assert isinstance(resp, Response)
        assert resp.ok is True
        assert resp.request_id == req.id
        assert "text" in resp.data
        r.stop()

    def test_backends_roundtrip(self):
        r = AIProcessRunner(timeout=15)
        r.start()
        req = Request(method="backends", payload={})
        resp = r.request(req)
        assert isinstance(resp, Response)
        assert resp.ok is True
        assert resp.request_id == req.id
        names = [name for name, _ in resp.data.get("backends", [])]
        assert "ollama" in names
        r.stop()

    def test_models_roundtrip(self):
        r = AIProcessRunner(timeout=15)
        r.start()
        req = Request(method="models", payload={})
        resp = r.request(req)
        assert isinstance(resp, Response)
        assert resp.ok is True
        assert "qwen2.5-coder:7b" in resp.data.get("models", [])
        r.stop()

    def test_error_inside_worker_is_normalized(self):
        """Un fallo del worker llega como Response ok=False con error."""
        r = AIProcessRunner(timeout=5)
        r.start()
        # method existe en el worker pero falla por payload inválido
        req = Request(method="generate", payload={"prompt": ""})
        resp = r.request(req)
        assert isinstance(resp, Response)
        assert resp.ok is False
        assert resp.error is not None
        assert resp.request_id == req.id
        r.stop()
