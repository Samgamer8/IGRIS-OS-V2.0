import unittest
from types import SimpleNamespace
from unittest.mock import patch

from igris_os.application.intent_classifier import _GREETING_CANNED
from igris_os.application.assistant import AssistantService, ConversationState


class _ClosedClient:
    """Cliente de prueba que bloquea: nunca responde a generate."""

    calls = []

    def generate(self, *args, **kwargs):
        _ClosedClient.calls.append(1)
        raise RuntimeError("no deberia llamar nunca al LLM en un saludo")


class TestAssistantGreetingFastPath(unittest.TestCase):
    def _service(self):
        service = AssistantService(client=_ClosedClient())
        service.state = ConversationState()
        return service

    def test_greeting_uses_fast_path_without_llm(self):
        service = self._service()
        reply = service.respond("hola")
        self.assertTrue(reply.ok)
        self.assertEqual(reply.text, _GREETING_CANNED["hola"])
        self.assertEqual(reply.model, "")
        self.assertEqual(reply.tokens, 0)
        self.assertEqual(len(_ClosedClient.calls), 0)

    def test_greeting_variants(self):
        service = self._service()
        for raw, key in (
            ("Hola!", "hola!"),
            ("hola?", "hola?"),
            ("Buenos dias", "buenos dias"),
            ("Buenas tardes", "buenas tardes"),
            ("Que tal", "que tal"),
            ("gracias", "gracias"),
            ("ok", "ok"),
            ("perfecto", "perfecto"),
            ("de acuerdo", "de acuerdo"),
            ("Entendido", "entendido"),
        ):
            reply = service.respond(raw)
            self.assertTrue(reply.ok, raw)
            self.assertEqual(reply.text, _GREETING_CANNED[key], raw)

    def test_greeting_state_is_preserved(self):
        service = self._service()
        reply = service.respond("hola")
        self.assertEqual(len(service.state.turns), 2)
        self.assertEqual(service.state.turns[0].role, "user")
        self.assertEqual(service.state.turns[0].text, "hola")
        self.assertEqual(service.state.turns[1].role, "assistant")
        self.assertEqual(service.state.turns[1].text, reply.text)

    def test_non_greeting_goes_to_llm(self):
        service = self._service()
        with self.assertRaises(RuntimeError):
            service.respond("crea un archivo")
        self.assertEqual(len(_ClosedClient.calls), 1)


if __name__ == "__main__":
    unittest.main()
