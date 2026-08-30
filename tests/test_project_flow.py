import pytest

from igris_os.application.project_flow import ProjectFlow, ProjectStage


def test_project_flow_requires_every_stage_in_order():
    flow = ProjectFlow()

    for stage in ProjectStage:
        assert flow.next_stage is stage
        flow = flow.record(stage, f"evidencia de {stage.value}", success=True)

    assert flow.complete
    assert flow.next_stage is None


def test_project_flow_rejects_skipped_stage():
    with pytest.raises(ValueError, match="se esperaba request"):
        ProjectFlow().record(ProjectStage.DEVELOP, "codigo", success=True)


def test_project_flow_rejects_failure_and_empty_evidence():
    flow = ProjectFlow()

    with pytest.raises(ValueError, match="requiere evidencia"):
        flow.record(ProjectStage.REQUEST, " ", success=True)
    with pytest.raises(ValueError, match="No se puede avanzar"):
        flow.record(ProjectStage.REQUEST, "objetivo ambiguo", success=False)
