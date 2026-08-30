import json

from igris_os.ai import ModelReply
from igris_os.programming.sequential_developer import SequentialPythonComponentDeveloper


class SequentialClient:
    def generate_json(self, prompt, model, schema):
        if "ARCHIVO: model.py" in prompt:
            content = "class Item:\n    def __init__(self, name):\n        self.name = name\n"
        elif "ARCHIVO: service.py" in prompt:
            content = "from model import Item\n\ndef create(name):\n    return Item(name)\n"
        elif "ARCHIVO: main.py" in prompt:
            content = "from service import create\n\ndef main():\n    return create('ok').name\n"
        else:
            assert "ARCHIVOS YA ESCRITOS" in prompt
            content = (
                "from service import create\n\ndef test_create():\n"
                "    assert create('ok').name == 'ok'\n")
        return ModelReply(True, json.dumps({"content": content}), model)


def test_sequential_developer_writes_components_in_dependency_order(tmp_path):
    result = SequentialPythonComponentDeveloper(
        SequentialClient(), tmp_path, "test").develop(
            "crea una aplicación", confirmed=True)

    assert result.ok
    assert result.project is not None
    assert result.files == ("model.py", "service.py", "main.py", "test_service.py")
    assert (result.project / "VERIFICATION.json").is_file()


def test_sequential_test_prompt_requires_self_contained_fixtures(tmp_path):
    class PromptClient(SequentialClient):
        prompts = []

        def generate_json(self, prompt, model, schema):
            self.prompts.append(prompt)
            return super().generate_json(prompt, model, schema)

    client = PromptClient()
    result = SequentialPythonComponentDeveloper(
        client, tmp_path, "test").develop("crea una aplicación", confirmed=True)
    assert result.ok
    test_prompt = next(prompt for prompt in client.prompts if "ARCHIVO: test_service.py" in prompt)
    assert "pruebas deben ser autocontenidas" in test_prompt