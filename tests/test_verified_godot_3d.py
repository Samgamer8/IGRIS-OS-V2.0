import json
import shutil
from pathlib import Path

import pytest

from igris_os.games.export import GodotExporter
from igris_os.games.verified_3d import VerifiedGodot3DFactory
from igris_os.games.verifier import GameVerifier


pytestmark = pytest.mark.skipif(
    shutil.which("godot") is None, reason="Godot no disponible")


def test_verified_3d_project_boots_renders_and_exports(tmp_path: Path):
    project = VerifiedGodot3DFactory(tmp_path).create(
        "IGRIS 3D RC", confirmed=True)

    playtest = GameVerifier().playtest(project, tmp_path, frames=20)
    exported = GodotExporter().export(
        project, tmp_path / "build" / "igris_3d.exe",
        confirmed=True, launch_check=False)

    report = json.loads(
        (project / "VERIFICATION.json").read_text(encoding="utf-8"))
    assert report["dimension"] == "3D"
    assert report["godot_ok"] is True
    assert playtest.ok, playtest.message
    assert playtest.boot_ok
    assert playtest.visual_ok
    assert Path(playtest.capture_path).is_file()
    assert exported.ok, exported.message
    assert exported.verified
    assert Path(exported.executable).read_bytes()[:2] == b"MZ"


def test_verified_3d_requires_confirmation(tmp_path: Path):
    with pytest.raises(PermissionError):
        VerifiedGodot3DFactory(tmp_path).create("IGRIS 3D")
