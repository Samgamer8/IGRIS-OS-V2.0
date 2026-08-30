from __future__ import annotations

from dataclasses import dataclass

from igris_os.application.project_contract import ProjectContract


@dataclass(frozen=True, slots=True)
class ProjectPhase:
    name: str
    outcome: str
    acceptance_gate: str


@dataclass(frozen=True, slots=True)
class ProjectExecutionPlan:
    project_name: str
    phases: tuple[ProjectPhase, ...]
    risks: tuple[str, ...]
    dependencies: tuple[str, ...]


class ProjectOffice:
    """Convierte un contrato listo en un plan de ejecución con puertas reales."""

    def plan(self, contract: ProjectContract) -> ProjectExecutionPlan:
        if not contract.ready:
            raise ValueError("El contrato todavía tiene preguntas pendientes")
        phases = (
            ProjectPhase(
                "Alcance", "Contrato y criterios de aceptación confirmados",
                "No quedan decisiones pendientes"),
            ProjectPhase(
                "Implementación", "Código y pruebas dentro de staging aislado",
                "Archivos dentro del workspace y sin rutas prohibidas"),
            ProjectPhase(
                "Verificación", "Pruebas automatizadas ejecutadas",
                "Todas las pruebas terminan con código 0"),
            ProjectPhase(
                "Entrega", "Copia en la carpeta autorizada",
                "Existe VERIFICATION.json en la entrega"),
        )
        dependencies = ["Intérprete y herramientas de la tecnología seleccionada"]
        if contract.delivery == "source_and_exe":
            dependencies.append("Empaquetador y verificación de ejecutable disponibles")
        risks = [
            "Una respuesta del modelo no se acepta sin pruebas aprobadas",
            "El alcance cambia si se modifican los criterios de aceptación",
        ]
        if contract.constraints:
            risks.append("Restricciones declaradas: " + "; ".join(contract.constraints))
        return ProjectExecutionPlan(
            contract.project_name, phases, tuple(risks), tuple(dependencies))