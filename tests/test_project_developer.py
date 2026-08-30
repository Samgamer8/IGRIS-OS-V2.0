import json
import pytest

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


def test_developer_prompt_requires_critical_verification():
    from igris_os.programming.developer import PACKAGE_SCHEMA, SYSTEM

    assert "seguridad" in SYSTEM
    assert "rendimiento" in SYSTEM
    assert "mantenibilidad" in SYSTEM
    assert "tests" in SYSTEM
    assert "KISS" in SYSTEM
    assert "SOLID" in SYSTEM
    assert "placeholders" in SYSTEM
    assert set(PACKAGE_SCHEMA["required"]) == {"name", "source", "tests", "readme"}


def test_developer_uses_structured_generation_when_client_supports_it(tmp_path):
    class StructuredClient(FakeClient):
        used_schema = None

        def generate_json(self, prompt, model, schema):
            self.used_schema = schema
            return self.generate(prompt, model)

    client = StructuredClient()
    result = PythonProjectDeveloper(client, tmp_path, "fake").develop(
        "crea calculadora", confirmed=True)
    assert result.ok
    assert client.used_schema is not None


def test_package_rejects_truncated_source_and_tests():
    from igris_os.programming.developer import _package

    with pytest.raises(ValueError, match="truncado"):
        _package(json.dumps({
            "name": "broken",
            "source": "def collect():\n    value = 1 +",
            "tests": "def test_ok():\n    assert True\n",
        }))


def test_package_accepts_complete_additional_python_files():
    from igris_os.programming.developer import _package

    package = _package(json.dumps({
        "name": "multi",
        "source": "from helper import value\n",
        "tests": "def test_ok():\n    assert True\n",
        "files": {"helper.py": "value = 1\n"},
    }))
    assert package["files"]["helper.py"] == "value = 1\n"


def test_package_rejects_additional_path_escape():
    from igris_os.programming.developer import _package

    with pytest.raises(ValueError, match="Ruta"):
        _package(json.dumps({
            "name": "escape",
            "source": "value = 1\n",
            "tests": "def test_ok():\n    assert True\n",
            "files": {"../escape.py": "value = 2\n"},
        }))


def test_package_recovers_code_when_model_forgets_to_escape_f_string_quotes():
    from igris_os.programming.developer import _package

    package = _package('''{
        "name": "tasks",
        "source": "def show(data):\\n    return f'Value: {data[\"name\"]}'",
        "tests": "from tasks import show\\n\\ndef test_show():\\n    assert show({'name': 'ok'}) == 'Value: ok'",
        "readme": "usage"
    }''')

    assert "data[\"name\"]" in package["source"]
    assert "from tasks import show" in package["tests"]


def test_package_recovers_source_and_tests_from_two_python_blocks():
    from igris_os.programming.developer import _package

    package = _package("""Explicación que no forma parte de la entrega.
```python
class Tasks:
    def add(self, value):
        return value
```
```python
from solution import Tasks

def test_add():
    assert Tasks().add("ok") == "ok"
```
""")

    assert "class Tasks" in package["source"]
    assert "test_add" in package["tests"]


def test_developer_delivers_verified_project(tmp_path):
    result = PythonProjectDeveloper(FakeClient(), tmp_path, "fake").develop(
        "crea calculadora", confirmed=True)
    assert result.ok
    assert (tmp_path / "projects" / "calculadora" / "VERIFICATION.json").exists()


def test_developer_requires_confirmation(tmp_path):
    result = PythonProjectDeveloper(FakeClient(), tmp_path, "fake").develop("x")
    assert not result.ok


def test_developer_reports_granular_progress(tmp_path):
    events = []
    result = PythonProjectDeveloper(FakeClient(), tmp_path, "fake").develop(
        "crea calculadora", confirmed=True,
        on_progress=lambda pct, msg: events.append((pct, msg)))
    assert result.ok
    assert events
    assert all(1 <= pct <= 100 for pct, _ in events)
    assert events[-1][0] >= 90
