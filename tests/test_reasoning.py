"""Razonamiento (chain-of-thought) en la capa AI local.

Integra el patron de los modelos de razonamiento servidos por APIs
OpenAI-compatible: ``reasoning_content`` en la respuesta y el flag
``chat_template_kwargs.thinking`` opcional. No cambia el comportamiento
del backend Ollama clasico (``/api/generate``), que no emite razonamiento.
"""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

from igris_os.ai.daemon import AIDaemon
from igris_os.ai.lmstudio import LMStudioClient
from igris_os.ai.ollama import ModelReply, OllamaClient


class _OpenAIHandler(BaseHTTPRequestHandler):
    """Servidor OpenAI-compatible de prueba con reasoning_content."""

    last_body: dict | None = None
    reasoning = "17*20=340, 17*4=68, 340+68=408."

    def do_POST(self):
        length = int(self.headers["Content-Length"])
        type(self).last_body = json.loads(self.rfile.read(length))
        payload = json.dumps({
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "408",
                    "reasoning_content": type(self).reasoning,
                }
            }]
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


class _OllamaHandler(BaseHTTPRequestHandler):
    """Backend clasico /api/generate (sin razonamiento)."""

    def do_POST(self):
        length = int(self.headers["Content-Length"])
        type(self).last_body = json.loads(self.rfile.read(length))
        payload = json.dumps({"response": "respuesta normal", "done": True}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
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


def test_modelreply_reasoning_default_vacio():
    reply = ModelReply(True, "texto", "modelo")
    assert reply.reasoning == ""


def test_lmstudio_captura_reasoning():
    server, thread = _serve(_OpenAIHandler)
    try:
        port = server.server_address[1]
        client = LMStudioClient(f"http://127.0.0.1:{port}")
        reply = client.generate("17 por 24?", "thinking-model")
        assert reply.ok
        assert reply.text == "408"
        assert "17*20=340" in reply.reasoning
        assert reply.backend == "lmstudio"
    finally:
        server.shutdown()
        thread.join()


def test_ollama_conversation_uses_non_repetitive_options():
    server, thread = _serve(_OllamaHandler)
    try:
        port = server.server_address[1]
        client = OllamaClient(f"http://127.0.0.1:{port}")
        client.generate(
            "Eres IGRIS en una conversacion real. Responde al ultimo mensaje.",
            "qwen2.5-coder:7b")
        assert _OllamaHandler.last_body["options"]["repeat_penalty"] == 1.15
        assert _OllamaHandler.last_body["options"]["num_predict"] == 256
    finally:
        server.shutdown()
        thread.join()


def test_thinking_flag_se_envia_solo_cuando_se_pide():
    server, thread = _serve(_OpenAIHandler)
    try:
        port = server.server_address[1]
        client = LMStudioClient(f"http://127.0.0.1:{port}")
        client.generate("pregunta", "m", thinking=True)
        assert _OpenAIHandler.last_body["chat_template_kwargs"] == {"thinking": True}
        client.generate("pregunta2", "m")
        assert "chat_template_kwargs" not in _OpenAIHandler.last_body
    finally:
        server.shutdown()
        thread.join()


def test_ollama_clasico_sin_reasoning():
    server, thread = _serve(_OllamaHandler)
    try:
        port = server.server_address[1]
        client = OllamaClient(f"http://127.0.0.1:{port}")
        reply = client.generate("hola", "qwen2.5-coder:7b")
        assert reply.ok
        assert reply.text == "respuesta normal"
        assert reply.reasoning == ""
        assert reply.backend == "ollama"
    finally:
        server.shutdown()
        thread.join()


def test_daemon_expone_reasoning():
    server, thread = _serve(_OpenAIHandler)
    try:
        port = server.server_address[1]
        daemon = AIDaemon(client=LMStudioClient(f"http://127.0.0.1:{port}"))
        result = daemon.generate("17 por 24?", model="thinking-model")
        assert result["ok"]
        assert result["text"] == "408"
        assert "17*20=340" in (result["reasoning"] or "")
    finally:
        server.shutdown()
        thread.join()
