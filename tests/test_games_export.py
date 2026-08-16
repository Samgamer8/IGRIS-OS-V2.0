from pathlib import Path

import pytest

from igris_os.games import GodotExporter, GodotProjectFactory, GodotRuntime

pytestmark = pytest.mark.skipif(
    not (GodotRuntime().available and GodotExporter().templates_available()),
    reason="Godot o plantillas de exportacion no disponibles")


def test_export_produces_verified_exe(tmp_path):
    project = GodotProjectFactory(tmp_path).create("Export", confirmed=True)
    result = GodotExporter().export(
        project, tmp_path / "build" / "juego.exe",
        confirmed=True, launch_check=False)
    assert result.ok
    assert result.verified
    assert Path(result.executable).is_file()
    assert result.size > 1_000_000


def test_export_requires_confirmation(tmp_path):
    project = GodotProjectFactory(tmp_path).create("Export", confirmed=True)
    result = GodotExporter().export(project, tmp_path / "juego.exe")
    assert not result.ok


def test_verify_exe_rejects_non_pe(tmp_path):
    fake = tmp_path / "falso.exe"
    fake.write_bytes(b"no soy un ejecutable" * 100000)
    ok, message = GodotExporter.verify_exe(fake)
    assert not ok
    assert "PE" in message


def test_verify_exe_rejects_missing_file():
    ok, _ = GodotExporter.verify_exe("no_existe.exe")
    assert not ok
