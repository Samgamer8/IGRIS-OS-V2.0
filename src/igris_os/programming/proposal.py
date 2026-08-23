from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .assessment import EngineeringAssessment, EngineeringAssessor


@dataclass(frozen=True, slots=True)
class ChangeProposal:
    objective: str
    assessment: EngineeringAssessment
    affected_files: tuple[str, ...]
    changes: tuple[str, ...]
    risks: tuple[str, ...]
    tests: tuple[str, ...]
    requires_confirmation: bool = True

    @property
    def can_apply(self) -> bool:
        return self.assessment.can_proceed and bool(self.changes)


class ChangeProposalBuilder:
    """Construye planes de cambio sin escribir ni ejecutar código."""

    def __init__(self, assessor: EngineeringAssessor | None = None) -> None:
        self.assessor = assessor or EngineeringAssessor()

    def build(self, root: Path, objective: str) -> ChangeProposal:
        assessment = self.assessor.assess(root, objective)
        affected = tuple(sorted({item.path for item in assessment.risks
                                 if item.path != "."}))
        risks = tuple(
            f"{item.severity}: {item.path}: {item.message} ({item.evidence})"
            for item in assessment.risks)
        changes = (
            "Revisar los archivos afectados y conservar su comportamiento probado",
            "Aplicar el cambio mínimo en una copia aislada",
            "No eliminar controles de seguridad ni pruebas existentes",
        )
        if not assessment.can_proceed:
            changes = ("Resolver primero los bloqueos críticos del preflight",)
        return ChangeProposal(
            objective=objective.strip(), assessment=assessment,
            affected_files=affected, changes=changes, risks=risks,
            tests=assessment.required_tests)