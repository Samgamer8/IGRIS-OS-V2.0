from pathlib import Path

import pytest

from igris_os.application.project_development import (
    ProjectDevelopmentAdapter,
    StagedProject,
)
from igris_os.application.project_flow import ProjectStage
from igris_os.application.project_mission import ProjectMissionFactory
from igris_os.application.project_planning import ProjectMissionPlanner


def _planned(tmp_path: Path):
    mission = ProjectMissionFactory().create("Crea una aplicación", {
        "technology": "python",
        "delivery": "source",
        "destination": str(tmp_path / "delivery"),
        "acceptance": "las pruebas pasan",
    })
    return ProjectMissionPlanner().plan(mission)


class FakeStagingDeveloper:
    def __init__(self, root: Path):
        self.root = root

    def stage(self, mission):
        self.root.mkdir(parents=True)
        (self.root / "main.py").write_text("print('ok')\n", encoding="utf-8")
        return StagedProject(self.root, ("main.py",))


def test_development_records_staging_without_delivery(tmp_path):
    (tmp_path / "delivery").mkdir()
    planned = _planned(tmp_path)
    root = tmp_path / "workspace" / ".staging" / "candidate"
    adapter = ProjectDevelopmentAdapter(
        tmp_path / "workspace", FakeStagingDeveloper(root))

    result = adapter.develop(planned)

    assert result.mission.mission.flow.next_stage is ProjectStage.TEST
    assert result.staging.root == root.resolve()
    assert "1 archivos" in result.mission.mission.flow.evidence[-1].summary
    assert not (tmp_path / "delivery" / planned.plan.project_name).exists()
    assert planned.mission.flow.next_stage is ProjectStage.DEVELOP


def test_development_rejects_unplanned_mission(tmp_path):
    mission = ProjectMissionFactory().create("Crea una aplicación")
    fake_planned = type("Plan", (), {"mission": mission, "plan": object()})()
    adapter = ProjectDevelopmentAdapter(
        tmp_path, FakeStagingDeveloper(tmp_path / ".staging" / "candidate"))

    with pytest.raises(ValueError, match="no está lista"):
        adapter.develop(fake_planned)


def test_development_rejects_artifacts_outside_staging(tmp_path):
    (tmp_path / "delivery").mkdir()
    planned = _planned(tmp_path)
    adapter = ProjectDevelopmentAdapter(
        tmp_path / "workspace",
        FakeStagingDeveloper(tmp_path / "outside"))

    with pytest.raises(ValueError, match="staging aislado"):
        adapter.develop(planned)
