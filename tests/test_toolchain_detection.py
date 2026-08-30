from pathlib import Path

from igris_os.programming import Language, MultiLanguageVerifier


def test_detect_project_finds_python_without_network(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("print('ok')\n", encoding="utf-8")

    detected = MultiLanguageVerifier(tmp_path).detect_project()

    python = next(item for item in detected if item.language is Language.PYTHON)
    assert python.available
    assert python.requires_network is False
    assert "pyproject.toml" in python.markers


def test_detect_project_marks_typescript_as_network_sensitive(tmp_path):
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "main.ts").write_text("const value: number = 1;\n", encoding="utf-8")

    detected = MultiLanguageVerifier(tmp_path).detect_project()

    typescript = next(item for item in detected if item.language is Language.TYPESCRIPT)
    assert typescript.requires_network
    assert (Path(typescript.executable).stem.casefold() == "npx"
            if typescript.executable else not typescript.available)


def test_detect_project_returns_empty_for_missing_root(tmp_path):
    assert MultiLanguageVerifier(tmp_path / "missing").detect_project() == ()