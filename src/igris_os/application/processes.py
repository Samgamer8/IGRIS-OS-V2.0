from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from igris_os.application.project_contract import ProjectContract
from igris_os.application.project_office import ProjectOffice


@dataclass(frozen=True, slots=True)
class ProcessStep:
    name: str
    owner: str
    purpose: str
    evidence: str
    risk: str = "medium"


@dataclass(frozen=True, slots=True)
class ProjectProcess:
    objective: str
    stages: tuple[ProcessStep, ...]
    status: str
    ooda: dict[str, str]


class ProcessOrchestrator:
    """Representa un flujo mínimo de ejecución basado en líderes de proyecto y revisores."""

    def __init__(self, office: ProjectOffice | None = None) -> None:
        self.office = office or ProjectOffice()

    def build(self, objective: str, contract: ProjectContract | None = None) -> ProjectProcess:
        if not objective or not objective.strip():
            raise ValueError("El objetivo del proceso no puede estar vacío")

        if contract is None:
            contract = ProjectContract(
                objective=objective.strip(),
                project_name="proyecto_igris",
                destination=None,
                technology="python",
                delivery="source",
                acceptance=("El objetivo queda definido y verificable",),
                constraints=("No se aceptan supuestos no comprobados",),
                questions=(),
            )

        plan = self.office.plan(contract) if contract.ready else None
        stages = self._default_stages(contract, plan)
        return ProjectProcess(
            objective=objective.strip(),
            stages=stages,
            status="planned",
            ooda=self._ooda_summary(objective.strip(), contract, plan),
        )

    def run(self, objective: str, contract: ProjectContract | None = None,
            on_progress: Callable[[int, str], None] | None = None) -> ProjectProcess:
        process = self.build(objective, contract)
        for index, stage in enumerate(process.stages, start=1):
            if on_progress is not None:
                on_progress(int((index / max(len(process.stages), 1)) * 100),
                            f"Proceso: {stage.name} ({stage.owner})")

        return ProjectProcess(
            objective=process.objective,
            stages=process.stages,
            status="ready",
            ooda=process.ooda,
        )

    @staticmethod
    def _default_stages(contract: ProjectContract,
                        plan) -> tuple[ProcessStep, ...]:
        base = (
            ProcessStep(
                "Misión y alcance",
                "Mission Commander",
                "Definir objetivo, criterios de aceptación y riesgos",
                "Hay objetivo claro y sin supuestos no verificados",
                "high",
            ),
            ProcessStep(
                "Arquitectura",
                "Architect",
                "Elegir stack, módulos y flujo técnico",
                "La solución tiene estructura y decisiones basadas en requisitos",
                "high",
            ),
            ProcessStep(
                "Implementación",
                "Senior Developer",
                "Convertir la arquitectura en código y pruebas",
                "Se produce código dentro del workspace y con validación prevista",
                "medium",
            ),
            ProcessStep(
                "Verificación",
                "QA / Verification",
                "Comprobar pruebas, ejecución y rejilla de errores",
                "Existe evidencia de pruebas reales y no solo sintaxis",
                "high",
            ),
            ProcessStep(
                "Entrega",
                "Project Lead",
                "Preparar la entrega con criterios de aceptación",
                "La entrega queda documentada y validada por evidencia",
                "medium",
            ),
        )

        if plan is not None:
            return tuple(
                ProcessStep(
                    phase.name,
                    {"Alcance": "Mission Commander",
                     "Implementación": "Senior Developer",
                     "Verificación": "QA / Verification",
                     "Entrega": "Project Lead"}.get(phase.name, "Architect"),
                    phase.outcome,
                    phase.acceptance_gate,
                    "high" if phase.name in {"Alcance", "Verificación"} else "medium",
                )
                for phase in plan.phases
            )
        return base

    @staticmethod
    def _ooda_summary(objective: str, contract: ProjectContract, plan) -> dict[str, str]:
        observe = (
            f"Se observa que el objetivo es '{objective}'. "
            f"La tecnología elegida es {contract.technology} y la entrega es {contract.delivery}."
        )
        orient = (
            "Se orienta hacia una ejecución por fases: alcance, implementación, verificación y entrega. "
            "Las decisiones se basan en requisitos y evidencia, no en suposiciones no comprobadas."
        )
        decide = (
            "Se decide priorizar la arquitectura, la validación y la revisión independiente antes de cerrar la entrega."
        )
        act = (
            "Se actuará con un ciclo de ejecución y verificación: definición, construcción, pruebas, corrección y cierre."
        )
        if plan is not None:
            act += f" Hay {len(plan.phases)} fases confirmadas por el Project Office."
        return {
            "observe": observe,
            "orient": orient,
            "decide": decide,
            "act": act,
        }
