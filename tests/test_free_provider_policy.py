import unittest
from unittest.mock import Mock, patch

from igris_os.ai.multi_provider import GenerationRequest, GenerationResponse, MultiProviderRouter, ProviderRank
from igris_os.ai.ollama import ModelReply


class FreeProviderPolicyTests(unittest.TestCase):
    def test_local_specialist_works_without_external_sdk(self):
        client = Mock()
        client.models.return_value = ('qwen2.5-coder:7b', 'kimi-k3:cloud')
        client.generate.return_value = ModelReply(True, 'Resultado local', 'qwen2.5-coder:7b', backend='openai')
        router = MultiProviderRouter(local_client=client)
        result = router.generate(GenerationRequest('Orden', system_prompt='Revisor', task_type='review'))
        self.assertTrue(result.success)
        self.assertEqual(result.cost_usd, 0)
        client.generate.assert_called_once_with('Revisor\n\nOrden', 'qwen2.5-coder:7b')

    def test_cloud_tag_is_not_a_local_free_model(self):
        client = Mock()
        client.models.return_value = ('kimi-k3:cloud',)
        router = MultiProviderRouter(local_client=client)
        with self.assertRaises(RuntimeError):
            router.generate(GenerationRequest('Orden'))
        client.generate.assert_not_called()

    def test_paid_provider_is_blocked_even_if_cached_as_available(self):
        router = MultiProviderRouter()
        for provider in ProviderRank:
            if provider != ProviderRank.OLLAMA:
                router._availability_cache[provider] = True
                self.assertFalse(router._is_provider_available(provider))
                response = router._execute_with_provider(provider, GenerationRequest('Hola'))
                self.assertFalse(response.success)
                self.assertIn('bloqueado', response.error)

    def test_local_failure_does_not_call_paid_fallback(self):
        router = MultiProviderRouter()
        router.custom_priority = [ProviderRank.OLLAMA, ProviderRank.OPENAI]
        router._availability_cache = {ProviderRank.OLLAMA: True, ProviderRank.OPENAI: True}
        failure = GenerationResponse('', ProviderRank.OLLAMA, 'local', success=False, error='Fallo local')
        with patch('igris_os.ai.multi_provider.LITELLM_AVAILABLE', True), \
             patch.object(router, '_execute_with_provider', return_value=failure) as execute:
            self.assertFalse(router.generate(GenerationRequest('Hola')).success)
        execute.assert_called_once()
        self.assertEqual(execute.call_args.args[0], ProviderRank.OLLAMA)


if __name__ == '__main__':
    unittest.main()