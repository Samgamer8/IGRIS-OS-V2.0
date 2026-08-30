from __future__ import annotations

from pathlib import Path
from typing import Mapping

from igris_os.application.project_delivery import (
    DeliveredProjectMission,
    ProjectDeliveryAdapter,
)
from igris_os.application.project_development import (
    ProjectDevelopmentAdapter,
    ProjectStagingDeveloper,
)
from igris_os.application.project_mission import ProjectMissionFactory
from igris_os.application.project_planning import ProjectMissionPlanner
from igris_os.application.project_repair import (
    ProjectRepairAdapter,
    ProjectStagingRepairer,
)
from igris_os.application.project_testing import (
    ProjectStagingVerifier,
    ProjectTestingAdapter,
)


class ProjectLifecycle:
    """Fachada del flujo completo conservando todas sus puertas de seguridad."""

    def __init__(self, workspace: Path, developer: ProjectStagingDeveloper,
                 verifier: ProjectStagingVerifier,
                 repairer: ProjectStagingRepairer) -> None:
        self.factory = ProjectMissionFactory()
        self.planner = ProjectMissionPlanner()
        self.development = ProjectDevelopmentAdapter(workspace, developer)
        self.testing = ProjectTestingAdapter(verifier)
        self.repair = ProjectRepairAdapter(repairer)
        self.delivery = ProjectDeliveryAdapter()

    def execute(self, objective: str, answers: Mapping[str, object], *,
                delivery_authorized: bool = False) -> DeliveredProjectMission:
        mission = self.factory.create(objective, answers)
        planned = self.planner.plan(mission)
        developed = self.development.develop(planned)
        tested = self.testing.test(developed)
        repaired = self.repair.repair(tested)
        return self.delivery.deliver(
            repaired, authorized=delivery_authorized)
