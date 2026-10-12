"""Tests del consentimiento explicito en el AssistantService real.

Verifica que IGRIS PREGUNTA antes de un paso de alto calado (cablear algo
en el nucleo) en vez de ejecutarlo a ciegas, y que un 'si'/'no' resuelve la
propuesta. Determinista: usa un cliente cerrado, sin red ni Ollama.
"""
from __future__ import annotations

from igris_os.ai.ollama import ModelReply
from igris_os.application.assistant import AssistantService, ConversationState


class _ClosedClient:
    def models(self):
        return ()

    def generate(self, *a, **k):
        return ModelReply(False, "", "", "sin modelo", "")

    def chat_turn(self, *a, **k):
        raise RuntimeError("sin red")


def _service() -> AssistantService:
    service = AssistantService(client=_ClosedClient())
    service.state = ConversationState()
    return service


def test_high_impact_request_asks_instead_of_executing():
    service = _service()
    reply = service.respond("cablear el FallbackChain dentro del asistente real")
    assert reply.data.get("consent", {}).get("decision") == "pending"
    assert "cablee" in reply.text.lower() or "asistente real" in reply.text.lower()
    assert service.consent.has_pending()


def test_pending_reply_is_interpreted_as_consent_not_new_order():
    service = _service()
    service.respond("integrar esto en el kernel del sistema")
    assert service.consent.has_pending()
    accepted = service.respond("si")
    assert accepted.data.get("consent", {}).get("decision") == "accepted"
    assert not service.consent.has_pending()


def test_pending_rejection_does_not_run():
    service = _service()
    service.respond("modificar el nucleo del sistema")
    assert service.consent.has_pending()
    rejected = service.respond("no")
    assert rejected.data.get("consent", {}).get("decision") == "rejected"
    assert not service.consent.has_pending()


def test_unclear_answer_keeps_pending():
    service = _service()
    service.respond("cablear el bootstrap")
    assert service.consent.has_pending()
    reply = service.respond("no estoy seguro")
    assert reply.data.get("consent", {}).get("decision") == "unclear"
    assert service.consent.has_pending()  # sigue esperando


def test_normal_request_does_not_trigger_consent():
    service = _service()
    # Un encargo corriente no debe disparar la pregunta de alto calado.
    reply = service.respond("hola")
    assert reply.data.get("consent") is None
    assert not service.consent.has_pending()
