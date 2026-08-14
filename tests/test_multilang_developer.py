import json

from igris_os.ai import ModelReply
from igris_os.programming import MultiLanguageDeveloper
from igris_os.programming.languages import LanguageCheck


class FakeClient:
    def generate(self, prompt, model):
        package = {"name": "demo_js", "source": "console.log('IGRIS');",
                   "tests": "if (2 + 2 !== 4) throw new Error('fallo');",
                   "readme": "node main.js"}
        return ModelReply(True, json.dumps(package), model)


def test_multilang_developer_delivers_verified_project(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "igris_os.programming.multilang.LanguageVerifier.check",
        lambda self, language, source: LanguageCheck(True, True, "Sintaxis valida"))
    result = MultiLanguageDeveloper(
        FakeClient(), tmp_path, "coder").develop(
            "crea una demo", "javascript", confirmed=True)
    assert result.ok
    project = tmp_path / "projects" / "demo_js"
    assert (project / "main.js").is_file()
    assert (project / "test.js").is_file()
    assert (project / "VERIFICATION.json").is_file()
    evidence = json.loads(
        (project / "VERIFICATION.json").read_text(encoding="utf-8"))
    assert evidence["tests_syntax_valid"]
    assert evidence["tests_executed"] is False


def test_multilang_developer_requires_confirmation(tmp_path):
    result = MultiLanguageDeveloper(
        FakeClient(), tmp_path, "coder").develop("demo", "rust")
    assert not result.ok


def test_javascript_dangerous_operations_are_blocked(tmp_path, monkeypatch):
    class DangerousClient:
        def generate(self, prompt, model):
            return ModelReply(True, json.dumps({
                "name": "unsafe", "source": "require('child_process')",
                "tests": "console.log('x')"}), model)

    monkeypatch.setattr(
        "igris_os.programming.multilang.LanguageVerifier.check",
        lambda self, language, source: LanguageCheck(True, True, "ok"))
    result = MultiLanguageDeveloper(
        DangerousClient(), tmp_path, "coder").develop(
            "demo", "javascript", confirmed=True, attempts=1)
    assert not result.ok
    assert "peligrosa" in result.message


class TypeScriptClient:
    def generate(self, prompt, model):
        package = {"name": "demo_ts",
                   "source": "const value: number = 2 + 2;\nexport default value;",
                   "tests": "const other: string = 'ok';\nexport {};",
                   "readme": "npx tsc main.ts"}
        return ModelReply(True, json.dumps(package), model)


def test_multilang_developer_delivers_typescript_project(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "igris_os.programming.multilang.LanguageVerifier.check",
        lambda self, language, source: LanguageCheck(True, True, "Sintaxis valida"))
    result = MultiLanguageDeveloper(
        TypeScriptClient(), tmp_path, "coder").develop(
            "crea una utilidad", "typescript", confirmed=True)
    assert result.ok
    project = tmp_path / "projects" / "demo_ts"
    assert (project / "main.ts").is_file()
    assert (project / "test.ts").is_file()
    evidence = json.loads(
        (project / "VERIFICATION.json").read_text(encoding="utf-8"))
    assert evidence["language"] == "typescript"
    assert evidence["tests_syntax_valid"] is None
