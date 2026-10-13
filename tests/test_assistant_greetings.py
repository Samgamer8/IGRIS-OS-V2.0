import unittest
from types import SimpleNamespace
from unittest.mock import patch

from igris_os.application.intent_classifier import _GREETING_CANNED
from igris_os.application.assistant import AssistantService, ConversationState


class _ReplyClient:
    """Cliente de prueba con un modelo local disponible."""

    def models(self):
        return ('qwen2.5-coder:7b',)

    def generate(self, prompt, model):
        return SimpleNamespace(
            ok=True, text='Hola. IGRIS a la espera.', model=model,
            error='', backend='local', reasoning='')


class _ClosedClient:
    """Cliente que no debe ser invocado en estas pruebas."""

    calls = []

    def models(self):
        return ('qwen2.5-coder:7b',)

    def generate(self, *args, **kwargs):
        _ClosedClient.calls.append(1)
        raise RuntimeError('no deberia llamar al LLM aqui')


_GREETING_CASES = ("Hola!", "hola?", "Buenos dias", "Buenas tardes",
                   "Que tal", "gracias", "ok", "perfecto",
                   "de acuerdo", "Entendido")


class TestAssistantGreetingPath(unittest.TestCase):
    """Saludos sin frases enlatadas: van al LLM como cualquier conversacion."""

    def setUp(self):
        _ClosedClient.calls = []

    def _resources(self):
        return patch('igris_os.ai.resources.get_system_resources',
                     return_value={'ram_free_gb': 64.0, 'vram_free_gb': None,
                                   'uncertain': True})

    def _service(self, client):
        service = AssistantService(client=client)
        service.state = ConversationState()
        return service

    def test_canned_greetings_are_disabled_by_design(self):
        # Sin frases preestablecidas: el LLM responde como un humano.
        self.assertEqual(_GREETING_CANNED, {})

    def test_greeting_variants_are_conversational(self):
        # Todos los saludos conocidos enrutan al camino conversacional.
        for raw in _GREETING_CASES:
            self.assertTrue(AssistantService._is_conversation(raw), raw)

    def test_greeting_reaches_the_model(self):
        service = self._service(_ReplyClient())
        with self._resources():
            reply = service.respond("hola")
        self.assertTrue(reply.ok)
        self.assertEqual(reply.model, 'qwen2.5-coder:7b')

    def test_greeting_state_is_preserved(self):
        service = self._service(_ReplyClient())
        with self._resources():
            reply = service.respond("hola")
        self.assertEqual(len(service.state.turns), 2)
        self.assertEqual(service.state.turns[0].role, "user")
        self.assertEqual(service.state.turns[0].text, "hola")
        self.assertEqual(service.state.turns[1].role, "assistant")
        self.assertEqual(service.state.turns[1].text, reply.text)

    def test_non_greeting_goes_to_llm(self):
        service = self._service(_ClosedClient())
        with self.assertRaises(RuntimeError):
            service.respond("crea un archivo")
        self.assertEqual(len(_ClosedClient.calls), 1)


if __name__ == "__main__":
    unittest.main()
