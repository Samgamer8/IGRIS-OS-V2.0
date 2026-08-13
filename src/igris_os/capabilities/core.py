from igris_os.application import CapabilityRegistry, MissionDirector
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
            "Capacidades reales de IGRIS",
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
    plan = MissionDirector().plan(Mission(objective))
    return ExecutionResult.success("Mision planificada", branch=plan.branch.value,
                                   steps=plan.steps, acceptance=plan.acceptance)
