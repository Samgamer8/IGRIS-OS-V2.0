"""Politica reforzada con auditoría estructurada y Zero Trust."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from igris_os.domain.models import ActionRisk, CapabilitySpec
from igris_os.security.audit_logger import SecurityAuditLogger


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    allowed: bool
    reason: str
    confirmation_required: bool = False


class PermissionPolicy:
    """Evaluador de políticas de permisos con soporte Zero Trust y auditoría."""

    DEFAULT_TOKEN_TTL_SECONDS = 900  # 15 minutos

    def __init__(self, audit_logger: SecurityAuditLogger | None = None) -> None:
        self.audit_logger = audit_logger or SecurityAuditLogger()

    def evaluate(
        self,
        spec: CapabilitySpec | None,
        *,
        confirmed: bool = False,
        token_timestamp: float | None = None,
        token_ttl_seconds: int = DEFAULT_TOKEN_TTL_SECONDS,
        context: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        """Evalúa permiso con auditoría e inspección de expiración Zero Trust."""
        ctx = context or {}
        risk_name = spec.risk.name if spec and hasattr(spec.risk, "name") else str(spec.risk) if spec else "UNKNOWN"
        cap_name = spec.name if spec else "INVALID"

        if spec is None:
            reason = "Capacidad especificada invalida"
            decision = PolicyDecision(False, reason)
            self._audit(cap_name, decision, risk_name, ctx)
            return decision

        # DESTRUCTIVE SIEMPRE bloqueado
        if spec.risk is ActionRisk.DESTRUCTIVE:
            reason = "Acciones destructivas siempre estan bloqueadas"
            decision = PolicyDecision(False, reason)
            self._audit(cap_name, decision, risk_name, ctx)
            return decision

        # Verificación de expiración de token de aprobación (Zero Trust TTL)
        if confirmed and token_timestamp is not None:
            elapsed = time.time() - token_timestamp
            if elapsed > token_ttl_seconds:
                reason = f"Token de aprobacion expirado ({int(elapsed)}s > {token_ttl_seconds}s)"
                decision = PolicyDecision(False, reason, confirmation_required=True)
                self._audit(cap_name, decision, risk_name, ctx, event_type="TOKEN_EXPIRED")
                return decision

        # Requiere confirmación explícita
        needs_confirmation = spec.requires_confirmation or spec.risk in {
            ActionRisk.WRITE_WORKSPACE,
            ActionRisk.EXTERNAL,
        }

        if needs_confirmation and not confirmed:
            reason = "Se necesita confirmacion explicita"
            decision = PolicyDecision(False, reason, confirmation_required=True)
            self._audit(cap_name, decision, risk_name, ctx)
            return decision

        reason = "Accion permitida"
        decision = PolicyDecision(True, reason)
        self._audit(cap_name, decision, risk_name, ctx)
        return decision

    def _audit(
        self,
        capability: str,
        decision: PolicyDecision,
        risk_level: str,
        context: dict[str, Any],
        event_type: str | None = None,
    ) -> None:
        if event_type is None:
            event_type = "POLICY_DENIED" if not decision.allowed else "POLICY_ALLOWED"
        severity = "WARNING" if not decision.allowed else "INFO"
        if risk_level == "DESTRUCTIVE" and not decision.allowed:
            severity = "CRITICAL"

        self.audit_logger.log(
            event_type=event_type,
            severity=severity,
            capability=capability,
            allowed=decision.allowed,
            reason=decision.reason,
            risk_level=risk_level,
            details=context,
        )