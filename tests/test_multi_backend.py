"""Deteccion multi-backend de la capa AI.

Ollama (11434) y LM Studio (1234) locales + servidor OpenAI-compatible
configurable (IGRIS_OPENAI_PORT / IGRIS_OPENAI_ENDPOINT, por defecto 30000).

El cliente agrega los modelos de todos los backends alcanzables y despacha
cada llamada al backend propietario del modelo. Si el servidor configurado
no responde, se mantiene el fallback local.
"""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

from igris_os.ai import ollama as ollama_mod
from igris_os.ai.ollama import OllamaClient


# ---------------------------------------------------------------------------
# Servidores falsos
# ---------------------------------------------------------------------------

class _OllamaHandler(BaseHTTPRequestHandler):
    """Backend clasico Ollama: /api/tags, /api/generate, /api/embed."""

    def do_GET(self):
        if self.path == "/api/tags":
            payload = json.dumps({
                "models": [{"name": "qwen2.5-coder:7b"},
                           {"name": "nomic-embed-text"}]}).encode()
            self._reply(payload)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers["Content-Length"])
        json.loads(self.rfile.read(length))
        if self.path == "/api/embed":
            payload = json.dumps({"embeddings": [[1.0, 0.0]]}).encode()
        else:  # /api/generate (stream o no — una sola linea JSON vale para ambos)
            payload = json.dumps(
                {"response": "respuesta ollama", "done": True}).encode()
        self._reply(payload)

    def _reply(self, payload: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


class _OpenAIHandler(BaseHTTPRequestHandler):
    """Servidor OpenAI-compatible: /v1/models, /v1/chat/completions, /v1/embeddings."""

    last_body: dict | None = None

    def do_GET(self):
        if self.path == "/v1/models":
            payload = json.dumps({
                "data": [{"id": "thinkingmachines/Inkling-NVFP4"}]}).encode()
            self._reply(payload)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers["Content-Length"])
        type(self).last_body = json.loads(self.rfile.read(length))
        if self.path == "/v1/embeddings":
            payload = json.dumps(
                {"data": [{"embedding": [0.5, 0.5]}]}).encode()
            self._reply(payload)
        elif type(self).last_body.get("stream"):
            chunk = json.dumps({
                "choices": [{"delta": {"content": "respuesta openai"}}]})
            sse = f"data: {chunk}\n\ndata: [DONE]\n\n".encode()
            self._reply(sse, content_type="text/event-stream")
        else:
            payload = json.dumps({
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": "respuesta openai",
                        "reasoning_content": "pensamiento interno",
                    }
                }]
            }).encode()
            self._reply(payload)

    def _reply(self, payload: bytes, content_type: str = "application/json") -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


def _serve(handler):
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _candidates_ollama_mas_openai(ollama_port: int, openai_port: int):
    return (
        ("ollama", f"http://127.0.0.1:{ollama_port}", "/api/tags"),
        ("lmstudio", "http://127.0.0.1:1", "/v1/models"),  # no alcanzable
        ("openai", f"http://127.0.0.1:{openai_port}", "/v1/models"),
    )


# ---------------------------------------------------------------------------
# Configuracion del endpoint OpenAI-compatible
# ---------------------------------------------------------------------------

def test_openai_endpoint_default_port(monkeypatch):
    monkeypatch.delenv("IGRIS_OPENAI_ENDPOINT", raising=False)
    monkeypatch.delenv("IGRIS_OPENAI_PORT", raising=False)
    assert ollama_mod._openai_endpoint_from_env() == "http://127.0.0.1:30000"


def test_openai_endpoint_env_port(monkeypatch):
    monkeypatch.delenv("IGRIS_OPENAI_ENDPOINT", raising=False)
    monkeypatch.setenv("IGRIS_OPENAI_PORT", "39999")
    assert ollama_mod._openai_endpoint_from_env() == "http://127.0.0.1:39999"


def test_openai_endpoint_env_full_url(monkeypatch):
    monkeypatch.setenv("IGRIS_OPENAI_ENDPOINT", "http://127.0.0.1:7777/v1/")
    assert ollama_mod._openai_endpoint_from_env() == "http://127.0.0.1:7777/v1"


def test_openai_endpoint_rechaza_no_loopback(monkeypatch):
    monkeypatch.setenv("IGRIS_OPENAI_ENDPOINT", "http://evil.example:30000")
    assert ollama_mod._openai_endpoint_from_env() == "http://127.0.0.1:30000"


def test_openai_endpoint_port_invalido_cae_a_default(monkeypatch):
    monkeypatch.delenv("IGRIS_OPENAI_ENDPOINT", raising=False)
    monkeypatch.setenv("IGRIS_OPENAI_PORT", "abc")
    assert ollama_mod._openai_endpoint_from_env() == "http://127.0.0.1:30000"


# ---------------------------------------------------------------------------
# Deteccion + despacho multi-backend
# ---------------------------------------------------------------------------

def test_deteccion_y_despacho_multi_backend(monkeypatch):
    ollama_server, ollama_thread = _serve(_OllamaHandler)
    openai_server, openai_thread = _serve(_OpenAIHandler)
    try:
        ollama_port = ollama_server.server_address[1]
        openai_port = openai_server.server_address[1]
        monkeypatch.setattr(
            ollama_mod, "_BACKEND_CANDIDATES",
            _candidates_ollama_mas_openai(ollama_port, openai_port))
        monkeypatch.setenv("IGRIS_OPENAI_PORT", str(openai_port))
        ollama_mod.reset_backend_detection()
        try:
            client = OllamaClient()
            assert ("ollama", f"http://127.0.0.1:{ollama_port}") in client._backends
            assert ("openai", f"http://127.0.0.1:{openai_port}") in client._backends

            models = client.models()
            assert "qwen2.5-coder:7b" in models
            assert "nomic-embed-text" in models
            assert "thinkingmachines/Inkling-NVFP4" in models

            # despacho: modelo de ollama -> protocolo /api/generate
            r1 = client.generate("hola", "qwen2.5-coder:7b")
            assert r1.ok and r1.text == "respuesta ollama"
            assert r1.backend == "ollama"

            # despacho: modelo del servidor OpenAI-compatible -> /v1/chat/completions
            r2 = client.generate("17 por 24?", "thinkingmachines/Inkling-NVFP4")
            assert r2.ok and r2.text == "respuesta openai"
            assert "pensamiento interno" in r2.reasoning
            assert r2.backend == "openai"

            # modelo desconocido -> backend primario (ollama, fallback local)
            r3 = client.generate("hola", "modelo-inexistente")
            assert r3.ok and r3.text == "respuesta ollama"
            assert r3.backend == "ollama"

            # embeddings: despacho al backend propietario del modelo
            ok, vectors = client.embed(["."], "thinkingmachines/Inkling-NVFP4")
            assert ok and vectors == [[0.5, 0.5]]
        finally:
            ollama_mod.reset_backend_detection()
    finally:
        ollama_server.shutdown()
        openai_server.shutdown()
        ollama_thread.join()
        openai_thread.join()


def test_cache_hit_conserva_backend(monkeypatch):
    """Una respuesta cacheada conserva el backend que la genero."""
    ollama_server, ollama_thread = _serve(_OllamaHandler)
    openai_server, openai_thread = _serve(_OpenAIHandler)
    try:
        ollama_port = ollama_server.server_address[1]
        openai_port = openai_server.server_address[1]
        monkeypatch.setattr(
            ollama_mod, "_BACKEND_CANDIDATES",
            _candidates_ollama_mas_openai(ollama_port, openai_port))
        monkeypatch.setenv("IGRIS_OPENAI_PORT", str(openai_port))
        ollama_mod.reset_backend_detection()
        try:
            client = OllamaClient()
            client.models()
            first = client.generate("17 por 24?", "thinkingmachines/Inkling-NVFP4")
            assert first.backend == "openai"
            # misma peticion -> cache hit, backend conservado
            second = client.generate("17 por 24?", "thinkingmachines/Inkling-NVFP4")
            assert second.ok and second.text == "respuesta openai"
            assert second.backend == "openai"
        finally:
            ollama_mod.reset_backend_detection()
    finally:
        ollama_server.shutdown()
        openai_server.shutdown()
        ollama_thread.join()
        openai_thread.join()


def test_generate_stream_despacha_por_backend(monkeypatch):
    ollama_server, ollama_thread = _serve(_OllamaHandler)
    openai_server, openai_thread = _serve(_OpenAIHandler)
    try:
        ollama_port = ollama_server.server_address[1]
        openai_port = openai_server.server_address[1]
        monkeypatch.setattr(
            ollama_mod, "_BACKEND_CANDIDATES",
            _candidates_ollama_mas_openai(ollama_port, openai_port))
        monkeypatch.setenv("IGRIS_OPENAI_PORT", str(openai_port))
        ollama_mod.reset_backend_detection()
        try:
            client = OllamaClient()
            client.models()  # construye el indice modelo -> backend

            chunks_ollama = list(client.generate_stream("hola", "qwen2.5-coder:7b"))
            assert "".join(chunks_ollama) == "respuesta ollama"

            chunks_openai = list(
                client.generate_stream("hola", "thinkingmachines/Inkling-NVFP4"))
            assert "".join(chunks_openai) == "respuesta openai"
        finally:
            ollama_mod.reset_backend_detection()
    finally:
        ollama_server.shutdown()
        openai_server.shutdown()
        ollama_thread.join()
        openai_thread.join()


def test_fallback_local_sin_servidor_openai(monkeypatch):
    """Si el servidor OpenAI-compatible no responde, solo queda el local."""
    ollama_server, ollama_thread = _serve(_OllamaHandler)
    try:
        ollama_port = ollama_server.server_address[1]
        monkeypatch.setattr(
            ollama_mod, "_BACKEND_CANDIDATES",
            (("ollama", f"http://127.0.0.1:{ollama_port}", "/api/tags"),))
        monkeypatch.setenv("IGRIS_OPENAI_PORT", "1")  # puerto sin servidor
        ollama_mod.reset_backend_detection()
        try:
            client = OllamaClient()
            assert client._backends == [
                ("ollama", f"http://127.0.0.1:{ollama_port}")]
            assert client.models() == ("qwen2.5-coder:7b", "nomic-embed-text")
            reply = client.generate("hola", "qwen2.5-coder:7b")
            assert reply.ok and reply.text == "respuesta ollama"
        finally:
            ollama_mod.reset_backend_detection()
    finally:
        ollama_server.shutdown()
        ollama_thread.join()


def test_probe_sin_ningun_backend_mantiene_ollama(monkeypatch):
    monkeypatch.setattr(
        ollama_mod, "_BACKEND_CANDIDATES",
        (("ollama", "http://127.0.0.1:1", "/api/tags"),))
    monkeypatch.setenv("IGRIS_OPENAI_PORT", "1")
    assert ollama_mod._probe_backends() == [("ollama", "http://127.0.0.1:11434")]
