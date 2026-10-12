import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from igris_os.ai import ModelReply
from igris_os.delegation.contract import DelegatedResult, DelegatedTask
from igris_os.programming.local_team import LocalProgrammingTeam
from igris_os.security.sandbox import SandboxRun


class LocalProgrammingTeamTests(unittest.TestCase):
    def test_roles_run_in_sequence_and_require_independent_validation(self):
        with TemporaryDirectory() as directory:
            client = Mock()
            client.generate_json.return_value = ModelReply(
                True,
                json.dumps({"steps": ["Implementar"], "acceptance": ["Funciona"],
                            "risks": [], "needs_clarification": False}),
                "deepseek-r1:8b",
            )
            programmer_result = DelegatedResult(
                True, "ok", changed_files=("main.py",), verified=True)
            programmer = Mock()
            programmer.run.return_value = programmer_result
            verifier = Mock()
            verifier.run.return_value = SandboxRun(0, "ok", "", sandboxed=True)
            task = DelegatedTask(
                "Crear funcionalidad", Path(directory), verify_command=("python", "-m", "pytest"))

            with patch("igris_os.programming.local_team.OllamaSpecialist",
                       return_value=programmer) as specialist_class:
                result = LocalProgrammingTeam(client, validator=verifier).run(task)

            self.assertTrue(result.success)
            specialist_class.assert_called_once_with(
                model="qwen2.5-coder:7b", client=client)
            programmer.run.assert_called_once()
            verifier.run.assert_called_once()
            self.assertTrue(result.validation.sandboxed)

    def test_missing_verification_command_fails_before_model_call(self):
        with TemporaryDirectory() as directory:
            client = Mock()
            task = DelegatedTask("Crear funcionalidad", Path(directory))
            result = LocalProgrammingTeam(client).run(task)
            self.assertFalse(result.success)
            self.assertIn("verificación", result.message)
            client.generate_json.assert_not_called()

    def test_invalid_director_plan_stops_before_programmer(self):
        with TemporaryDirectory() as directory:
            client = Mock()
            client.generate_json.return_value = ModelReply(True, "{}", "test")
            task = DelegatedTask(
                "Crear funcionalidad", Path(directory), verify_command=("python", "-m", "pytest"))
            with patch("igris_os.programming.local_team.OllamaSpecialist") as programmer:
                result = LocalProgrammingTeam(client).run(task)
            self.assertFalse(result.success)
            self.assertEqual(result.message, "Director devolvió un plan inválido")
            programmer.assert_not_called()

    def test_failed_independent_validation_rejects_delivery(self):
        with TemporaryDirectory() as directory:
            client = Mock()
            client.generate_json.return_value = ModelReply(
                True,
                json.dumps({"steps": ["Implementar"], "acceptance": ["Funciona"],
                            "risks": [], "needs_clarification": False}), "test")
            programmer = Mock()
            programmer.run.return_value = DelegatedResult(
                True, "ok", changed_files=("main.py",), verified=True)
            validator = Mock()
            validator.run.return_value = SandboxRun(1, "", "fallo")
            task = DelegatedTask(
                "Crear funcionalidad", Path(directory), verify_command=("python", "-m", "pytest"))
            with patch("igris_os.programming.local_team.OllamaSpecialist",
                       return_value=programmer):
                result = LocalProgrammingTeam(client, validator=validator).run(task)
            self.assertFalse(result.success)
            self.assertEqual(result.message, "Validador independiente rechazó la entrega")


if __name__ == "__main__":
    unittest.main()
