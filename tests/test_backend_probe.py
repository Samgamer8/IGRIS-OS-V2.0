import threading
import unittest
from unittest.mock import MagicMock, Mock, patch

from igris_os.ai.ollama import OllamaClient, _probe_backends


class BackendProbeTests(unittest.TestCase):
    def test_structured_requests_send_schema_to_compatible_engine(self):
        client = OllamaClient.__new__(OllamaClient)
        client.endpoint = 'http://127.0.0.1:30000'
        client._cache = Mock()
        schema = {'type': 'object', 'properties': {'ok': {'type': 'boolean'}},
                  'required': ['ok'], 'additionalProperties': False}
        data = {'choices': [{'finish_reason': 'stop', 'message': {'content': '{"ok":true}'}}]}
        with patch.object(client, '_post_json', return_value=data) as post:
            reply = client._generate_openai('Devuelve JSON', 'model', 'hash', response_format=schema)
        self.assertTrue(reply.ok)
        body = post.call_args.args[1]
        self.assertEqual(body['response_format']['json_schema']['schema'], schema)
        self.assertEqual(body['max_tokens'], 4096)

    def test_probes_are_parallel_and_preference_order_is_preserved(self):
        gate = threading.Barrier(3)

        def open_response(request, timeout):
            gate.wait(timeout=2)
            response = MagicMock(status=200)
            response.__enter__.return_value = response
            return response

        opener = Mock()
        opener.open.side_effect = open_response
        with patch('urllib.request.build_opener', return_value=opener), \
             patch.dict('os.environ', {'IGRIS_OPENAI_ENDPOINT': '', 'IGRIS_OPENAI_PORT': '30000',
                                       'IGRIS_PREFERRED_BACKEND': ''}):
            found = _probe_backends()
        self.assertEqual([name for name, endpoint in found], ['ollama', 'lmstudio', 'openai'])
        self.assertEqual(opener.open.call_count, 3)

    def test_explicit_preference_selects_compatible_engine_first(self):
        response = MagicMock(status=200)
        response.__enter__.return_value = response
        opener = Mock()
        opener.open.return_value = response
        with patch('urllib.request.build_opener', return_value=opener), \
             patch.dict('os.environ', {'IGRIS_PREFERRED_BACKEND': 'openai'}):
            self.assertEqual(_probe_backends()[0][0], 'openai')

    def test_exclusive_mode_does_not_probe_or_select_another_engine(self):
        response = MagicMock(status=200)
        response.__enter__.return_value = response
        opener = Mock()
        opener.open.return_value = response
        with patch('urllib.request.build_opener', return_value=opener), \
             patch.dict('os.environ', {'IGRIS_PREFERRED_BACKEND': 'openai',
                                       'IGRIS_EXCLUSIVE_BACKEND': 'true'}):
            self.assertEqual(len(_probe_backends()), 1)
        opener.open.assert_called_once()

    def test_unreachable_servers_are_not_reported(self):
        opener = Mock()
        opener.open.side_effect = OSError('Offline')
        with patch('urllib.request.build_opener', return_value=opener):
            self.assertEqual(_probe_backends(), [])


if __name__ == '__main__':
    unittest.main()