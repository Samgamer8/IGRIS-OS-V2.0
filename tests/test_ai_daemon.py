"""Tests para ``igris_os.ai.daemon.AIDaemon`` — Paso 1/N.

Cubren:
  * import sin side-effect
  * ``health()`` cuando el backend lista 0 modelos
  * ``chat(messages)`` compone y delega en ``generate``
  * ``generate()`" traga excepciones y devuelve ``ok=False``
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from igris_os.ai.daemon import AIDaemon
from igris_os.ai.ollama import ModelReply


def test_daemon_imports_clean() -> None:
    """Re-import idempotente, sin IO ni threads."""
    import importlib

    import igris_os.ai.daemon

    # reload no debe lanzar ni tocar la red
    importlib.reload(igris_os.ai.daemon)


def test_health_returns_proper_shape_when_no_models() -> None:
    fake = MagicMock()
    fake.models.return_value = ()
    d = AIDaemon(client=fake, timeout_s=1.0)
    out = d.health()

    assert isinstance(out, dict)
    assert out["ok"] is False
    assert "0 modelos" in (out["error"] or "")
    assert out["text"] is None
    assert out["model"] == ""
    assert out["latency_ms"] >= 0


def test_chat_composes_prompt_and_delegates_to_generate() -> None:
    fake = MagicMock()
    fake.generate.return_value = ModelReply(
        ok=True, text="hola", model="llama3.1:8b", error="",
    )
    d = AIDaemon(client=fake, timeout_s=1.0)
    out = d.chat([
        {"role": "system", "content": "sé breve"},
        {"role": "user", "content": "di hola"},
    ])

    assert out["ok"] is True
    assert out["text"] == "hola"
    assert out["model"] == "llama3.1:8b"
    assert out["error"] is None

    prompt = fake.generate.call_args[0][0]
    assert "[SYSTEM] sé breve" in prompt
    assert "[USER] di hola" in prompt


def test_generate_swallows_exception() -> None:
    fake = MagicMock()
    fake.generate.side_effect = RuntimeError("connection refused")
    d = AIDaemon(client=fake, timeout_s=1.0)
    out = d.generate("hola mundo", model="llama3.1:8b")

    assert out["ok"] is False
    assert out["text"] is None
    assert "RuntimeError" in out["error"]
    assert "connection refused" in out["error"]
    # La excepcion no se propaga al caller
