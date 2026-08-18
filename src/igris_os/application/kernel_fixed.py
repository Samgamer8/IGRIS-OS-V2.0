"""Kernel robusto con timeout usando subprocesos (Windows compatible)."""
from __future__ import annotations
import logging
import multiprocessing
import queue
import subprocess
import sys
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


def _run_handler_in_subprocess(handler: Callable, request: dict, result_queue: multiprocessing.Queue) -> None:
    """Ejecuta handler en subproceso separado para poder matarlo."""
    try:
        result = handler(request)
        result_queue.put(("success", result))
    except Exception as e:
        result_queue.put(("error", e))


class IgrisKernel:
    def __init__(self, registry: CapabilityRegistry, policy: PermissionPolicy,
                 audit: AuditLog, workspaces: MissionWorkspace,
                 approval: ApprovalAuthority | None = None) -> None:
        self.registry = registry
        self.policy = policy
        self.audit = audit
        self.workspaces = workspaces
        self.approval = approval or ApprovalAuthority()
        self._active_processes: dict[str, subprocess.Popen] = {}

    def issue_approval(self, binding: str, capability: str) -> str:
        """Emite un token de aprobacion vinculado a un objetivo y capacidad."""
        return self.approval.issue(binding, capability)

    def execute(self, mission: Mission, capability: str,
                payload: Mapping[str, Any] | None = None, *,
                approval: str | None = None,
                on_progress: Callable[[int, str], None] | None = None,
                user_id: str | None = None) -> ExecutionResult:
        """Ejecuta capacidad con validacion, timeout, auditoria."""
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
        
        # PASO 2: Evaluar policy con aprobacion verificada
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
        
        # PASO 4: Ejecutar con timeout usando subprocesos (Windows compatible)
        request = dict(payload or {})
        request["mission_id"] = mission.id
        request["workspace"] = str(workspace)
        if on_progress:
            request["on_progress"] = on_progress
        
        try:
            result = self._execute_with_timeout(handler, request, spec.timeout_seconds, mission.id)
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

    def _execute_with_timeout(self, handler: Callable, request: dict, 
                             timeout_seconds: int, mission_id: str) -> ExecutionResult:
        """Ejecuta handler con timeout usando subprocesos (Windows compatible)."""
        result_queue = multiprocessing.Queue()
        
        # Crear subproceso para ejecutar el handler
        process = multiprocessing.Process(
            target=_run_handler_in_subprocess,
            args=(handler, request, result_queue)
        )
        
        self._active_processes[mission_id] = process
        process.start()
        
        try:
            # Esperar resultado con timeout
            process.join(timeout=timeout_seconds)
            
            if process.is_alive():
                # Timeout: matar el proceso
                process.terminate()
                process.join(timeout=2)
                if process.is_alive():
                    process.kill()
                    process.join()
                logger.warning(f"Proceso para misión {mission_id[:8]} matado por timeout")
                raise TimeoutException()
            
            # Obtener resultado
            try:
                status, data = result_queue.get(timeout=1)
                if status == "success":
                    return data
                else:
                    raise data
            except queue.Empty:
                raise TimeoutException("No se obtuvo resultado del subproceso")
                
        finally:
            self._active_processes.pop(mission_id, None)
            if process.is_alive():
                process.terminate()
                process.join(timeout=1)
                if process.is_alive():
                    process.kill()
