import pytest

from igris_os.application.project_flow import ProjectStage
from igris_os.application.project_mission import ProjectMissionFactory
from igris_os.application.project_planning import ProjectMissionPlanner


def test_planner_rejects_incomplete_mission():
    mission = ProjectMissionFactory().create("Crea una aplicación")

    with pytest.raises(ValueError, match="no está lista"):
        ProjectMissionPlanner().plan(mission)


def test_planner_records_office_plan_as_evidence(tmp_path):
    mission = ProjectMissionFactory().create("Crea una aplicación", {
        "technology": "python",
        "delivery": "source",
        "destination": str(tmp_path),
        "acceptance": "las pruebas pasan",
    })

    result = ProjectMissionPlanner().plan(mission)

    assert result.plan.project_name == mission.contract.project_name
    assert [phase.name for phase in result.plan.phases] == [
        "Alcance", "Implementación", "Verificación", "Entrega"]
    assert result.mission.flow.next_stage is ProjectStage.DEVELOP
    assert "4 fases" in result.mission.flow.evidence[-1].summary
    assert mission.flow.next_stage is ProjectStage.PLAN
