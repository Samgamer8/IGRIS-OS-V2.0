"""Politica reforzada."""
from dataclasses import dataclass
from igris_os.domain.models import ActionRisk, CapabilitySpec

@dataclass(frozen=True, slots=True)
class PolicyDecision:
    allowed: bool
    reason: str
    confirmation_required: bool = False

class PermissionPolicy:
    def evaluate(self, spec: CapabilitySpec | None, *, confirmed: bool = False) -> PolicyDecision:
        """Evalua permiso con auditoría."""
        if spec is None:
            return PolicyDecision(False, "Capacidad especificada invalida")
        
        # DESTRUCTIVE SIEMPRE bloqueado
        if spec.risk is ActionRisk.DESTRUCTIVE:
            return PolicyDecision(False, "Acciones destructivas siempre estan bloqueadas")
        
        # Requiere confirmación explícita
        needs_confirmation = spec.requires_confirmation or spec.risk in {
            ActionRisk.WRITE_WORKSPACE,
            ActionRisk.EXTERNAL,
        }
        
        if needs_confirmation and not confirmed:
            return PolicyDecision(False, "Se necesita confirmacion explicita", confirmation_required=True)
        
        return PolicyDecision(True, "Accion permitida")