import unittest
from unittest.mock import Mock, patch

from igris_os.application.assistant import AssistantService, PERSONALITY, SYSTEM
from igris_os.application.intent_classifier import classify_intent
from igris_os.application.delivery_request import requested_delivery


class AssistantPersonalityTests(unittest.TestCase):
    def test_image_order_cannot_be_answered_with_an_unsupported_promise(self):
        request = 'ok igris te puedo pedir que me hagas una imagen de una esfera neuronal como jarvis'
        self.assertEqual(classify_intent(request).subtype, 'media_creation')
        assistant = AssistantService.__new__(AssistantService)
        assistant.client = Mock()
        reply = assistant.respond(request)
        self.assertFalse(reply.ok)
        self.assertTrue(reply.data['requires_execution'])
        assistant.client.generate.assert_not_called()

    def test_image_advice_is_not_an_execution_order(self):
        self.assertTrue(classify_intent('Como puedo crear una imagen?').is_conversation)

    def test_folder_name_does_not_include_the_next_sentence(self):
        request = 'crea una carpeta en el escritorio con el nombre : ajedrez 3D 1997 remasterizado. ahi lo pones el proyecto'
        self.assertEqual(requested_delivery(request)['name'], 'ajedrez 3D 1997 remasterizado')

    def test_actual_self_description_is_recognized(self):
        self.assertTrue(AssistantService._is_self_description_question('cuentame un poco sobre ti?'))

    def test_capable_model_is_kept_when_a_smaller_model_is_available(self):
        assistant = AssistantService.__new__(AssistantService)
        assistant.client = Mock()
        assistant.client.models.return_value = ('qwen2.5-coder:7b', 'qwen2.5:3b')
        with patch.dict('os.environ', {'IGRIS_CONVERSATION_MODEL': ''}):
            self.assertEqual(assistant._conversation_model(), 'qwen2.5-coder:7b')

    def test_explicit_conversation_model_is_respected(self):
        assistant = AssistantService.__new__(AssistantService)
        assistant.client = Mock()
        with patch.dict('os.environ', {'IGRIS_CONVERSATION_MODEL': 'custom-model'}):
            self.assertEqual(assistant._conversation_model(), 'custom-model')
        assistant.client.models.assert_not_called()

    def test_existing_model_is_kept_when_lightweight_model_is_missing(self):
        assistant = AssistantService.__new__(AssistantService)
        assistant.client = Mock()
        assistant.client.models.return_value = ('qwen2.5-coder:7b',)
        with patch.dict('os.environ', {'IGRIS_CONVERSATION_MODEL': ''}):
            self.assertEqual(assistant._conversation_model(), 'qwen2.5-coder:7b')

    def test_conversation_includes_personality_and_current_context(self):
        prompt = AssistantService._conversation_prompt(
            'No estoy de acuerdo.', ('user: Una idea anterior.',))
        self.assertIn(PERSONALITY, prompt)
        self.assertIn('con criterio propio', prompt)
        self.assertIn('No des la razon por complacer', prompt)
        self.assertIn('Responde siempre en espanol', prompt)
        self.assertIn('No ocultes ni maquilles errores', prompt)
        self.assertIn('user: Una idea anterior.', prompt)
        self.assertIn('No estoy de acuerdo.', prompt)
        self.assertIn('No ejecutes herramientas', prompt)

    def test_operational_prompt_keeps_personality_and_evidence_rules(self):
        self.assertIn(PERSONALITY, SYSTEM)
        self.assertIn('Nunca afirmes que modificaste', SYSTEM)
        self.assertIn('Si hace falta confirmacion', SYSTEM)


if __name__ == '__main__':
    unittest.main()