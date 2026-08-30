import json

from igris_os.ai import ModelReply
from igris_os.programming.multi_file_developer import PythonMultiFileDeveloper


class MultiFileClient:
    def generate_json(self, prompt, model, schema):
        package = {"name": "inventory", "readme": "Uso local.", "files": {
            "inventory.py": "def add(items, name):\n    return [*items, name]\n",
            "test_inventory.py": (
                "from inventory import add\n\n"
                "def test_add():\n    assert add([], 'cable') == ['cable']\n"),
        }}
        return ModelReply(True, json.dumps(package), model)


def test_multi_file_developer_writes_and_tests_package(tmp_path):
    result = PythonMultiFileDeveloper(
        MultiFileClient(), tmp_path, "test").develop("crea inventario", confirmed=True)

    assert result.ok
    assert result.project is not None
    assert set(result.files) == {"inventory.py", "test_inventory.py"}
    assert (result.project / "VERIFICATION.json").is_file()


def test_multi_file_developer_allows_only_readme_as_non_python_file(tmp_path):
    class ReadmeClient:
        def generate_json(self, prompt, model, schema):
            return ModelReply(True, json.dumps({"name": "readme", "readme": "", "files": {
                "app.py": "def ok():\n    return True\n",
                "test_app.py": "from app import ok\n\ndef test_ok():\n    assert ok()\n",
                "README.md": "# Uso\n",
            }}), model)

    result = PythonMultiFileDeveloper(
        ReadmeClient(), tmp_path, "test").develop("crea algo", confirmed=True)
    assert result.ok
    assert "README.md" in result.files


def test_multi_file_developer_rejects_package_without_tests(tmp_path):
    class NoTestsClient:
        def generate_json(self, prompt, model, schema):
            return ModelReply(True, json.dumps({"name": "bad", "readme": "", "files": {
                "main.py": "value = 1\n", "other.py": "value = 2\n"}}), model)

    result = PythonMultiFileDeveloper(
        NoTestsClient(), tmp_path, "test").develop("crea algo", confirmed=True, attempts=1)
    assert not result.ok
    assert "Falta test" in result.diagnostics[0]


def test_multi_file_developer_retries_in_new_staging_directory(tmp_path):
    class RetryingClient:
        calls = 0

        def generate_json(self, prompt, model, schema):
            self.calls += 1
            source = "def add(a, b):\n    return 0\n" if self.calls == 1 else (
                "def add(a, b):\n    return a + b\n")
            return ModelReply(True, json.dumps({"name": "retry", "readme": "", "files": {
                "app.py": source,
                "test_app.py": "from app import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
            }}), model)

    result = PythonMultiFileDeveloper(
        RetryingClient(), tmp_path, "test").develop("crea suma", confirmed=True, attempts=2)
    assert result.ok
    assert result.project is not None
    assert result.project.name == "retry_2"


def test_multi_file_developer_retries_after_syntax_error(tmp_path):
    class SyntaxRetryClient:
        calls = 0

        def generate_json(self, prompt, model, schema):
            self.calls += 1
            tests = "def test_bad(:\n" if self.calls == 1 else (
                "from app import ok\n\ndef test_ok():\n    assert ok()\n")
            return ModelReply(True, json.dumps({"name": "syntax", "readme": "", "files": {
                "app.py": "def ok():\n    return True\n", "test_app.py": tests,
            }}), model)

    result = PythonMultiFileDeveloper(
        SyntaxRetryClient(), tmp_path, "test").develop("crea algo", confirmed=True, attempts=2)
    assert result.ok


def test_componentized_developer_requires_planned_modules(tmp_path):
    class MissingModuleClient:
        def generate_json(self, prompt, model, schema):
            return ModelReply(True, json.dumps({"name": "missing", "readme": "", "files": {
                "model.py": "class Item: pass\n",
                "test_service.py": "def test_ok():\n    assert True\n",
            }}), model)

    result = PythonMultiFileDeveloper(
        MissingModuleClient(), tmp_path, "test").develop(
            "crea una aplicación", confirmed=True, attempts=1, componentized=True)
    assert not result.ok
    assert "Faltan componentes" in result.diagnostics[0]


def test_componentized_retry_includes_test_expectation_diagnostic(tmp_path):
    class RecordingClient:
        prompts = []
        calls = 0

        def generate_json(self, prompt, model, schema):
            self.prompts.append(prompt)
            self.calls += 1
            expected = "2" if self.calls == 1 else "3"
            return ModelReply(True, json.dumps({"name": "counts", "readme": "", "files": {
                "model.py": "def count(text):\n    return len(text.split())\n",
                "service.py": "from model import count\n\ndef stats(text):\n    return count(text)\n",
                "main.py": "from service import stats\n\ndef main():\n    print(stats('a b c'))\n",
                "test_service.py": (
                    "from service import stats\n\ndef test_stats():\n"
                    f"    assert stats('a b c') == {expected}\n"),
            }}), model)

    client = RecordingClient()
    result = PythonMultiFileDeveloper(
        client, tmp_path, "test").develop(
            "crea estadísticas", confirmed=True, attempts=2, componentized=True)
    assert result.ok
    assert "expectativa de prueba incorrecta" in client.prompts[1]


def test_componentized_retry_includes_previous_package(tmp_path):
    class RecordingClient:
        prompts = []
        calls = 0

        def generate_json(self, prompt, model, schema):
            self.prompts.append(prompt)
            self.calls += 1
            expected = "0" if self.calls == 1 else "1"
            return ModelReply(True, json.dumps({"name": "repair", "readme": "", "files": {
                "model.py": "def count(items):\n    return len(items)\n",
                "service.py": "from model import count\n\ndef total(items):\n    return count(items)\n",
                "main.py": "from service import total\n\ndef main():\n    print(total(['x']))\n",
                "test_service.py": (
                    "from service import total\n\ndef test_total():\n"
                    f"    assert total(['x']) == {expected}\n"),
            }}), model)

    client = RecordingClient()
    result = PythonMultiFileDeveloper(
        client, tmp_path, "test").develop(
            "crea componentes", confirmed=True, attempts=2, componentized=True)
    assert result.ok
    assert "PAQUETE ANTERIOR A REPARAR" in client.prompts[1]
    assert '"model.py"' in client.prompts[1]

def test_domain_validator_feeds_rejection_back_into_repair_loop(tmp_path):
    class DomainRepairClient:
        calls = 0
        prompts = []

        def generate_json(self, prompt, model, schema):
            self.prompts.append(prompt)
            self.calls += 1
            source = (
                "MODE = 'placeholder'\n" if self.calls == 1
                else "MODE = 'real'\n"
            )
            package = {"name": "domain", "readme": "Uso.", "files": {
                "app.py": source,
                "test_app.py": "from app import MODE\n\ndef test_mode():\n    assert MODE\n",
            }}
            return ModelReply(True, json.dumps(package), model)

    client = DomainRepairClient()
    result = PythonMultiFileDeveloper(client, tmp_path, "test").develop(
        "crea entrega real", confirmed=True, attempts=2,
        domain_validator=lambda root: (
            "forbidden: placeholder"
            if "placeholder" in (root / "app.py").read_text(encoding="utf-8")
            else ""
        ),
    )

    assert result.ok
    assert client.calls == 2
    assert "forbidden: placeholder" in client.prompts[1]
    assert "PAQUETE ANTERIOR A REPARAR" in client.prompts[1]

def test_repeated_domain_failure_escalates_to_fallback_model(tmp_path):
    class AdaptiveClient:
        models = []

        def generate_json(self, prompt, model, schema):
            self.models.append(model)
            mode = "placeholder" if model == "primary" else "real"
            package = {"name": "adaptive", "readme": "Uso.", "files": {
                "app.py": f"MODE = {mode!r}\n",
                "test_app.py": "from app import MODE\n\ndef test_mode():\n    assert MODE\n",
            }}
            return ModelReply(True, json.dumps(package), model)

    client = AdaptiveClient()
    result = PythonMultiFileDeveloper(client, tmp_path, "primary").develop(
        "crea entrega real", confirmed=True, attempts=3,
        fallback_models=("fallback",),
        domain_validator=lambda root: (
            "forbidden: placeholder"
            if "placeholder" in (root / "app.py").read_text(encoding="utf-8")
            else ""
        ),
    )

    assert result.ok
    assert client.models == ["primary", "primary", "fallback"]
    assert result.models_tried == ("primary", "fallback")
    verification = json.loads(
        (result.project / "VERIFICATION.json").read_text(encoding="utf-8")
    )
    assert verification["model"] == "fallback"
    assert verification["models_tried"] == ["primary", "fallback"]