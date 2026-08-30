from __future__ import annotations

import hmac
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any

from .store import ApprovalRequest, SamadminStore


class SamadminServer:
    """Servidor loopback de supervisión: solicita, aprueba y consume permisos."""

    def __init__(self, root: Path, *, admin_token: str,
                 host: str = "127.0.0.1", port: int = 8765) -> None:
        if not admin_token:
            raise ValueError("Samadmin requiere un token de administrador")
        self.store = SamadminStore(root)
        self.admin_token = admin_token
        self.httpd = ThreadingHTTPServer((host, port), self._handler())
        self.thread: Thread | None = None

    @property
    def url(self) -> str:
        host, port = self.httpd.server_address[:2]
        return f"http://{host}:{port}"

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.thread = Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        if self.thread:
            self.thread.join(timeout=2)

    def _handler(self):
        store = self.store
        token = self.admin_token

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path == "/health":
                    return self._send(200, {"ok": True, "service": "samadmin"})
                if self.path == "/v1/requests":
                    return self._send(200, {"requests": [_serialize(item) for item in store.pending()]})
                if self.path.startswith("/v1/requests/"):
                    request = store.get(self.path.rsplit("/", 1)[-1])
                    return self._send(200, _serialize(request)) if request else self._send(404, {"error": "not_found"})
                self._send(404, {"error": "not_found"})

            def do_POST(self) -> None:
                body = self._body()
                if body is None:
                    return
                if self.path == "/v1/requests":
                    try:
                        request = store.create(str(body.get("objective", "")),
                                               str(body.get("capability", "")),
                                               str(body.get("stage", "")))
                    except ValueError as exc:
                        return self._send(400, {"error": str(exc)})
                    return self._send(201, _serialize(request))
                if self.path == "/v1/authorizations/consume":
                    approved = store.consume(str(body.get("request_id", "")),
                                             str(body.get("objective", "")),
                                             str(body.get("capability", "")),
                                             str(body.get("stage", "")))
                    return self._send(200, {"approved": approved})
                if self.path.startswith("/v1/requests/") and self.path.endswith(("/approve", "/reject")):
                    if not self._admin_authorized():
                        return self._send(401, {"error": "admin_token_required"})
                    request_id, decision = self.path.split("/")[-2:]
                    decided = store.decide(request_id, approved=decision == "approve",
                                           operator=str(body.get("operator", "Samadmin")))
                    return self._send(200, _serialize(decided)) if decided else self._send(409, {"error": "not_pending"})
                self._send(404, {"error": "not_found"})

            def _body(self) -> dict[str, Any] | None:
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    raw = self.rfile.read(min(length, 64 * 1024))
                    value = json.loads(raw.decode("utf-8")) if raw else {}
                    if not isinstance(value, dict):
                        raise ValueError
                    return value
                except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
                    self._send(400, {"error": "invalid_json"})
                    return None

            def _admin_authorized(self) -> bool:
                given = self.headers.get("X-Samadmin-Token", "")
                return hmac.compare_digest(given, token)

            def _send(self, status: int, value: dict[str, Any]) -> None:
                data = json.dumps(value, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, format: str, *args: object) -> None:
                return

        return Handler


def _serialize(request: ApprovalRequest | None) -> dict[str, str]:
    if request is None:
        return {}
    return {
        "request_id": request.request_id, "objective": request.objective,
        "capability": request.capability, "stage": request.stage,
        "status": request.status, "operator": request.operator,
        "created_at": request.created_at, "decided_at": request.decided_at,
    }