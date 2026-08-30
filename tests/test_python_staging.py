from pathlib import Path

import pytest

from igris_os.application.project_mission import ProjectMissionFactory
from igris_os.application.project_planning import ProjectMissionPlanner
from igris_os.application.python_staging import PythonMultiFileStagingAdapter
from igris_os.programming.multi_file_developer import MultiFileDevelopmentResult


class FakeDeveloper:
    def __init__(self, result: MultiFileDevelopmentResult):
        self.result = result
        self.objective = ""

    def develop(self, objective, *, confirmed, componentized):
        assert confirmed
        assert componentized
        self.objective = objective
        return self.result


def _planned(tmp_path: Path, technology: str = "python"):
    destination = tmp_path / "delivery"
    destination.mkdir()
    mission = ProjectMissionFactory().create("Crea un inventario", {
        "technology": technology, "delivery": "source",
        "destination": str(destination),
        "acceptance": "crear artículos; listar artículos",
        "constraints": "sin red",
    })
    return ProjectMissionPlanner().plan(mission)


def test_python_adapter_returns_verified_multifile_staging(tmp_path):
    root = tmp_path / "workspace" / ".staging" / "inventory"
    root.mkdir(parents=True)
    for name in ("app.py", "test_app.py", "VERIFICATION.json"):
        (root / name).write_text("{}\n" if name.endswith("json") else "pass\n")
    developer = FakeDeveloper(MultiFileDevelopmentResult(
        True, "verificado", root, ("app.py", "test_app.py")))

    result = PythonMultiFileStagingAdapter(
        None, tmp_path / "workspace", "fake",
        developer=developer).stage(_planned(tmp_path))

    assert result.root == root.resolve()
    assert result.changed_files == ("app.py", "test_app.py")
    assert "crear artículos" in developer.objective
    assert "PLAN APROBADO" in developer.objective
    assert "sin red" in developer.objective


def test_python_adapter_rejects_missing_verification(tmp_path):
    root = tmp_path / "workspace" / ".staging" / "inventory"
    root.mkdir(parents=True)
    (root / "app.py").write_text("pass\n", encoding="utf-8")
    developer = FakeDeveloper(MultiFileDevelopmentResult(
        True, "sin evidencia", root, ("app.py",)))

    with pytest.raises(ValueError, match="VERIFICATION.json"):
        PythonMultiFileStagingAdapter(
            None, tmp_path / "workspace", "fake",
            developer=developer).stage(_planned(tmp_path))


def test_python_adapter_rejects_other_technology_before_development(tmp_path):
    developer = FakeDeveloper(MultiFileDevelopmentResult(False, "no llamado"))

    with pytest.raises(ValueError, match="no admite"):
        PythonMultiFileStagingAdapter(
            None, tmp_path / "workspace", "fake",
            developer=developer).stage(_planned(tmp_path, "godot"))

    assert developer.objective == ""
