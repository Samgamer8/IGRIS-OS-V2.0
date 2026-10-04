import unittest

from igris_os.ai.daemon import AIDaemon
from igris_os.ai.ollama import ModelReply
from igris_os.ui.response_preferences import output_limit, preference_context


class FakeClient:
    output_token_limit = 4096

    def generate(self, prompt, model, thinking=False):
        return ModelReply(True, str(self.output_token_limit), model, backend='local')


class ResponsePreferenceTests(unittest.TestCase):
    def test_gateway_local_client_receives_limit_without_mutation(self):
        class Gateway:
            def __init__(self):
                self.local = FakeClient()

            def generate(self, prompt, model, thinking=False):
                return self.local.generate(prompt, model, thinking=thinking)

        client = Gateway()
        daemon = AIDaemon(client=client)
        self.assertEqual(daemon.generate('Hola', 'model', output_limit=1024)['text'], '1024')
        self.assertEqual(client.local.output_token_limit, 4096)

    def test_output_limit_is_per_request_not_mutated_globally(self):
        client = FakeClient()
        daemon = AIDaemon(client=client)
        self.assertEqual(daemon.generate('Hola', 'model', output_limit=512)['text'], '512')
        self.assertEqual(client.output_token_limit, 4096)
        self.assertEqual(daemon.generate('Hola', 'model')['text'], '4096')
        self.assertFalse(daemon.generate('Hola', 'model', output_limit=-1)['ok'])

    def test_profiles_do_not_change_permissions(self):
        self.assertIn('No cambia permisos', preference_context({'conversation_agent': 'reviewer'})[0])
        self.assertEqual(output_limit({'resource_mode': 'advanced'}), 2048)
        self.assertIsNone(output_limit({'resource_mode': 'auto'}))


if __name__ == '__main__':
    unittest.main()