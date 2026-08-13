import json

from igris_os.ai import ModelReply
from igris_os.programming import MultiLanguageDeveloper
from igris_os.programming.languages import LanguageCheck


class FakeClient:
    def generate(self, prompt, model):
        package = {"name": "demo_js", "source": "console.log('IGRIS');",
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
    assert (project / "VERIFICATION.json").is_file()


def test_multilang_developer_requires_confirmation(tmp_path):
    result = MultiLanguageDeveloper(
        FakeClient(), tmp_path, "coder").develop("demo", "rust")
    assert not result.ok
