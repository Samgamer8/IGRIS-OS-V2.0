import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

from igris_os.ai.ollama import ModelReply
from igris_os.evolution.dual_debate import (
    DebatePersona, DualDebateSession, load_default_manual)


class DualDebateSessionTests(unittest.TestCase):
    def _client(self, replies):
        client = Mock()
        client.generate.side_effect = replies
        return client

    def test_personas_alternate_and_each_turn_is_persisted_immediately(self):
        with TemporaryDirectory() as directory:
            log_path = Path(directory) / "debate.jsonl"
            replies = [
                ModelReply(True, "Propuesta A", "m"),
                ModelReply(True, "Contrapropuesta B", "m"),
                ModelReply(True, "Ajuste A", "m"),
            ]
            client = self._client(replies)
            session = DualDebateSession(client, "tema de prueba", log_path=log_path)
            calls = {"count": 0}

            def should_stop():
                calls["count"] += 1
                return calls["count"] > 3

            turns = session.run(should_stop)
            self.assertEqual([t.persona for t in turns],
                             ["IGRIS OS", "IGRIS OS ibrido", "IGRIS OS"])
            self.assertEqual([t.message for t in turns],
                             ["Propuesta A", "Contrapropuesta B", "Ajuste A"])
            # Persistencia turno a turno: el archivo ya tiene las 3 lineas,
            # nunca se pierde progreso si el proceso se interrumpe.
            lines = log_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 3)
            self.assertEqual(json.loads(lines[0])["persona"], "IGRIS OS")

    def test_should_stop_halts_before_the_next_turn(self):
        with TemporaryDirectory() as directory:
            log_path = Path(directory) / "debate.jsonl"
            client = self._client([ModelReply(True, "Unica respuesta", "m")])
            session = DualDebateSession(client, "tema", log_path=log_path)
            turns = session.run(lambda: True)
            self.assertEqual(turns, [])
            self.assertFalse(log_path.exists())
            client.generate.assert_not_called()

    def test_max_turns_caps_the_loop_even_without_should_stop(self):
        with TemporaryDirectory() as directory:
            log_path = Path(directory) / "debate.jsonl"
            replies = [ModelReply(True, f"turno {i}", "m") for i in range(5)]
            client = self._client(replies)
            session = DualDebateSession(client, "tema", log_path=log_path)
            turns = session.run(lambda: False, max_turns=2)
            self.assertEqual(len(turns), 2)

    def test_failed_reply_is_recorded_without_aborting_the_debate(self):
        with TemporaryDirectory() as directory:
            log_path = Path(directory) / "debate.jsonl"
            replies = [
                ModelReply(False, "", "m", error="backend caido"),
                ModelReply(True, "sigue el debate", "m"),
            ]
            client = self._client(replies)
            session = DualDebateSession(client, "tema", log_path=log_path)
            turns = session.run(lambda: False, max_turns=2)
            self.assertIn("backend caido", turns[0].message)
            self.assertEqual(turns[1].message, "sigue el debate")

    def test_prompt_includes_topic_manual_and_opposing_persona_history(self):
        with TemporaryDirectory() as directory:
            log_path = Path(directory) / "debate.jsonl"
            client = self._client([
                ModelReply(True, "primero", "m"), ModelReply(True, "segundo", "m")])
            session = DualDebateSession(
                client, "optimizar la bola neuronal", log_path=log_path,
                reference_material="MANUAL-DE-PRUEBA")
            session.run(lambda: False, max_turns=2)
            first_prompt, second_prompt = (
                call.args[0] for call in client.generate.call_args_list)
            self.assertIn("optimizar la bola neuronal", first_prompt)
            self.assertIn("MANUAL-DE-PRUEBA", first_prompt)
            self.assertIn("IGRIS OS ibrido", second_prompt)
            self.assertIn("primero", second_prompt)

    def test_custom_personas_are_respected(self):
        with TemporaryDirectory() as directory:
            log_path = Path(directory) / "debate.jsonl"
            personas = (
                DebatePersona(name="Analista", system_prompt="Mide todo."),
                DebatePersona(name="Disenador", system_prompt="Simplifica todo."),
            )
            client = self._client([ModelReply(True, "x", "m")])
            session = DualDebateSession(
                client, "tema", personas=personas, log_path=log_path)
            turns = session.run(lambda: False, max_turns=1)
            self.assertEqual(turns[0].persona, "Analista")

    def test_render_markdown_includes_every_turn(self):
        with TemporaryDirectory() as directory:
            log_path = Path(directory) / "debate.jsonl"
            client = self._client([
                ModelReply(True, "primero", "m"), ModelReply(True, "segundo", "m")])
            session = DualDebateSession(client, "tema de la interfaz", log_path=log_path)
            session.run(lambda: False, max_turns=2)
            markdown = session.render_markdown()
            self.assertIn("tema de la interfaz", markdown)
            self.assertIn("primero", markdown)
            self.assertIn("segundo", markdown)

    def test_default_manual_is_the_github_reference_material(self):
        manual = load_default_manual()
        self.assertIn("GitHub", manual)
        self.assertIn("prompt", manual.lower())


if __name__ == "__main__":
    unittest.main()
