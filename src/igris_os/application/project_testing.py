from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol

from igris_os.application.project_development import DevelopedProjectMission
from igris_os.application.project_flow import ProjectStage


@dataclass(frozen=True, slots=True)
class ProjectTestEvidence:
    executed: bool
    passed: bool
    command: tuple[str, ...]
    summary: str


class ProjectStagingVerifier(Protocol):
    """Verificador que ejecuta pruebas sobre un staging ya construido."""

    def verify(self, mission: DevelopedProjectMission) -> ProjectTestEvidence:
        ...


@dataclass(frozen=True, slots=True)
class TestedProjectMission:
    mission: DevelopedProjectMission
    evidence: ProjectTestEvidence


class ProjectTestingAdapter:
    """Registra pruebas ejecutadas para permitir reparar los fallos detectados."""

    def __init__(self, verifier: ProjectStagingVerifier) -> None:
        self.verifier = verifier

    def test(self, developed: DevelopedProjectMission) -> TestedProjectMission:
        project_mission = developed.mission.mission
        if project_mission.flow.next_stage is not ProjectStage.TEST:
            raise ValueError("La misión no está lista para pruebas")
        evidence = self.verifier.verify(developed)
        if not evidence.executed:
            raise ValueError("Las pruebas no fueron ejecutadas")
        if not evidence.command or not all(item.strip() for item in evidence.command):
            raise ValueError("La evidencia no identifica el comando ejecutado")
        if not evidence.summary.strip():
            raise ValueError("La evidencia de pruebas está vacía")
        command = " ".join(evidence.command)
        result = "aprobadas" if evidence.passed else "fallidas"
        summary = f"Pruebas {result} con `{command}`: {evidence.summary}"
        tested_mission = replace(
            project_mission,
            flow=project_mission.flow.record(
                ProjectStage.TEST, summary, success=True),
        )
        planned = replace(developed.mission, mission=tested_mission)
        return TestedProjectMission(
            replace(developed, mission=planned), evidence)
