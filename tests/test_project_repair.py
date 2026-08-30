from pathlib import Path

import pytest

from igris_os.application.project_development import (
    ProjectDevelopmentAdapter,
    StagedProject,
)
from igris_os.application.project_flow import ProjectStage
from igris_os.application.project_mission import ProjectMissionFactory
from igris_os.application.project_planning import ProjectMissionPlanner
from igris_os.application.project_repair import (
    ProjectRepairAdapter,
    ProjectRepairEvidence,
)
from igris_os.application.project_testing import (
    ProjectTestEvidence,
    ProjectTestingAdapter,
)


class FakeDeveloper:
    def __init__(self, root: Path):
        self.root = root

    def stage(self, mission):
        self.root.mkdir(parents=True)
        (self.root / "main.py").write_text("print('ok')\n", encoding="utf-8")
        return StagedProject(self.root, ("main.py",))


class FakeVerifier:
    def verify(self, mission):
        return ProjectTestEvidence(True, True, ("pytest", "-q"), "1 passed")


class FakeRepairer:
    def __init__(self, evidence: ProjectRepairEvidence):
        self.evidence = evidence

    def repair(self, mission):
        return self.evidence


def _tested(tmp_path: Path):
    destination = tmp_path / "delivery"
    destination.mkdir()
    mission = ProjectMissionFactory().create("Crea una aplicación", {
        "technology": "python", "delivery": "source",
        "destination": str(destination), "acceptance": "las pruebas pasan",
    })
    planned = ProjectMissionPlanner().plan(mission)
    root = tmp_path / "workspace" / ".staging" / "candidate"
    developed = ProjectDevelopmentAdapter(
        tmp_path / "workspace", FakeDeveloper(root)).develop(planned)
    return ProjectTestingAdapter(FakeVerifier()).test(developed)


def test_repair_records_verified_changes_without_delivery(tmp_path):
    tested = _tested(tmp_path)
    root = tested.mission.staging.root
    evidence = ProjectRepairEvidence(
        root, True, True, True, ("main.py",), "1 passed tras reparación")

    result = ProjectRepairAdapter(FakeRepairer(evidence)).repair(tested)

    assert result.mission.mission.mission.mission.flow.next_stage is ProjectStage.DELIVER
    assert "1 archivos" in (
        result.mission.mission.mission.mission.flow.evidence[-1].summary)
    assert tested.mission.mission.mission.flow.next_stage is ProjectStage.REPAIR
    destination = tested.mission.mission.mission.contract.destination
    assert destination is not None
    assert not (destination / tested.mission.mission.plan.project_name).exists()


@pytest.mark.parametrize("change, message", [
    ({"attempted": False}, "no fue ejecutada"),
    ({"successful": False}, "falló"),
    ({"tests_passed": False}, "pruebas posteriores"),
    ({"changed_files": ()}, "no registra archivos"),
])
def test_repair_rejects_unverified_evidence(tmp_path, change, message):
    tested = _tested(tmp_path)
    values = {
        "root": tested.mission.staging.root,
        "attempted": True, "successful": True, "tests_passed": True,
        "changed_files": ("main.py",), "summary": "ok",
    }
    values.update(change)

    with pytest.raises(ValueError, match=message):
        ProjectRepairAdapter(FakeRepairer(
            ProjectRepairEvidence(**values))).repair(tested)

    assert tested.mission.mission.mission.flow.next_stage is ProjectStage.REPAIR


def test_repair_rejects_different_staging(tmp_path):
    tested = _tested(tmp_path)
    outside = tmp_path / "workspace" / ".staging" / "other"
    outside.mkdir(parents=True)
    (outside / "main.py").write_text("print('bad')\n", encoding="utf-8")
    evidence = ProjectRepairEvidence(
        outside, True, True, True, ("main.py",), "ok")

    with pytest.raises(ValueError, match="salió del staging"):
        ProjectRepairAdapter(FakeRepairer(evidence)).repair(tested)
