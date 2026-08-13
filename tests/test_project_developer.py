import json

from igris_os.ai import ModelReply
from igris_os.programming import PythonProjectDeveloper


class FakeClient:
    def generate(self, prompt, model):
        package = {
            "name": "calculadora",
            "source": "def add(a, b):\n    return a + b\n",
            "tests": "import unittest\nfrom solution import add\n"
                     "class T(unittest.TestCase):\n"
                     "    def test_add(self): self.assertEqual(add(2,3),5)\n",
            "readme": "Calculadora verificada",
        }
        return ModelReply(True, json.dumps(package), model)


def test_developer_delivers_verified_project(tmp_path):
    result = PythonProjectDeveloper(FakeClient(), tmp_path, "fake").develop(
        "crea calculadora", confirmed=True)
    assert result.ok
    assert (tmp_path / "projects" / "calculadora" / "VERIFICATION.json").exists()


def test_developer_requires_confirmation(tmp_path):
    result = PythonProjectDeveloper(FakeClient(), tmp_path, "fake").develop("x")
    assert not result.ok
