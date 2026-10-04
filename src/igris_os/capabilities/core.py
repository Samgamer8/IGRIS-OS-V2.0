from igris_os.application import CapabilityRegistry, LLMMissionDirector
from igris_os.domain import ActionRisk, CapabilitySpec, ExecutionResult, Mission
from igris_os.tools import ToolCatalog


def register_core_capabilities(registry: CapabilityRegistry) -> None:
    registry.register(
        CapabilitySpec("mission.plan", "Plan verificable de una mision",
                       ActionRisk.READ_ONLY),
        lambda payload: _plan(payload),
    )
    registry.register(
        CapabilitySpec("system.tools", "Disponibilidad de herramientas locales",
                       ActionRisk.READ_ONLY),
        lambda _: ExecutionResult.success(
            "Herramientas inspeccionadas",
            tools=[{"name": tool.name, "available": tool.available,
                    "domains": tool.domains} for tool in ToolCatalog().discover()]),
    )
    registry.register(
        CapabilitySpec("system.capabilities", "Catalogo real de capacidades",
                       ActionRisk.READ_ONLY),
        lambda _: ExecutionResult.success(
            "Puedo inspeccionar archivos y herramientas locales e intentar generar proyectos. "
            "La generación necesita un modelo que responda y las herramientas de la tarea. "
            "Este catálogo describe funciones registradas; no confirma que estén disponibles "
            "en tu equipo ni garantiza un juego completo. Cada entrega debe indicar qué "
            "se ha comprobado y qué queda pendiente.",
            capabilities=[{"name": spec.name,
                           "description": spec.description,
                           "risk": spec.risk.value}
                          for spec in registry.specs()
                          if spec.name != "system.capabilities"]),
    )


def _plan(payload) -> ExecutionResult:
    objective = str(payload.get("objective", "")).strip()
    if not objective:
        return ExecutionResult.failure("Falta el objetivo", "EMPTY_OBJECTIVE")
    plan = LLMMissionDirector().plan(Mission(objective))
    return ExecutionResult.success(
        "Mision planificada",
        branch=plan.branch.value,
        deliverables=plan.deliverables,
        constraints=plan.constraints,
        acceptance_criteria=plan.acceptance_criteria,
        risks=plan.risks,
        estimated_complexity=plan.estimated_complexity,
        needs_clarification=plan.needs_clarification,
        clarification_questions=plan.clarification_questions,
    )
