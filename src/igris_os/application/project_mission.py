from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping

from igris_os.application.project_contract import ProjectContract, ProjectIntake
from igris_os.application.project_flow import ProjectFlow, ProjectStage


@dataclass(frozen=True, slots=True)
class ProjectMission:
    """Une el contrato solicitado con su evidencia de ejecución."""

    contract: ProjectContract
    flow: ProjectFlow

    @property
    def ready_for_plan(self) -> bool:
        return self.contract.ready and self.flow.next_stage is ProjectStage.PLAN

    def record_plan(self, summary: str) -> ProjectMission:
        if not self.contract.ready:
            raise ValueError("No se puede planificar con decisiones pendientes")
        return replace(
            self,
            flow=self.flow.record(ProjectStage.PLAN, summary, success=True),
        )


class ProjectMissionFactory:
    def __init__(self, intake: ProjectIntake | None = None) -> None:
        self.intake = intake or ProjectIntake()

    def create(self, objective: str,
               answers: Mapping[str, object] | None = None) -> ProjectMission:
        contract = self.intake.build(objective, answers)
        flow = ProjectFlow().record(
            ProjectStage.REQUEST,
            f"Solicitud registrada: {contract.objective}",
            success=True,
        )
        return ProjectMission(contract, flow)
