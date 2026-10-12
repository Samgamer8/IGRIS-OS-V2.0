import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from igris_os.ai.ollama import ModelReply
from igris_os.evolution.github_sources import (
    EvidenceChunk, RepositoryFile, RepositorySnapshot,
)
from igris_os.evolution.dual_debate import _evidence_batches, run_repository_debate


class RepositoryDebateTests(unittest.TestCase):
    def test_evidence_batches_split_long_material_under_the_context_budget(self):
        source = RepositorySnapshot(
            "https://github.com/example/course", "example", "course", "main", "abc123",
            (RepositoryFile("README.md", "x" * 20_000),),
            (EvidenceChunk("S1-R001", "S1", "README.md", 1, 1, "x" * 20_000),),
            1, 0, (),
        )
        batches = list(_evidence_batches((source,), limit=1_000))
        self.assertGreater(len(batches), 1)
        self.assertTrue(all(len(batch) <= 1_000 for batch in batches))
        self.assertTrue(all("[S1-R001]" in batch for batch in batches))

    def test_independent_reads_precede_alternating_debate_and_two_plans(self):
        source = RepositorySnapshot(
            "https://github.com/example/course", "example", "course", "main", "abc123",
            (RepositoryFile("README.md", "Concepts and workflow"),),
            (EvidenceChunk("S1-R001", "S1", "README.md", 1, 1, "Concepts and workflow"),),
            1, 0, (),
        )
        answers = [f"Nota citada [S1-R001] {i}" for i in range(2)]
        answers += ["Tres pasos iniciales [S1-R001]", "Rebatir los tres [S1-R001]"]
        answers += ["Plan A [S1-R001]", "Plan B [S1-R001]"]
        client = Mock()
        client.generate.side_effect = [ModelReply(True, text, "test") for text in answers]
        events = []

        with TemporaryDirectory() as directory, patch(
            "igris_os.evolution.dual_debate.read_github_repositories", return_value=(source,)
        ) as read_repos:
            log_path = Path(directory) / "events.jsonl"
            result = run_repository_debate(
                client, [source.url], log_path=log_path,
                model="test", max_turns=2, on_event=events.append)
            lines = log_path.read_text(encoding="utf-8").splitlines()

        read_repos.assert_called_once_with([source.url])
        self.assertEqual(result["state"], "complete")
        self.assertEqual([e["persona"] for e in events if e["type"] == "turn"],
                         ["IGRIS OS", "IGRIS OS ibrido"])
        self.assertEqual(len([e for e in events if e["type"] == "reading_note"]), 2)
        self.assertEqual(len([e for e in events if e["type"] == "plan"]), 2)
        self.assertTrue(all("timestamp" in json.loads(line) for line in lines))
        self.assertIn("tres pasos", client.generate.call_args_list[2].args[0].lower())
        self.assertIn("rebate", client.generate.call_args_list[3].args[0].lower())

    def test_no_automatic_turn_cap_and_manual_stop_ends_the_exchange(self):
        source = RepositorySnapshot(
            "https://github.com/example/course", "example", "course", "main", "abc123",
            (RepositoryFile("README.md", "Concepts"),),
            (EvidenceChunk("S1-R001", "S1", "README.md", 1, 1, "Concepts"),),
            1, 0, (),
        )
        client = Mock()
        client.generate.side_effect = [
            ModelReply(True, "Nota [S1-R001]", "test"),
            ModelReply(True, "Nota [S1-R001]", "test"),
            *[ModelReply(True, f"Intervención {i} [S1-R001]\nESTADO COMPARTIDO: punto {i}", "test")
              for i in range(23)],
            ModelReply(True, "Plan IGRIS OS [S1-R001]", "test"),
            ModelReply(True, "Plan híbrido [S1-R001]", "test"),
        ]
        events = []

        with TemporaryDirectory() as directory, patch(
            "igris_os.evolution.dual_debate.read_github_repositories", return_value=(source,)
        ):
            result = run_repository_debate(
                client, [source.url], log_path=Path(directory) / "events.jsonl",
                model="test", max_turns=None,
                should_stop=lambda: len([event for event in events if event["type"] == "turn"]) >= 23,
                on_event=events.append)

        turns = [event for event in events if event["type"] == "turn"]
        self.assertEqual(result["state"], "complete")
        self.assertEqual(len(result["plans"]), 2)
        self.assertEqual(len(turns), 23)
        self.assertEqual(turns[-1]["persona"], "IGRIS OS")
        self.assertIn("ESTADO COMPARTIDO ACUMULADO", client.generate.call_args_list[3].args[0])


if __name__ == "__main__":
    unittest.main()
