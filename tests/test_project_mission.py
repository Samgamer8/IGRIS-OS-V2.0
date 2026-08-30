import pytest

from igris_os.application.project_mission import ProjectMissionFactory
from igris_os.application.project_flow import ProjectStage


def test_project_mission_connects_contract_and_request_evidence():
    mission = ProjectMissionFactory().create("Crea una aplicación")

    assert mission.contract.objective == "Crea una aplicación"
    assert mission.flow.evidence[0].stage is ProjectStage.REQUEST
    assert mission.flow.next_stage is ProjectStage.PLAN
    assert not mission.ready_for_plan


def test_incomplete_contract_cannot_advance_to_plan():
    mission = ProjectMissionFactory().create("Crea una aplicación")

    with pytest.raises(ValueError, match="decisiones pendientes"):
        mission.record_plan("Arquitectura definida")


def test_complete_contract_can_record_plan(tmp_path):
    mission = ProjectMissionFactory().create("Crea una aplicación", {
        "technology": "python",
        "delivery": "source",
        "destination": str(tmp_path),
        "acceptance": "las pruebas pasan",
    })

    assert mission.ready_for_plan
    planned = mission.record_plan("Componentes y pruebas definidos")
    assert planned.flow.next_stage is ProjectStage.DEVELOP
    assert mission.flow.next_stage is ProjectStage.PLAN
