from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

from igris_os.application.project_flow import ProjectStage
from igris_os.application.project_planning import PlannedProjectMission


@dataclass(frozen=True, slots=True)
class StagedProject:
    root: Path
    changed_files: tuple[str, ...]


class ProjectStagingDeveloper(Protocol):
    """Ejecutor que construye exclusivamente dentro de un staging."""

    def stage(self, mission: PlannedProjectMission) -> StagedProject:
        ...


@dataclass(frozen=True, slots=True)
class DevelopedProjectMission:
    mission: PlannedProjectMission
    staging: StagedProject


class ProjectDevelopmentAdapter:
    """Registra desarrollo aislado sin probar ni entregar el proyecto."""

    def __init__(self, workspace: Path,
                 developer: ProjectStagingDeveloper) -> None:
        self.workspace = Path(workspace).resolve()
        self.developer = developer

    def develop(self, planned: PlannedProjectMission) -> DevelopedProjectMission:
        if planned.mission.flow.next_stage is not ProjectStage.DEVELOP:
            raise ValueError("La misión no está lista para desarrollo")
        staging = self.developer.stage(planned)
        root = Path(staging.root).resolve()
        staging_base = (self.workspace / ".staging").resolve()
        if not root.is_dir() or not root.is_relative_to(staging_base):
            raise ValueError("El desarrollo no produjo un staging aislado válido")
        if not staging.changed_files:
            raise ValueError("El staging no contiene cambios registrables")
        for relative in staging.changed_files:
            candidate = (root / relative).resolve()
            if not candidate.is_file() or not candidate.is_relative_to(root):
                raise ValueError("La evidencia del staging contiene una ruta inválida")
        summary = (
            f"Desarrollo aislado en {root.name}: "
            f"{len(staging.changed_files)} archivos registrados"
        )
        mission = replace(
            planned.mission,
            flow=planned.mission.flow.record(
                ProjectStage.DEVELOP, summary, success=True),
        )
        return DevelopedProjectMission(
            PlannedProjectMission(mission, planned.plan),
            StagedProject(root, staging.changed_files),
        )
