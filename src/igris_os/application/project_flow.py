from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ProjectStage(str, Enum):
    REQUEST = "request"
    PLAN = "plan"
    DEVELOP = "develop"
    TEST = "test"
    REPAIR = "repair"
    DELIVER = "deliver"


STAGE_ORDER = tuple(ProjectStage)


@dataclass(frozen=True, slots=True)
class StageEvidence:
    stage: ProjectStage
    summary: str
    success: bool

    def __post_init__(self) -> None:
        if not self.summary.strip():
            raise ValueError("Cada etapa requiere evidencia")


@dataclass(frozen=True, slots=True)
class ProjectFlow:
    """Contrato inmutable para avanzar sin saltar etapas ni ocultar fallos."""

    evidence: tuple[StageEvidence, ...] = ()

    @property
    def next_stage(self) -> ProjectStage | None:
        if len(self.evidence) >= len(STAGE_ORDER):
            return None
        return STAGE_ORDER[len(self.evidence)]

    @property
    def complete(self) -> bool:
        return self.next_stage is None

    def record(self, stage: ProjectStage, summary: str,
               *, success: bool) -> ProjectFlow:
        expected = self.next_stage
        if expected is None:
            raise ValueError("El flujo ya esta completado")
        if stage is not expected:
            raise ValueError(
                f"Etapa fuera de orden: se esperaba {expected.value}")
        evidence = StageEvidence(stage, summary, success)
        if not success:
            raise ValueError(
                f"No se puede avanzar: fallo en {stage.value}: {summary}")
        return ProjectFlow(self.evidence + (evidence,))
