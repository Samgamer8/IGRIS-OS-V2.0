from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class OrgUnit:
    name: str
    role: str
    owner: str
    responsibilities: tuple[str, ...]
    priority: str = "normal"
    dependencies: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class IgrisOrgChart:
    ceo: str
    director: str
    mission: str
    units: tuple[OrgUnit, ...]
    control_rules: tuple[str, ...]
    escalation: str


def build_igris_org_chart() -> IgrisOrgChart:
    units = (
        OrgUnit(
            name="Mission Control",
            role="Dirección general",
            owner="IGRIS OS",
            responsibilities=(
                "Define la visión y el objetivo global del proyecto.",
                "Prioriza misiones y entrega criterios de éxito.",
                "Abre, cierra y reorienta flujos por evidencia.",
            ),
            priority="critical",
        ),
        OrgUnit(
            name="Arquitectura",
            role="Subjefe de estructura",
            owner="Arquitecto principal",
            responsibilities=(
                "Diseña módulos, interfaces y dependencias.",
                "Resuelve decisiones de stack y riesgos técnicos.",
                "Garantiza que cada bloque pueda probarse y sostenerse.",
            ),
            priority="high",
            dependencies=("Mission Control",),
        ),
        OrgUnit(
            name="Programación",
            role="Subjefe de ejecución",
            owner="Implementador senior",
            responsibilities=(
                "Genera código funcional y pruebas reales.",
                "Coordina la entrega por módulos y features.",
                "Evita soluciones que no puedan validarse.",
            ),
            priority="critical",
            dependencies=("Arquitectura",),
        ),
        OrgUnit(
            name="QA y Verificación",
            role="Subjefe de calidad",
            owner="Ingeniero de pruebas",
            responsibilities=(
                "Ejecuta pruebas, casos límite y regresiones.",
                "Valida que cada entregable cumple requerimientos.",
                "Bloquea la entrega si la evidencia no es suficiente.",
            ),
            priority="critical",
            dependencies=("Programación",),
        ),
        OrgUnit(
            name="Seguridad y Robustez",
            role="Subjefe de riesgos",
            owner="Auditor de seguridad",
            responsibilities=(
                "Revisa permisos, entradas, secretos y puntos de fallo.",
                "Propone mitigación y límites operativos.",
                "Impone restricciones cuando el riesgo supera el beneficio.",
            ),
            priority="high",
            dependencies=("Programación", "QA y Verificación"),
        ),
        OrgUnit(
            name="Infraestructura",
            role="Subjefe de ejecución operativa",
            owner="Ingeniero de despliegue",
            responsibilities=(
                "Prepara entornos, dependencias y runtime.",
                "Gestiona ejecución, aislamiento y recuperación.",
                "Asegura que el sistema pueda arrancar y mantenerse.",
            ),
            priority="high",
            dependencies=("Arquitectura", "Programación"),
        ),
        OrgUnit(
            name="Investigación",
            role="Subjefe de aprendizaje",
            owner="Analista técnico",
            responsibilities=(
                "Busca evidencia verificada y documentación de vanguardia.",
                "Evalúa alternativas y compara patrones reales.",
                "Evita decisiones basadas en intuición o rumor.",
            ),
            priority="medium",
            dependencies=("Mission Control", "Arquitectura"),
        ),
        OrgUnit(
            name="Revisión Crítica",
            role="Junta de control",
            owner="Revisor independiente",
            responsibilities=(
                "Revisa contradicciones, vacíos y promesas sin evidencia.",
                "Da veredicto final antes de entregar.",
                "Mantiene la integridad del sistema sin tomar decisiones técnicas por impulso.",
            ),
            priority="critical",
            dependencies=("QA y Verificación", "Seguridad y Robustez"),
        ),
    )
    return IgrisOrgChart(
        ceo="Usuario / CEO",
        director="IGRIS OS",
        mission="Construir un sistema de ingeniería autónoma que planifica, ejecuta, valida, corrige y entrega software con evidencia real.",
        units=units,
        control_rules=(
            "Cada unidad debe producir evidencia verificable.",
            "No se acepta una entrega sin prueba ejecutada.",
            "Si un sector falla, la causa se localiza por unidad, no por generalización.",
            "La figura del CEO no sustituye la revisión técnica ni la validación.",
        ),
        escalation="La revisión crítica bloquea la entrega cuando la evidencia no es suficiente o hay contradicción funcional.",
    )


__all__ = ["OrgUnit", "IgrisOrgChart", "build_igris_org_chart"]
