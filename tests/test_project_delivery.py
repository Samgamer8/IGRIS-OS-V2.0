from pathlib import Path

import pytest

from igris_os.application.project_delivery import ProjectDeliveryAdapter
from igris_os.application.project_development import (
    ProjectDevelopmentAdapter,
    StagedProject,
)
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
    def repair(self, mission):
        return ProjectRepairEvidence(
            mission.mission.staging.root, True, True, True,
            ("main.py",), "1 passed tras reparación")


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


def _repaired(tmp_path: Path):
    return ProjectRepairAdapter(FakeRepairer()).repair(_tested(tmp_path))


def test_delivery_copies_verified_staging_and_completes_flow(tmp_path):
    repaired = _repaired(tmp_path)

    result = ProjectDeliveryAdapter().deliver(repaired, authorized=True)

    assert result.mission.mission.mission.mission.mission.flow.complete
    assert (result.destination / "main.py").read_text(
        encoding="utf-8") == "print('ok')\n"
    assert repaired.mission.mission.mission.mission.flow.next_stage.value == "deliver"


def test_delivery_requires_explicit_authorization(tmp_path):
    repaired = _repaired(tmp_path)

    with pytest.raises(PermissionError, match="autorización explícita"):
        ProjectDeliveryAdapter().deliver(repaired)

    assert not (repaired.mission.mission.mission.mission.contract.destination /
                repaired.mission.mission.mission.plan.project_name).exists()


def test_delivery_never_overwrites_existing_destination(tmp_path):
    repaired = _repaired(tmp_path)
    contract = repaired.mission.mission.mission.mission.contract
    target = contract.destination / contract.project_name
    target.mkdir()
    marker = target / "user.txt"
    marker.write_text("preservar", encoding="utf-8")

    with pytest.raises(FileExistsError, match="no sobrescribe"):
        ProjectDeliveryAdapter().deliver(repaired, authorized=True)

    assert marker.read_text(encoding="utf-8") == "preservar"


def test_delivery_rejects_mission_before_repair(tmp_path):
    tested = _tested(tmp_path)
    fake = type("Repaired", (), {"mission": tested})()

    with pytest.raises(ValueError, match="no está lista"):
        ProjectDeliveryAdapter().deliver(fake, authorized=True)
