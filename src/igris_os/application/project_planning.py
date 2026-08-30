from __future__ import annotations

from dataclasses import dataclass

from igris_os.application.project_mission import ProjectMission
from igris_os.application.project_office import ProjectExecutionPlan, ProjectOffice


@dataclass(frozen=True, slots=True)
class PlannedProjectMission:
    mission: ProjectMission
    plan: ProjectExecutionPlan


class ProjectMissionPlanner:
    """Genera el plan y registra su evidencia sin iniciar desarrollo."""

    def __init__(self, office: ProjectOffice | None = None) -> None:
        self.office = office or ProjectOffice()

    def plan(self, mission: ProjectMission) -> PlannedProjectMission:
        if not mission.ready_for_plan:
            raise ValueError("La misión no está lista para planificación")
        plan = self.office.plan(mission.contract)
        phase_names = ", ".join(phase.name for phase in plan.phases)
        evidence = (
            f"Plan registrado con {len(plan.phases)} fases: {phase_names}; "
            f"{len(plan.risks)} riesgos y {len(plan.dependencies)} dependencias"
        )
        return PlannedProjectMission(mission.record_plan(evidence), plan)
