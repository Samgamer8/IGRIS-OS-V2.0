from pathlib import Path

import pytest

from igris_os.application.project_development import (
    ProjectDevelopmentAdapter,
    StagedProject,
)
from igris_os.application.project_flow import ProjectStage
from igris_os.application.project_mission import ProjectMissionFactory
from igris_os.application.project_planning import ProjectMissionPlanner
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
    def __init__(self, evidence: ProjectTestEvidence):
        self.evidence = evidence

    def verify(self, mission):
        return self.evidence


def _developed(tmp_path: Path):
    destination = tmp_path / "delivery"
    destination.mkdir()
    mission = ProjectMissionFactory().create("Crea una aplicación", {
        "technology": "python",
        "delivery": "source",
        "destination": str(destination),
        "acceptance": "las pruebas pasan",
    })
    planned = ProjectMissionPlanner().plan(mission)
    root = tmp_path / "workspace" / ".staging" / "candidate"
    return ProjectDevelopmentAdapter(
        tmp_path / "workspace", FakeDeveloper(root)).develop(planned)


def test_testing_records_executed_success_without_delivery(tmp_path):
    developed = _developed(tmp_path)
    evidence = ProjectTestEvidence(
        True, True, ("python", "-m", "pytest", "-q"), "3 passed")

    result = ProjectTestingAdapter(FakeVerifier(evidence)).test(developed)

    assert result.mission.mission.mission.flow.next_stage is ProjectStage.REPAIR
    assert "python -m pytest -q" in (
        result.mission.mission.mission.flow.evidence[-1].summary)
    assert developed.mission.mission.flow.next_stage is ProjectStage.TEST
    destination = developed.mission.mission.contract.destination
    assert destination is not None
    assert not (destination / developed.mission.plan.project_name).exists()


@pytest.mark.parametrize("evidence, message", [
    (ProjectTestEvidence(False, False, (), "sin ejecutar"), "no fueron ejecutadas"),
    (ProjectTestEvidence(True, False, ("pytest",), "1 failed"), "fallaron"),
    (ProjectTestEvidence(True, True, (), "3 passed"), "comando ejecutado"),
])
def test_testing_rejects_unverifiable_evidence(tmp_path, evidence, message):
    developed = _developed(tmp_path)

    with pytest.raises(ValueError, match=message):
        ProjectTestingAdapter(FakeVerifier(evidence)).test(developed)

    assert developed.mission.mission.flow.next_stage is ProjectStage.TEST


def test_testing_rejects_mission_without_development(tmp_path):
    mission = ProjectMissionFactory().create("Crea una aplicación")
    fake = type("Developed", (), {
        "mission": type("Planned", (), {"mission": mission})(),
    })()

    with pytest.raises(ValueError, match="no está lista"):
        ProjectTestingAdapter(FakeVerifier(
            ProjectTestEvidence(True, True, ("pytest",), "ok"))).test(fake)
