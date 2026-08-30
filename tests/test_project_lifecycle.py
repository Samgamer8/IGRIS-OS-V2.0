from pathlib import Path

import pytest

from igris_os.application.project_development import StagedProject
from igris_os.application.project_lifecycle import ProjectLifecycle
from igris_os.application.project_repair import ProjectRepairEvidence
from igris_os.application.project_testing import ProjectTestEvidence


class FakeDeveloper:
    def __init__(self, root: Path):
        self.root = root

    def stage(self, mission):
        self.root.mkdir(parents=True)
        (self.root / "main.py").write_text("print('ok')\n", encoding="utf-8")
        return StagedProject(self.root, ("main.py",))


class FakeVerifier:
    def verify(self, mission):
        return ProjectTestEvidence(
            True, True, ("python", "-m", "pytest", "-q"), "1 passed")


class FakeRepairer:
    def repair(self, mission):
        return ProjectRepairEvidence(
            mission.mission.staging.root, True, True, True,
            ("main.py",), "1 passed tras reparación")


def _answers(destination: Path):
    return {
        "technology": "python", "delivery": "source",
        "destination": str(destination), "acceptance": "las pruebas pasan",
    }


def test_lifecycle_executes_every_stage_in_order(tmp_path):
    destination = tmp_path / "delivery"
    destination.mkdir()
    workspace = tmp_path / "workspace"
    lifecycle = ProjectLifecycle(
        workspace,
        FakeDeveloper(workspace / ".staging" / "candidate"),
        FakeVerifier(), FakeRepairer())

    result = lifecycle.execute(
        "Crea una aplicación", _answers(destination),
        delivery_authorized=True)

    flow = result.mission.mission.mission.mission.mission.flow
    assert flow.complete
    assert [item.stage.value for item in flow.evidence] == [
        "request", "plan", "develop", "test", "repair", "deliver"]
    assert (result.destination / "main.py").is_file()


def test_lifecycle_stops_before_delivery_without_authorization(tmp_path):
    destination = tmp_path / "delivery"
    destination.mkdir()
    workspace = tmp_path / "workspace"
    lifecycle = ProjectLifecycle(
        workspace,
        FakeDeveloper(workspace / ".staging" / "candidate"),
        FakeVerifier(), FakeRepairer())

    with pytest.raises(PermissionError, match="autorización explícita"):
        lifecycle.execute("Crea una aplicación", _answers(destination))

    assert not (destination / "Crea_una_aplicación").exists()


def test_lifecycle_stops_before_development_for_incomplete_contract(tmp_path):
    workspace = tmp_path / "workspace"
    lifecycle = ProjectLifecycle(
        workspace,
        FakeDeveloper(workspace / ".staging" / "candidate"),
        FakeVerifier(), FakeRepairer())

    with pytest.raises(ValueError, match="no está lista"):
        lifecycle.execute("Crea una aplicación", {})

    assert not (workspace / ".staging").exists()
