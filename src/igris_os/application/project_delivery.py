from __future__ import annotations

import shutil
from dataclasses import dataclass, replace
from pathlib import Path

from igris_os.application.project_flow import ProjectStage
from igris_os.application.project_repair import RepairedProjectMission


@dataclass(frozen=True, slots=True)
class DeliveredProjectMission:
    mission: RepairedProjectMission
    destination: Path


class ProjectDeliveryAdapter:
    """Entrega un staging verificado con autorización y sin sobrescrituras."""

    def deliver(self, repaired: RepairedProjectMission, *,
                authorized: bool = False) -> DeliveredProjectMission:
        project_mission = repaired.mission.mission.mission.mission
        if project_mission.flow.next_stage is not ProjectStage.DELIVER:
            raise ValueError("La misión no está lista para entrega")
        if not authorized:
            raise PermissionError("La entrega requiere autorización explícita")
        contract = project_mission.contract
        if contract.destination is None or not contract.destination.is_dir():
            raise ValueError("La carpeta de entrega no está disponible")
        source = repaired.mission.mission.staging.root.resolve()
        if not source.is_dir():
            raise ValueError("El staging verificado ya no existe")
        target = (contract.destination / contract.project_name).resolve()
        if not target.is_relative_to(contract.destination.resolve()):
            raise ValueError("La ruta de entrega sale de la carpeta autorizada")
        if target.exists():
            raise FileExistsError("La entrega no sobrescribe destinos existentes")
        shutil.copytree(source, target)
        summary = (
            f"Entrega autorizada en {target.name}: "
            f"{len(repaired.evidence.changed_files)} archivos verificados"
        )
        delivered_mission = replace(
            project_mission,
            flow=project_mission.flow.record(
                ProjectStage.DELIVER, summary, success=True),
        )
        planned = replace(
            repaired.mission.mission.mission, mission=delivered_mission)
        developed = replace(repaired.mission.mission, mission=planned)
        tested = replace(repaired.mission, mission=developed)
        return DeliveredProjectMission(
            replace(repaired, mission=tested), target)
