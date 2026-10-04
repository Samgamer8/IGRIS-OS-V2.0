from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

from igris_os.application.project_flow import ProjectStage
from igris_os.application.project_testing import TestedProjectMission


@dataclass(frozen=True, slots=True)
class ProjectRepairEvidence:
    root: Path
    attempted: bool
    successful: bool
    tests_passed: bool
    changed_files: tuple[str, ...]
    summary: str
    reviewed_files: tuple[str, ...] = ()


class ProjectStagingRepairer(Protocol):
    """Reparador que modifica y vuelve a verificar el staging probado."""

    def repair(self, mission: TestedProjectMission) -> ProjectRepairEvidence:
        ...


@dataclass(frozen=True, slots=True)
class RepairedProjectMission:
    mission: TestedProjectMission
    evidence: ProjectRepairEvidence


class ProjectRepairAdapter:
    """Registra una reparación verificada sin entregar artefactos."""

    def __init__(self, repairer: ProjectStagingRepairer) -> None:
        self.repairer = repairer

    def repair(self, tested: TestedProjectMission) -> RepairedProjectMission:
        project_mission = tested.mission.mission.mission
        if project_mission.flow.next_stage is not ProjectStage.REPAIR:
            raise ValueError("La misión no está lista para reparación")
        evidence = self.repairer.repair(tested)
        expected_root = tested.mission.staging.root.resolve()
        repaired_root = Path(evidence.root).resolve()
        if repaired_root != expected_root:
            raise ValueError("La reparación salió del staging probado")
        if not evidence.attempted:
            raise ValueError("La reparación no fue ejecutada")
        if not evidence.successful:
            raise ValueError("La reparación falló: " + evidence.summary)
        if not evidence.tests_passed:
            raise ValueError("La reparación no superó las pruebas posteriores")
        if not evidence.summary.strip():
            raise ValueError("La evidencia de reparación está vacía")
        if not evidence.changed_files and not evidence.reviewed_files:
            raise ValueError("La reparación no registra archivos modificados")
        for relative in (*evidence.changed_files, *evidence.reviewed_files):
            candidate = (repaired_root / relative).resolve()
            if not candidate.is_file() or not candidate.is_relative_to(repaired_root):
                raise ValueError("La reparación contiene una ruta inválida")
        summary = (f"Reparación verificada en {repaired_root.name}: "
                   f"{len(evidence.changed_files)} archivos; {evidence.summary}"
                   if evidence.changed_files else
                   f"Revision verificada sin modificaciones: {evidence.summary}")
        repaired_mission = replace(
            project_mission,
            flow=project_mission.flow.record(
                ProjectStage.REPAIR, summary, success=True),
        )
        planned = replace(tested.mission.mission, mission=repaired_mission)
        developed = replace(tested.mission, mission=planned)
        return RepairedProjectMission(
            replace(tested, mission=developed), evidence)
