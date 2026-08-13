from dataclasses import dataclass

from igris_os.domain import ActionRisk, CapabilitySpec


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    allowed: bool
    reason: str
    confirmation_required: bool = False


class PermissionPolicy:
    def evaluate(self, spec: CapabilitySpec, *, confirmed: bool = False) -> PolicyDecision:
        if spec.risk is ActionRisk.DESTRUCTIVE:
            return PolicyDecision(False, "Las acciones destructivas estan bloqueadas")
        needs_confirmation = spec.requires_confirmation or spec.risk in {
            ActionRisk.WRITE_WORKSPACE,
            ActionRisk.EXTERNAL,
        }
        if needs_confirmation and not confirmed:
            return PolicyDecision(False, "Se necesita confirmacion explicita", True)
        return PolicyDecision(True, "Accion permitida")

