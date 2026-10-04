import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from igris_os.ai import server


class LocalServerTests(unittest.TestCase):
    def test_native_command_has_bounded_context_and_owned_shutdown(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / 'llama-server.exe'
            executable.touch()
            model = root / 'model.gguf'
            model.write_bytes(b'GGUF')
            native = server.LlamaCppServer(executable, model, 'http://127.0.0.1:30000')
            process = Mock()
            process.poll.return_value = None
            with patch.object(native, 'is_running', side_effect=[False, True]), \
                 patch('subprocess.Popen', return_value=process) as spawn:
                self.assertTrue(native.start())
            command = spawn.call_args.args[0]
            self.assertEqual(command[command.index('--ctx-size') + 1], '4096')
            self.assertEqual(command[command.index('--parallel') + 1], '1')
            self.assertIn('--sleep-idle-seconds', command)
            self.assertIn('--no-webui', command)
            native.stop()
            process.terminate.assert_called_once()

    def test_native_settings_survive_application_to_environment(self):
        from igris_os.ui.settings_store import apply_ai_settings

        with patch.dict('os.environ', {}, clear=True):
            apply_ai_settings({'preferred_backend': 'openai', 'native_model_path': 'model.gguf'})
            import os
            self.assertEqual(os.environ['IGRIS_PREFERRED_BACKEND'], 'openai')
            self.assertEqual(os.environ['IGRIS_NATIVE_MODEL_PATH'], 'model.gguf')

    def test_compatible_server_prevents_ollama_autostart(self):
        owned = Mock()
        with patch.object(server, 'is_ollama_running', return_value=False), \
             patch.object(server, 'is_lmstudio_running', return_value=False), \
             patch.object(server, 'is_openai_running', return_value=True), \
             patch.object(server, '_GLOBAL_SERVER', owned):
            self.assertTrue(server.ensure_ollama_server(auto=True))
            self.assertEqual(server.detect_backend(), 'openai')
        owned.start.assert_not_called()

    def test_status_reports_compatible_endpoint_without_ollama(self):
        with patch.object(server, 'is_ollama_running', return_value=False), \
             patch.object(server, 'is_lmstudio_running', return_value=False), \
             patch.object(server, 'is_openai_running', return_value=True), \
             patch.dict('os.environ', {'IGRIS_OPENAI_ENDPOINT': 'http://127.0.0.1:8080/v1'}):
            status = server.server_status()
        self.assertTrue(status['running'])
        self.assertEqual(status['endpoint'], 'http://127.0.0.1:8080')
        self.assertFalse(status['internal'])
        self.assertIsNone(status['executable'])

    def test_no_backend_does_not_start_without_authorization(self):
        with patch.object(server, 'is_local_llm_running', return_value=False), \
             patch.object(server, 'OllamaServer') as factory:
            self.assertFalse(server.ensure_ollama_server(auto=False))
        factory.assert_not_called()


if __name__ == '__main__':
    unittest.main()