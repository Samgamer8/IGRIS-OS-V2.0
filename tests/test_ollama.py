import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import pytest

from igris_os.ai import OllamaClient


def test_ollama_rejects_non_loopback():
    with pytest.raises(ValueError):
        OllamaClient("http://192.168.1.2:11434")


def test_unavailable_ollama_is_controlled():
    assert OllamaClient("http://127.0.0.1:1").models() == ()


class _EmbedHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers["Content-Length"])
        body = json.loads(self.rfile.read(length))
        assert body["model"] == "embed-model"
        texts = body.get("input", [])
        embeddings = [[1.0, 0.0] for _ in texts]
        payload = json.dumps({"embeddings": embeddings}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


def test_ollama_embed_returns_vectors():
    server = HTTPServer(("127.0.0.1", 0), _EmbedHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        ok, vectors = OllamaClient(
            f"http://127.0.0.1:{port}").embed(["hola", "mundo"], "embed-model")
        assert ok
        assert vectors == [[1.0, 0.0], [1.0, 0.0]]
    finally:
        server.shutdown()
        thread.join()


class _TagsEmbedHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/tags":
            payload = json.dumps({
                "models": [{"name": "llama3"}, {"name": "nomic-embed-text"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers["Content-Length"])
        body = json.loads(self.rfile.read(length))
        assert body["model"] == "nomic-embed-text"
        texts = body.get("input", [])
        payload = json.dumps(
            {"embeddings": [[1.0, 0.0] for _ in texts]}).encode()
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


def test_select_embedding_model_uses_validation():
    server, thread = _serve(_TagsEmbedHandler)
    try:
        port = server.server_address[1]
        client = OllamaClient(f"http://127.0.0.1:{port}")
        assert client.select_embedding_model() == "nomic-embed-text"
    finally:
        server.shutdown()
        thread.join()


def test_select_embedding_model_empty_when_offline():
    assert OllamaClient("http://127.0.0.1:1").select_embedding_model() is None
