from pathlib import Path

from igris_os.games import GameDevelopmentResult
from igris_os.capabilities.creation import _godot


def test_godot_delivery_copies_project_to_selected_folder(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    destination = tmp_path / "delivery"
    destination.mkdir()

    result = _godot({
        "workspace": str(workspace),
        "name": "Ajedrez Medieval",
        "genre": "top_down",
        "delivery_root": str(destination),
        "delivery_type": "source",
        "brief": {
            "objective": "juego de ajedrez",
            "delivery_type": "source",
        },
    })

    project = destination / "Ajedrez_Medieval"
    assert result.ok
    assert Path(result.data["project"]) == project
    assert (project / "PROJECT_BRIEF.json").is_file()


def test_full_code_failure_returns_diagnostics_without_delivering(tmp_path, monkeypatch):
    class FailedDeveloper:
        def __init__(self, *args, **kwargs):
            pass

        def develop(self, *args, **kwargs):
            return GameDevelopmentResult(
                False, "Código incompleto", diagnostics=("main.gd missing",))

    monkeypatch.setattr(
        "igris_os.capabilities.creation.GodotGameDeveloper", FailedDeveloper)
    result = _godot({
        "workspace": str(tmp_path), "name": "Fallido",
        "generate_full_code": True,
    })

    assert not result.ok
    assert result.code == "GAME_CODE_GENERATION_FAILED"
    assert result.data["diagnostics"] == ["main.gd missing"]