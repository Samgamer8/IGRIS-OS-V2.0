"""AIDaemon — fachada publica para la capa AI de IGRIS OS.

Paso 1 / N del plan de separacion por procesos. Esta fachada aísla los
metodos que cualquier futura capa IPC necesitara cruzar la frontera
del proceso, sin tocar ``cinematic.py`` / ``assistant.py`` / ``kernel.py``.

Reglas:
  * Sin estado a nivel de modulo.
  * Sin threads ni timers.
  * Sin IO en el import.
  * Ningun metodo lanza excepciones: fallas se devuelven como
    ``{"ok": False, "error": "..."}``.

Superficie expuesta (la que IPC necesitara):

    health()    -> liveness / modelos disponibles
    chat(msgs)  -> multi-turno, se compone a prompt y se delega a generate()
    generate(prompt, model)  -> el metodo directo que ya usa assistant.py

Los metodos delegan en ``OllamaClient`` sin modificarlo.
"""

from __future__ import annotations

import time
from typing import Any

from .ollama import ModelReply, OllamaClient


_DEFAULT_TIMEOUT_S: float = 30.0


class AIDaemon:
    """Fachada AI. Punto de entrada estable para IPC futuro."""

    def __init__(
        self,
        client: OllamaClient | None = None,
        timeout_s: float = _DEFAULT_TIMEOUT_S,
    ) -> None:
        self._client = client or OllamaClient()
        self._timeout = max(0.5, float(timeout_s))

    # ---- PROBE ---------------------------------------------------------
    def health(self) -> dict[str, Any]:
        """Liveness: confirma que el backend lista modelos."""
        t0 = time.perf_counter()
        try:
            models = self._client.models()
        except Exception as exc:                              # noqa: BLE001
            return _err(exc, t0)
        ok = bool(models)
        return {
            "ok": ok,
            "text": None,
            "error": None if ok else "backend lista 0 modelos",
            "latency_ms": _ms(t0),
            "model": models[0] if models else "",
        }

    # ---- MULTI-TURNO ---------------------------------------------------
    def chat(
        self,
        messages: list[dict[str, str]],
        model: str = "",
    ) -> dict[str, Any]:
        """messages = [{role: system|user|assistant, content: str}, ...]"""
        if not messages:
            return _err(ValueError("messages vacio"), time.perf_counter())
        prompt = _compose_prompt(messages)
        return self.generate(prompt, model=model)

    # ---- DIRECTO -------------------------------------------------------
    def generate(self, prompt: str, model: str = "") -> dict[str, Any]:
        t0 = time.perf_counter()
        if not prompt or not prompt.strip():
            return _err(ValueError("prompt vacio"), t0)
        try:
            reply: ModelReply = self._client.generate(prompt, model)
        except Exception as exc:                              # noqa: BLE001
            return _err(exc, t0)
        return {
            "ok": bool(reply.ok),
            "text": reply.text,
            "error": reply.error or None,
            "latency_ms": _ms(t0),
            "model": reply.model,
        }


# ---------------------------------------------------------------------
# Internals (private — no IO, puros)
# ---------------------------------------------------------------------

def _compose_prompt(messages: list[dict[str, str]]) -> str:
    parts: list[str] = []
    for m in messages:
        role = (m.get("role") or "").strip().lower()
        content = (m.get("content") or "").strip()
        if not content:
            continue
        if role == "system":
            parts.append(f"[SYSTEM] {content}")
        elif role == "assistant":
            parts.append(f"[ASSISTANT] {content}")
        else:
            parts.append(f"[USER] {content}")
    return "\n".join(parts)


def _ms(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)


def _err(exc: BaseException, t0: float) -> dict[str, Any]:
    return {
        "ok": False,
        "text": None,
        "error": f"{type(exc).__name__}: {exc}",
        "latency_ms": _ms(t0),
        "model": "",
    }
