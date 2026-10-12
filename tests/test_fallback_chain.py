"""Tests de FallbackChain (cadena de modelos con failover, codigo propio).

Sin red: se usa un generador falso que emula FrontierGateway.generate.
"""
from __future__ import annotations

from igris_os.ai.fallback_chain import FallbackChain, FallbackResult
from igris_os.ai.ollama import ModelReply


class FakeGenerator:
    """Devuelve respuestas preprogramadas por modelo, en orden de llamada."""

    def __init__(self, script: dict[str, list[ModelReply]]) -> None:
        self.script = {k: list(v) for k, v in script.items()}
        self.calls: list[str] = []

    def generate(self, prompt: str, model: str, **kwargs) -> ModelReply:
        self.calls.append(model)
        queue = self.script.get(model)
        if queue:
            return queue.pop(0)
        # Modelo sin script: responde vacio (falla sin comprometer).
        return ModelReply(False, "", model, "sin script", backend="fake")


def _reply(ok: bool, text: str, model: str, error: str = "") -> ModelReply:
    return ModelReply(ok, text, model, error, backend="fake")


def test_primary_ok_does_not_fall_back():
    gen = FakeGenerator({"a": [_reply(True, "hola", "a")]})
    chain = FallbackChain(gen, models=["a", "b", "c"])
    result = chain.run("prompt")
    assert result.ok
    assert not result.used_fallback
    assert result.committed_index == 0
    assert result.committed_model == "a"
    assert gen.calls == ["a"]  # no toca las reservas


def test_primary_empty_falls_back_to_next():
    gen = FakeGenerator({
        "a": [_reply(False, "", "a", "vacío")],
        "b": [_reply(True, "respuesta B", "b")],
    })
    chain = FallbackChain(gen, models=["a", "b"])
    result = chain.run("prompt")
    assert result.ok
    assert result.used_fallback
    assert result.committed_model == "b"
    assert result.committed_index == 1
    assert gen.calls == ["a", "b"]


def test_all_fail_returns_last_failure_with_trace():
    gen = FakeGenerator({
        "a": [_reply(False, "", "a", "error A")],
        "b": [_reply(False, "", "b", "error B")],
    })
    chain = FallbackChain(gen, models=["a", "b"])
    result = chain.run("prompt")
    assert not result.ok
    assert result.committed_index == -1
    assert result.committed_model == ""
    assert result.reply.error == "error B"
    # la traza deja constancia honesta de ambos intentos
    assert [a.model for a in result.attempts] == ["a", "b"]
    assert all(not a.produced_text for a in result.attempts)


def test_empty_text_counts_as_not_committed():
    # ok=True pero sin texto: se considera que no comprometio respuesta.
    gen = FakeGenerator({
        "a": [_reply(True, "   ", "a")],
        "b": [_reply(True, "real", "b")],
    })
    chain = FallbackChain(gen, models=["a", "b"])
    result = chain.run("prompt")
    assert result.committed_model == "b"
    assert result.attempts[0].ok and not result.attempts[0].produced_text


def test_explicit_model_moves_to_front():
    gen = FakeGenerator({
        "a": [_reply(True, "A", "a")],
        "c": [_reply(True, "C", "c")],
    })
    chain = FallbackChain(gen, models=["a", "b", "c"])
    result = chain.run("prompt", model="c")
    assert result.committed_model == "c"
    assert gen.calls == ["c"]  # c primero, a no llega a probarse


def test_duplicates_and_blanks_removed():
    gen = FakeGenerator({"a": [_reply(True, "A", "a")]})
    chain = FallbackChain(gen, models=["a", "", "a", "  ", "b"])
    assert chain.models == ("a", "b")


def test_requires_at_least_one_model():
    try:
        FallbackChain(FakeGenerator({}), models=[])
    except ValueError:
        return
    raise AssertionError("Debe rechazar una cadena sin modelos")
