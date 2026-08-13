import shutil

import pytest

from igris_os.games import GodotProjectFactory
from igris_os.multimedia import MediaEngine
from igris_os.programming import LanguageVerifier


def test_godot_project_requires_confirmation(tmp_path):
    factory = GodotProjectFactory(tmp_path)
    with pytest.raises(PermissionError):
        factory.create("Juego")
    project = factory.create("Juego IGRIS", confirmed=True)
    assert factory.validate(project)


def test_javascript_syntax_when_node_available(tmp_path):
    source = tmp_path / "app.js"
    source.write_text("const value = 2 + 2;\n", encoding="utf-8")
    result = LanguageVerifier().check("javascript", source)
    assert result.ok if shutil.which("node") else not result.available


def test_unknown_language_is_controlled(tmp_path):
    result = LanguageVerifier().check("unknown", tmp_path / "x")
    assert not result.ok and not result.available


def test_multimedia_confirmation_and_discovery(tmp_path):
    engine = MediaEngine(tmp_path)
    result = engine.transcode(tmp_path / "missing.mp4", "out.mp4")
    assert not result.ok
    assert engine.available == bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
