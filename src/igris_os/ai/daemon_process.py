"""AIProcessRunner — runs AIDaemon in a separate subprocess.

This is the real process separation (step 7 / N).  LLM calls happen in
a child process so the Qt event loop in the main process never blocks.

IPC: multiprocessing.Queue (reliable on Windows, no AF_UNIX needed).

Usage:
    runner = AIProcessRunner()
    runner.start()
    result = runner.health()          # non-blocking from main process
    result = runner.generate("hola")  # blocks until subprocess replies
    runner.stop()

If the subprocess crashes, the next call auto-restarts it.

No side-effects on import.
"""

from __future__ import annotations

import logging
import multiprocessing
import threading
import time
from typing import Any, Callable

from igris_os.core.contracts import ErrorCode, Request, Response, response_from_payload

logger = logging.getLogger(__name__)


# Ruta contractual AI → operación interna del runner.  Cada adaptador lee
# los kwargs del payload y delega en el método público correspondiente.
_AI_ROUTES: dict[str, Callable[[Any, dict[str, Any]], dict[str, Any]]] = {
    "generate": lambda self, p: self.generate(
        p.get("prompt", ""), model=p.get("model", ""),
        thinking=bool(p.get("thinking", False))),
    "chat": lambda self, p: self.chat(
        p.get("messages") or [], model=p.get("model", "")),
    "health": lambda self, p: self.health(),
    "models": lambda self, p: self.models(),
    "backends": lambda self, p: self.backends(),
}

# -----------------------------------------------------------------------
# Worker function (runs in the child process)
# -----------------------------------------------------------------------

def _ai_worker(request_q: multiprocessing.Queue,
               response_q: multiprocessing.Queue) -> None:
    """Child process: reads requests from request_q, writes responses to response_q."""
    # Lazy import — only instantiate AIDaemon inside the child
    from igris_os.ai.daemon import AIDaemon

    daemon = AIDaemon()
    logger.info("AI worker process started (pid=%d)", __import__("os").getpid())

    while True:
        try:
            msg = request_q.get(timeout=60)
        except Exception:
            # Timeout — check if parent is still alive, otherwise exit
            continue

        if msg is None:
            # Shutdown signal
            logger.info("AI worker received shutdown signal")
            break

        msg_id = msg.get("id", "")
        method = msg.get("method", "")
        args = msg.get("args", ())
        kwargs = msg.get("kwargs", {})

        try:
            fn = getattr(daemon, method, None)
            if fn is None:
                result = {"ok": False, "reason": f"unknown method: {method}"}
            else:
                result = fn(*args, **kwargs)
        except Exception as exc:
            result = {"ok": False, "reason": str(exc)}

        try:
            response_q.put({"id": msg_id, "result": result}, timeout=10)
        except Exception:
            logger.warning("AI worker: failed to send response for %s", msg_id)

    close_fn = getattr(daemon, "close", None)
    if callable(close_fn):
        close_fn()
    logger.info("AI worker process exiting")


# -----------------------------------------------------------------------
# Main-process runner
# -----------------------------------------------------------------------

class AIProcessRunner:
    """Thread-safe wrapper around the AI subprocess.

    All public methods are safe to call from the Qt main thread.
    """

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout
        self._process: multiprocessing.Process | None = None
        self._request_q: multiprocessing.Queue | None = None
        self._response_q: multiprocessing.Queue | None = None
        self._counter = 0
        self._call_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> dict[str, Any]:
        """Start the AI subprocess."""
        if self._process is not None and self._process.is_alive():
            return {"ok": True, "reason": "already running", "pid": self._process.pid}

        self._request_q = multiprocessing.Queue()
        self._response_q = multiprocessing.Queue()

        self._process = multiprocessing.Process(
            target=_ai_worker,
            args=(self._request_q, self._response_q),
            daemon=True,
            name="igris-ai",
        )
        self._process.start()
        logger.info("AI subprocess started (pid=%d)", self._process.pid)

        # Wait for first health check to confirm worker is alive
        time.sleep(0.3)
        if not self._process.is_alive():
            return {"ok": False, "reason": "worker died on startup"}

        return {"ok": True, "pid": self._process.pid}

    def stop(self) -> None:
        """Stop the AI subprocess gracefully."""
        if self._process is None:
            return
        if self._request_q is not None:
            try:
                self._request_q.put_nowait(None)  # shutdown signal
            except Exception:
                pass
        if self._process.is_alive():
            self._process.join(timeout=5)
            if self._process.is_alive():
                self._process.terminate()
                self._process.join(timeout=3)
        self._process = None
        self._request_q = None
        self._response_q = None
        logger.info("AI subprocess stopped")

    def is_alive(self) -> bool:
        """Check if the subprocess is running."""
        return self._process is not None and self._process.is_alive()

    # ------------------------------------------------------------------
    # Public API (thread-safe)
    # ------------------------------------------------------------------

    def health(self) -> dict[str, Any]:
        """Health check via subprocess."""
        return self._call("health", timeout=5.0)

    def models(self) -> dict[str, Any]:
        """List installed models via subprocess (full list)."""
        return self._call("models", timeout=5.0)

    def backends(self) -> dict[str, Any]:
        """Backends detectados via subprocess."""
        return self._call("backends", timeout=5.0)

    def request(self, request: Request) -> Response:
        """Frontera contractual IPC: procesa un ``Request`` AI y devuelve un
        ``Response``, todo a través del subproceso (paso 3 / N).

        Cualquier proceso (UI, CLI) puede hablar con la capa AI solo con
        contratos del núcleo, sin conocer el protocolo interno de colas.
        """
        if not isinstance(request, Request):
            return Response.error_response(
                ErrorCode.BAD_REQUEST,
                "request espera un Request contractual",
            )
        route = _AI_ROUTES.get(request.method)
        if route is None:
            return Response.error_response(
                ErrorCode.BAD_REQUEST,
                f"método no soportado por la capa AI: {request.method}",
                request_id=request.id,
            )
        raw = route(self, request.payload)
        return response_from_payload(raw, request_id=request.id)

    def generate(self, prompt: str, model: str = "", *, thinking: bool = False) -> dict[str, Any]:
        """Generate text via subprocess."""
        return self._call("generate", args=(prompt,), kwargs={"model": model, "thinking": thinking},
                          timeout=self._timeout)

    def chat(self, messages: list, model: str = "", **kwargs: Any) -> dict[str, Any]:
        """Chat via subprocess."""
        return self._call("chat", args=(messages,), kwargs={"model": model, **kwargs},
                          timeout=self._timeout)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _call(self, method: str, *, args: tuple = (), kwargs: dict | None = None,
              timeout: float | None = None) -> dict[str, Any]:
        """Send a request to the subprocess and wait for the response."""
        with self._call_lock:
            return self._call_locked(method, args=args, kwargs=kwargs,
                                     timeout=timeout)

    def _call_locked(self, method: str, *, args: tuple = (),
                     kwargs: dict | None = None,
                     timeout: float | None = None) -> dict[str, Any]:
        if timeout is None:
            timeout = self._timeout

        # Auto-restart if dead
        if not self.is_alive():
            start_result = self.start()
            if not start_result.get("ok"):
                return {"ok": False, "reason": f"worker not running: {start_result}"}

        self._counter += 1
        msg_id = f"req-{self._counter}"
        msg = {"id": msg_id, "method": method, "args": args, "kwargs": kwargs or {}}

        try:
            self._request_q.put_nowait(msg)  # type: ignore[union-attr]
        except Exception as exc:
            return {"ok": False, "reason": f"failed to send request: {exc}"}

        # Wait for response
        t0 = time.monotonic()
        while (time.monotonic() - t0) < timeout:
            try:
                resp = self._response_q.get(timeout=min(0.5, timeout))  # type: ignore[union-attr]
            except Exception:
                continue

            if resp.get("id") == msg_id:
                return resp.get("result", {"ok": False, "reason": "empty response"})

            # Respuesta de una llamada anterior que ya expiró (id < actual):
            # se descarta.  Nunca se escribe en la cola de peticiones — eso
            # corrompía el protocolo (bug de race condition).
            logger.debug("descartando respuesta obsoleta id=%s", resp.get("id"))

        return {"ok": False, "reason": f"timeout after {timeout}s", "method": method}
