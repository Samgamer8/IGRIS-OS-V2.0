from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .preflight import PreflightFinding, PreflightReport, ProgrammingPreflight


@dataclass(frozen=True, slots=True)
class EngineeringAssessment:
    root: str
    facts: tuple[str, ...]
    risks: tuple[PreflightFinding, ...]
    doubts: tuple[str, ...]
    proposal: tuple[str, ...]
    required_tests: tuple[str, ...]
    preflight: PreflightReport

    @property
    def can_proceed(self) -> bool:
        return self.preflight.ok


class EngineeringAssessor:
    """Convierte un preflight en un diagnóstico técnico trazable."""

    def __init__(self, preflight: ProgrammingPreflight | None = None) -> None:
        self.preflight = preflight or ProgrammingPreflight()

    def assess(self, root: Path, objective: str = "") -> EngineeringAssessment:
        report = self.preflight.inspect(root)
        facts = (
            f"Proyecto: {report.root}",
            f"Archivos inspeccionados: {report.files}",
            f"Archivos Python: {report.python_files}",
            f"Archivos de pruebas: {report.test_files}",
            "Inspección estática realizada sin modificar archivos",
        )
        risks = tuple(item for item in report.findings
                      if item.severity in {"critical", "high"})
        doubts: list[str] = []
        if not objective.strip():
            doubts.append("No se ha definido un objetivo de cambio")
        if report.truncated:
            doubts.append("La inspección alcanzó su límite de archivos")
        if report.test_files == 0 and report.python_files:
            doubts.append("No hay pruebas detectadas para validar cambios")
        proposal = (
            "No modificar la fuente original",
            "Resolver primero los riesgos críticos",
            "Trabajar sobre una copia aislada",
            "Ejecutar las pruebas antes y después del cambio",
        )
        required_tests = (
            "compilación o comprobación de sintaxis",
            "pruebas existentes del proyecto",
            "verificación de rutas y límites",
        )
        return EngineeringAssessment(
            report.root, facts, risks, tuple(doubts), proposal,
            required_tests, report)