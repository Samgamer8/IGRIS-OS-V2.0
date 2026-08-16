from pathlib import Path

import pytest

from igris_os.games import GameVerifier, GodotProjectFactory, GodotRuntime

pytestmark = pytest.mark.skipif(
    not GodotRuntime().available, reason="Godot no disponible")


def test_playtest_boots_and_captures(tmp_path):
    project = GodotProjectFactory(tmp_path).create("Playtest", confirmed=True)
    result = GameVerifier().playtest(project, capture_dir=tmp_path)
    assert result.ok
    assert result.boot_ok
    assert result.visual_ok
    assert Path(result.capture_path).is_file()


def test_playtest_matches_its_own_reference(tmp_path):
    project = GodotProjectFactory(tmp_path).create("Playtest", confirmed=True)
    reference = tmp_path / "referencia.png"
    GodotRuntime().capture(project, reference, frames=15)
    result = GameVerifier().playtest(
        project, capture_dir=tmp_path, reference=reference)
    assert result.ok
    assert result.reference_ok is True
    assert result.similarity > 0.9


def test_playtest_rejects_missing_project(tmp_path):
    result = GameVerifier().playtest(tmp_path / "no_existe")
    assert not result.ok
