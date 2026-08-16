"""Kernel robusto sin dependency de SIGALRM (Windows compatible)."""
from __future__ import annotations
import logging
import threading
import time
import traceback
from typing import Any, Callable, Mapping

from igris_os.application.approval import ApprovalAuthority
from igris_os.application.registry import CapabilityRegistry
from igris_os.domain.models import ExecutionResult, Mission, ActionRisk
from igris_os.security import PermissionPolicy
from igris_os.storage.audit import AuditLog
from igris_os.storage.workspace import MissionWorkspace

logger = logging.getLogger(__name__)

class TimeoutException(Exception):
    pass

class IgrisKernel:
    def __init__(self, registry: CapabilityRegistry, policy: PermissionPolicy,
                 audit: AuditLog, workspaces: MissionWorkspace,
                 approval: ApprovalAuthority | None = None) -> None:
        self.registry = registry
        self.policy = policy
        self.audit = audit
        self.workspaces = workspaces
        self.approval = approval or ApprovalAuthority()

    def issue_approval(self, binding: str, capability: str) -> str:
        """Emite un token de aprobacion vinculado a un objetivo y capacidad."""
        return self.approval.issue(binding, capability)

    def execute(self, mission: Mission, capability: str,
                payload: Mapping[str, Any] | None = None, *,
                approval: str | None = None,
                on_progress: Callable[[int, str], None] | None = None,
                user_id: str | None = None) -> ExecutionResult:
        """Ejecuta capacidad con validacion, timeout, auditoria.

        Las capacidades que requieren confirmacion exigen un ``approval``
        (token firmado por ``issue_approval``) vinculado a este objetivo y
        capacidad. Un booleano no basta.
        """
        start_ms = time.time() * 1000
        
        # PASO 1: Obtener spec
        item = self.registry.get(capability)
        if item is None:
            result = ExecutionResult.failure(
                f"Capacidad no disponible: {capability}", "NOT_FOUND"
            )
            self.audit.record_execution(
                mission.id, capability, False, result.code, result.message, user_id=user_id
            )
            return result
        
        spec, handler = item
        
        # PASO 2: Evaluar policy con aprobacion verificada (nunca un bool crudo)
        approved = self.approval.verify(approval, mission.objective, capability)
        decision = self.policy.evaluate(spec, confirmed=approved)
        if not decision.allowed:
            code = "CONFIRMATION_REQUIRED" if decision.confirmation_required else "DENIED"
            self.audit.record_denial(mission.id, capability, decision.reason, code=code, user_id=user_id)
            result = ExecutionResult(ok=False, code=code, message=decision.reason)
            return result
        
        # PASO 3: Crear workspace aislado
        try:
            workspace = self.workspaces.create(mission.id)
        except Exception as e:
            result = ExecutionResult.failure(f"Fallo creando workspace: {str(e)}", "WORKSPACE_FAILED")
            self.audit.record_execution(
                mission.id, capability, False, result.code, result.message, 
                stack_trace=traceback.format_exc(), user_id=user_id
            )
            return result
        
        # PASO 4: Ejecutar con timeout (threading, Windows compatible)
        request = dict(payload or {})
        request["mission_id"] = mission.id
        request["workspace"] = str(workspace)
        if on_progress:
            request["on_progress"] = on_progress
        
        try:
            result = self._execute_with_timeout(handler, request, spec.timeout_seconds)
            if not isinstance(result, ExecutionResult):
                result = ExecutionResult.failure(
                    "Resultado de capacidad invalido", "INVALID_RESULT"
                )
        except TimeoutException:
            result = ExecutionResult.timeout(spec.timeout_seconds)
        except Exception as e:
            result = ExecutionResult.failure(
                "Capacidad fallo de forma controlada",
                "CAPABILITY_FAILED",
                stack_trace=traceback.format_exc()
            )
        
        # PASO 5: Auditar COMPLETO
        duration_ms = time.time() * 1000 - start_ms
        self.audit.record_execution(
            mission.id, capability, result.ok, result.code, result.message,
            payload_input=dict(payload or {}),
            payload_output=result.payload_output,
            stack_trace=result.stack_trace,
            duration_ms=duration_ms,
            user_id=user_id
        )
        
        return result

    @staticmethod
    def _execute_with_timeout(handler: Callable, request: dict, timeout_seconds: int) -> ExecutionResult:
        """Ejecuta handler con timeout usando threading (Windows compatible)."""
        result_container = {"result": None, "exception": None}
        
        def run():
            try:
                result_container["result"] = handler(request)
            except Exception as e:
                result_container["exception"] = e
        
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        thread.join(timeout=timeout_seconds)
        
        if thread.is_alive():
            logger.warning(
                "Handler agotó el timeout de %ss; el hilo queda finalizando "
                "(no se puede matar un hilo en Python). Limitar el trabajo "
                "colgante exige aislamiento en subproceso.", timeout_seconds)
            raise TimeoutException()
        
        if result_container["exception"]:
            raise result_container["exception"]
        
        return result_container["result"]