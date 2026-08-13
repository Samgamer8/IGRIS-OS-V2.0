from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from igris_os.application.registry import CapabilityRegistry
from igris_os.domain import ExecutionResult, Mission
from igris_os.security import PermissionPolicy
from igris_os.storage.audit import AuditLog
from igris_os.storage.workspace import MissionWorkspace


class IgrisKernel:
    def __init__(self, registry: CapabilityRegistry, policy: PermissionPolicy,
                 audit: AuditLog, workspaces: MissionWorkspace) -> None:
        self.registry = registry
        self.policy = policy
        self.audit = audit
        self.workspaces = workspaces

    def execute(self, mission: Mission, capability: str,
                payload: Mapping[str, Any] | None = None, *, confirmed: bool = False) -> ExecutionResult:
        item = self.registry.get(capability)
        if item is None:
            result = ExecutionResult.failure(f"Capacidad no disponible: {capability}", "NOT_FOUND")
            self.audit.record(mission, capability, result)
            return result
        spec, handler = item
        decision = self.policy.evaluate(spec, confirmed=confirmed)
        if not decision.allowed:
            code = "CONFIRMATION_REQUIRED" if decision.confirmation_required else "POLICY_DENIED"
            result = ExecutionResult.failure(decision.reason, code)
            self.audit.record(mission, capability, result)
            return result
        workspace = self.workspaces.create(mission.id)
        request = dict(payload or {})
        request["mission_id"] = mission.id
        request["workspace"] = str(workspace)
        try:
            result = handler(request)
            if not isinstance(result, ExecutionResult):
                result = ExecutionResult.failure("Resultado de capacidad invalido", "INVALID_RESULT")
        except Exception:
            result = ExecutionResult.failure("La capacidad fallo de forma controlada", "CAPABILITY_FAILED")
        self.audit.record(mission, capability, result)
        return result

