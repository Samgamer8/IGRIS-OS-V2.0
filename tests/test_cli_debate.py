from pathlib import Path
from tempfile import TemporaryDirectory
import json
import os
import unittest
from unittest.mock import patch

from igris_os.ai.ollama import ModelReply, OllamaClient
from igris_os.cli import main as cli_main


class DebateCliTests(unittest.TestCase):
    def test_debate_command_runs_bounded_turns_and_writes_transcript(self):
        with TemporaryDirectory() as directory:
            previous = os.getcwd()
            os.chdir(directory)
            try:
                with patch.object(OllamaClient, 'generate',
                                  return_value=ModelReply(True, 'respuesta', 'm')):
                    exit_code = cli_main([
                        'debate', 'tema de prueba', '--max-turns', '2'])
                self.assertEqual(exit_code, 0)
                debates_dir = Path(directory) / 'runtime' / 'debates'
                jsonl_files = list(debates_dir.glob('*.jsonl'))
                markdown_files = list(debates_dir.glob('*.md'))
                self.assertEqual(len(jsonl_files), 1)
                self.assertEqual(len(markdown_files), 1)
                lines = jsonl_files[0].read_text(encoding='utf-8').splitlines()
                self.assertEqual(len(lines), 2)
                self.assertIn('tema de prueba', markdown_files[0].read_text(encoding='utf-8'))
            finally:
                os.chdir(previous)

    def test_debate_stops_when_stop_file_appears(self):
        with TemporaryDirectory() as directory:
            previous = os.getcwd()
            os.chdir(directory)
            try:
                stop_file = Path(directory) / 'stop.flag'
                calls = {'count': 0}

                def fake_generate(prompt, model, **_kwargs):
                    calls['count'] += 1
                    if calls['count'] == 1:
                        stop_file.touch()
                    return ModelReply(True, f'turno {calls["count"]}', model)

                with patch.object(OllamaClient, 'generate', side_effect=fake_generate):
                    exit_code = cli_main([
                        'debate', 'tema', '--stop-file', str(stop_file)])
                self.assertEqual(exit_code, 0)
                self.assertEqual(calls['count'], 1)
                self.assertFalse(stop_file.exists())
            finally:
                os.chdir(previous)


if __name__ == '__main__':
    unittest.main()
