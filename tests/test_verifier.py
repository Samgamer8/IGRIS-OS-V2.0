from igris_os.ai import ModelReply
from igris_os.evaluation import IndependentVerifier


class FakeClient:
    def __init__(self, models, replies):
        self._models = models
        self._replies = list(replies)

    def models(self):
        return self._models

    def generate(self, prompt, model):
        if self._replies:
            return self._replies.pop(0)
        return ModelReply(False, "", model, "sin mas respuestas")


def test_verifier_uses_a_different_model_and_approves():
    client = FakeClient(
        ("qwen2.5-coder:7b", "qwen2.5-coder:14b"),
        [ModelReply(True, '{"score": 95, "approved": true, "reason": "ok"}',
                    "qwen2.5-coder:14b")])
    verdict = IndependentVerifier(client).verify(
        "codigo listo", "crear utilidad", ["pruebas pasan"],
        generator_model="qwen2.5-coder:7b")
    assert verdict.approved
    assert verdict.verifier_model == "qwen2.5-coder:14b"
    assert verdict.score == 95.0


def test_verifier_rejects_below_threshold():
    client = FakeClient(
        ("m1", "m2"),
        [ModelReply(True, '{"score": 40, "approved": true, "reason": "pobre"}',
                    "m2")])
    verdict = IndependentVerifier(client, threshold=0.7).verify(
        "x", "objetivo", (), generator_model="m1")
    assert not verdict.approved


def test_verifier_skips_without_second_model():
    client = FakeClient(("m1",), [])
    verdict = IndependentVerifier(client).verify(
        "x", "objetivo", (), generator_model="m1")
    assert verdict.skipped
    assert verdict.approved


def test_verifier_handles_unparseable_reply():
    client = FakeClient(
        ("m1", "m2"), [ModelReply(True, "no hay json aqui", "m2")])
    verdict = IndependentVerifier(client).verify(
        "x", "objetivo", (), generator_model="m1")
    assert not verdict.approved


def test_verifier_rejects_invalid_threshold():
    import pytest
    with pytest.raises(ValueError):
        IndependentVerifier(FakeClient((), []), threshold=1.5)
