from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from igris_os.ai.ollama import ModelReply
from igris_os.programming.multi_file_developer import PythonMultiFileDeveloper


BROKEN_PACKAGE = {
    "name": "contador",
    "files": {
        "model.py": "VALUE = 0\n",
        "service.py": (
            "from model import VALUE\n\n"
            "def increment(value):\n"
            "    return value + 1\n"
        ),
        "main.py": (
            "from service import increment\n\n"
            "def main():\n"
            "    print(increment(0))\n\n"
            "if __name__ == '__main__':\n"
            "    main()\n"
        ),
        "test_service.py": (
            "from service import increment\n\n"
            "def test_increment(:\n"  # <- error de sintaxis deliberado
            "    assert increment(0) == 1\n"
        ),
    },
    "readme": "Contador simple",
}

FIXED_TEST_FILE = (
    "from service import increment\n\n"
    "def test_increment():\n"
    "    assert increment(0) == 1\n"
)


class MultiFileDeveloperSyntaxRepairTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_whole_package_is_validated_before_any_file_is_written(self):
        """Un error de sintaxis en un solo archivo no debe dejar escrituras
        parciales en disco: la validacion ocurre antes de escribir nada."""
        client = Mock()
        client.generate_json.side_effect = [
            ModelReply(True, _as_json({"files": {"test_service.py": FIXED_TEST_FILE}}), "model"),
        ]
        developer = PythonMultiFileDeveloper(client, self.workspace, "model")

        package, errors = developer._ensure_valid_syntax(dict(BROKEN_PACKAGE), "model")

        self.assertEqual(errors, {})
        self.assertEqual(package["files"]["test_service.py"], FIXED_TEST_FILE)
        self.assertEqual(client.generate_json.call_count, 1)

    def test_repair_is_bounded_and_does_not_write_when_still_broken(self):
        client = Mock()
        still_broken = {"files": {"test_service.py": "def test_increment(:\n    pass\n"}}
        client.generate_json.side_effect = [
            ModelReply(True, _as_json(still_broken), "model"),
            ModelReply(True, _as_json(still_broken), "model"),
        ]
        developer = PythonMultiFileDeveloper(client, self.workspace, "model")

        package, errors = developer._ensure_valid_syntax(dict(BROKEN_PACKAGE), "model")

        self.assertIn("test_service.py", errors)
        self.assertEqual(client.generate_json.call_count,
                         PythonMultiFileDeveloper.MAX_SYNTAX_REPAIRS)
        self.assertFalse((self.workspace / ".staging").exists())

    def test_develop_writes_only_after_syntax_repair_succeeds(self):
        client = Mock()
        client.generate_json.side_effect = [
            ModelReply(True, _as_json(BROKEN_PACKAGE), "model"),
            ModelReply(True, _as_json({"files": {"test_service.py": FIXED_TEST_FILE}}), "model"),
        ]
        developer = PythonMultiFileDeveloper(client, self.workspace, "model")

        result = developer.develop("contador simple", confirmed=True, attempts=1)

        self.assertTrue(result.ok, result.diagnostics)
        self.assertTrue((result.project / "test_service.py").read_text(encoding="utf-8")
                        == FIXED_TEST_FILE)


def _as_json(payload):
    import json
    return json.dumps(payload, ensure_ascii=False)


if __name__ == "__main__":
    unittest.main()
