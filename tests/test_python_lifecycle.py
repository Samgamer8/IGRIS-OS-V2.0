import json
from pathlib import Path

import pytest

from igris_os.application.python_lifecycle import build_python_project_lifecycle
from igris_os.programming.multi_file_developer import MultiFileDevelopmentResult


class DeterministicDeveloper:
    def __init__(self, workspace: Path):
        self.workspace = workspace

    def develop(self, objective, *, confirmed, componentized):
        assert confirmed and componentized
        root = self.workspace / ".staging" / "inventory"
        root.mkdir(parents=True)
        (root / "inventory.py").write_text(
            "def add(items, name):\n    return [*items, name]\n",
            encoding="utf-8")
        (root / "test_inventory.py").write_text(
            "from inventory import add\n\n"
            "def test_add():\n    assert add([], 'cable') == ['cable']\n",
            encoding="utf-8")
        (root / "VERIFICATION.json").write_text(json.dumps({
            "tests_passed": True,
        }), encoding="utf-8")
        return MultiFileDevelopmentResult(
            True, "verificado", root,
            ("inventory.py", "test_inventory.py"))


def _answers(destination: Path):
    return {
        "technology": "python", "delivery": "source",
        "destination": str(destination),
        "acceptance": "añadir artículos; pruebas pasan",
    }


def test_python_lifecycle_runs_real_tests_retest_and_delivery(tmp_path):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "delivery"
    destination.mkdir()
    lifecycle = build_python_project_lifecycle(
        None, workspace, "fake",
        developer=DeterministicDeveloper(workspace))

    result = lifecycle.execute(
        "Crea un inventario", _answers(destination),
        delivery_authorized=True)

    assert result.mission.mission.mission.mission.mission.flow.complete
    assert (result.destination / "inventory.py").is_file()
    assert (result.destination / "test_inventory.py").is_file()
    assert (result.destination / "VERIFICATION.json").is_file()


def test_python_lifecycle_keeps_delivery_blocked_without_authorization(tmp_path):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "delivery"
    destination.mkdir()
    lifecycle = build_python_project_lifecycle(
        None, workspace, "fake",
        developer=DeterministicDeveloper(workspace))

    with pytest.raises(PermissionError, match="autorización explícita"):
        lifecycle.execute("Crea un inventario", _answers(destination))

    assert not (destination / "Crea_un_inventario").exists()
