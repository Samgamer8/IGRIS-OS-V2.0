from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ComponentSpec:
    name: str
    path: str
    purpose: str
    depends_on: tuple[str, ...] = ()
    acceptance: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ComponentPlan:
    objective: str
    components: tuple[ComponentSpec, ...]
    integration_test: str


class PythonComponentPlanner:
    """Define una arquitectura mínima antes de pedir una entrega multiarchivo."""

    def plan(self, objective: str) -> ComponentPlan:
        if not objective.strip():
            raise ValueError("Falta el objetivo de la aplicación")
        components = (
            ComponentSpec(
                "model", "model.py",
                "Entidades y validación de datos en memoria.",
                acceptance=("No realiza E/S", "Expone tipos y errores claros")),
            ComponentSpec(
                "service", "service.py",
                "Casos de uso y reglas de negocio.", ("model",),
                ("Usa el modelo", "Maneja casos límite")),
            ComponentSpec(
                "cli", "main.py",
                "Entrada de consola del usuario.", ("service",),
                ("No ejecuta al importar", "Expone main()")),
            ComponentSpec(
                "tests", "test_service.py",
                "Pruebas de integración del servicio.", ("model", "service"),
                ("Ejecutable con pytest", "Cubre flujo principal y error")),
        )
        return ComponentPlan(
            objective.strip(), components,
            "pytest -q debe aprobar todas las pruebas del conjunto")

    @staticmethod
    def validate_files(plan: ComponentPlan, files: dict[str, str]) -> None:
        expected = {component.path for component in plan.components}
        supplied = set(files)
        missing = expected - supplied
        if missing:
            raise ValueError("Faltan componentes: " + ", ".join(sorted(missing)))
        unexpected_tests = [path for path in supplied if path.startswith("test_")]
        if not unexpected_tests:
            raise ValueError("Falta una prueba de integración")