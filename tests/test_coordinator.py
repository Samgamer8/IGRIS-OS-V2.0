import json

from igris_os.application import ExecutionPlan, SpecialistCoordinator, SpecialistTeam
from igris_os.ai import ModelReply


class FakeClient:
    def __init__(self, fail_at=-1):
        self.calls = []
        self.fail_at = fail_at

    def generate(self, prompt, model):
        self.calls.append((prompt, model))
        if len(self.calls) == self.fail_at:
            return ModelReply(False, "", model, "fallo controlado")
        return ModelReply(True, f"informe {len(self.calls)}", model)


def test_specialists_are_cross_reviewed_and_recorded(tmp_path):
    client = FakeClient()
    result = SpecialistCoordinator(client, tmp_path).coordinate(
        "programa una API Python", "coder")
    assert result.complete
    assert len(result.findings) == 6
    assert result.findings[0].role == "mission_commander"
    assert result.review.role == "revisor_independiente"
    evidence = json.loads(
        (tmp_path / "specialist_coordination.json").read_text(encoding="utf-8"))
    assert evidence["complete"] is True


def test_specialist_failure_prevents_complete_result(tmp_path):
    result = SpecialistCoordinator(FakeClient(fail_at=2), tmp_path).coordinate(
        "crea un videojuego", "coder")
    assert not result.complete
    assert not result.findings[1].ok


def test_coordinate_reports_granular_progress(tmp_path):
    events = []
    result = SpecialistCoordinator(FakeClient(), tmp_path).coordinate(
        "programa una API Python", "coder",
        on_progress=lambda pct, msg: events.append((pct, msg)))
    assert result.complete
    assert events
    assert all(0 <= pct <= 100 for pct, _ in events)
    assert events[-1][0] >= 90


def test_specialist_team_for_programming_has_explicit_roles():
    team = SpecialistCoordinator.build_team("Crea una API Python", "programming")
    assert isinstance(team, SpecialistTeam)
    assert team.branch == "programming"
    assert team.roles[:2] == ("mission_commander", "arquitecto")
    assert "codigo_verificado" in team.controls


def test_execution_plan_maps_roles_to_real_concrete_phases():
    plan = SpecialistCoordinator.build_execution_plan("Crea una API Python", "programming")
    assert isinstance(plan, ExecutionPlan)
    assert plan.branch == "programming"
    assert plan.steps[0].phase == "Alcance"
    assert plan.steps[0].gate == "alcance_confirmado"
    assert plan.steps[-1].role == "revisor_critico"
    assert plan.steps[-1].phase == "Revisión"
    assert "codigo_verificado" in plan.controls


def test_coordinate_keeps_execution_plan_in_result(tmp_path):
    result = SpecialistCoordinator(FakeClient(), tmp_path).coordinate(
        "programa una API Python", "coder")
    assert result.execution_plan is not None
    assert result.execution_plan.branch == "programming"
    assert result.execution_plan.steps[0].role == "mission_commander"
