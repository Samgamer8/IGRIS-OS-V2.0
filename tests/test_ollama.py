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
