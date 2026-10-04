import threading
import time
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
        with TemporaryDirectory() as directory:
            registry = server.SharedServerRegistry(Path(directory) / '.igris_shared_server')
            with patch.object(server, 'is_ollama_running', return_value=False), \
                 patch.object(server, 'is_lmstudio_running', return_value=False), \
                 patch.object(server, 'is_openai_running', return_value=True), \
                 patch.object(server, '_GLOBAL_SERVER', owned), \
                 patch.object(server, '_shared_registry', return_value=registry):
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


class SharedServerRegistryTests(unittest.TestCase):
    """IGRIS OS e IGRIS OS ibrido pueden compartir el mismo servidor LLM en
    loopback. Estas pruebas cubren el conteo de referencias entre procesos
    que evita apagarlo mientras otro panel lo siga usando."""

    def test_second_client_prevents_shutdown_until_both_release(self):
        with TemporaryDirectory() as directory:
            registry = server.SharedServerRegistry(Path(directory) / '.igris_shared_server')
            with patch.object(server, '_pid_alive', return_value=True):
                with patch('os.getpid', return_value=111):
                    registry.register(server_pid=999)
                with patch('os.getpid', return_value=222):
                    registry.register()
                with patch('os.getpid', return_value=111):
                    self.assertIsNone(registry.release())
                with patch('os.getpid', return_value=222):
                    self.assertEqual(registry.release(), 999)

    def test_dead_clients_are_pruned_on_access(self):
        with TemporaryDirectory() as directory:
            registry = server.SharedServerRegistry(Path(directory) / '.igris_shared_server')
            # El PID 111 queda registrado pero luego "muere" (crash/kill -9);
            # solo el 222, que sigue vivo, cuenta como cliente real.
            with patch.object(server, '_pid_alive', side_effect=lambda pid: pid != 111):
                with patch('os.getpid', return_value=111):
                    registry.register(server_pid=999)
                with patch('os.getpid', return_value=222):
                    registry.register()
                    self.assertEqual(registry.release(), 999)

    def test_stop_owned_server_skips_shutdown_while_other_panel_active(self):
        with TemporaryDirectory() as directory:
            registry = server.SharedServerRegistry(Path(directory) / '.igris_shared_server')
            owned = Mock()
            with patch.object(server, '_shared_registry', return_value=registry), \
                 patch.object(server, '_pid_alive', return_value=True):
                registry.register(server_pid=4321)  # nuestro propio panel
                with patch('os.getpid', return_value=99999):
                    registry.register()  # IGRIS OS ibrido se suma como cliente
                with patch.object(server, '_GLOBAL_SERVER', owned):
                    server.stop_owned_server()
                owned.stop.assert_not_called()
                # El otro panel tambien cierra: ahora si debe apagarse.
                with patch('os.getpid', return_value=99999):
                    self.assertEqual(registry.release(), 4321)

    def test_concurrent_panels_do_not_double_start_native_server(self):
        """Dos paneles arrancando a la vez no deben lanzar dos procesos
        llama-server: el segundo debe esperar y sumarse al primero."""
        with TemporaryDirectory() as directory:
            model = Path(directory) / 'model.gguf'
            model.write_bytes(b'GGUF')
            executable = Path(directory) / 'llama-server.exe'
            executable.touch()
            registry = server.SharedServerRegistry(Path(directory) / '.igris_shared_server')
            running = threading.Event()
            start_calls = []
            start_lock = threading.Lock()

            class FakeNativeServer:
                _proc = None

                def __init__(self, *args, **kwargs):
                    pass

                def start(self, wait=45.0):
                    with start_lock:
                        start_calls.append(1)
                    time.sleep(0.2)  # simula el tiempo real de carga del modelo
                    running.set()
                    return True

            with patch.object(server, '_shared_registry', return_value=registry), \
                 patch.dict('os.environ', {'IGRIS_PREFERRED_BACKEND': 'openai',
                                           'IGRIS_NATIVE_EXECUTABLE': str(executable),
                                           'IGRIS_NATIVE_MODEL_PATH': str(model)}), \
                 patch.object(server, 'is_openai_running', side_effect=lambda *a, **k: running.is_set()), \
                 patch.object(server, 'LlamaCppServer', FakeNativeServer), \
                 patch.object(server, '_GLOBAL_SERVER', None):
                results = []
                threads = [threading.Thread(target=lambda: results.append(server.ensure_ollama_server(auto=True)))
                          for _ in range(2)]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(timeout=10)
            self.assertEqual(len(start_calls), 1)
            self.assertEqual(results, [True, True])


if __name__ == '__main__':
    unittest.main()