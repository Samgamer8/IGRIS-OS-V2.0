"""Kernel robusto con timeout en subproceso y fallback en hilo.

El timeout de una capacidad se resuelve en dos caminos complementarios:

1. **Subproceso** (``multiprocessing.Process``): permite matar de verdad un
   handler que cuelga (compatible con Windows/POSIX). Solo es viable cuando el
   handler y su payload son ``pickle``-ables (funciones a nivel de modulo). El
   progreso se comunica por cola y lo reenvia el padre en su propio proceso.
2. **Hilo daemon** (fallback): para handlers no ``pickle``-ables (lambdas o
   closures, que son la mayoria de las capacidades registradas). Python no
   puede matar un hilo, asi que aqui el timeout es "soft": se devuelve
   ``TIMEOUT`` y el hilo queda finalizando en segundo plano. Es la limitacion
   documentada y asumida del modelo de handlers en-proceso.
"""
from __future__ import annotations

import logging
import multiprocessing
import pickle
import queue
import threading
import time
import traceback
from functools import partial
from typing import Any, Callable, Mapping

from igris_os.application.approval import ApprovalAuthority
from igris_os.application.registry import CapabilityRegistry
from igris_os.domain.models import ActionRisk, ExecutionResult, Mission
from igris_os.security import PermissionPolicy
from igris_os.storage.audit import AuditLog
from igris_os.storage.workspace import MissionWorkspace

logger = logging.getLogger(__name__)

_PROGRESS = "progress"
_SUCCESS = "success"
_ERROR = "error"


class TimeoutException(Exception):
    pass


def _run_handler_in_subprocess(handler: Callable, request: dict,
                               result_queue: multiprocessing.Queue) -> None:
    """Ejecuta el handler en un subproceso y comunica resultado/progreso.

    Nunca deja escapar la excepcion: el padre distingue ``success``/``error``
    por el primer elemento de la tupla encolada.
    """
    try:
        result = handler(request)
        result_queue.put((_SUCCESS, result))
    except Exception as exc:
        child_traceback = traceback.format_exc()
        try:
            result_queue.put((_ERROR, exc, child_traceback))
        except Exception:
            # Si ni la excepcion es pickleable, el padre observara un proceso
            # muerto sin resultado y lo tratara como fallo controlado.
            pass


def _queue_progress(result_queue: multiprocessing.Queue,
                    pct: int, msg: str) -> None:
    """Stub ``on_progress`` pickleable que encola el evento hacia el padre."""
    result_queue.put((_PROGRESS, pct, msg))


class IgrisKernel:
    def __init__(self, registry: CapabilityRegistry, policy: PermissionPolicy,
                 audit: AuditLog, workspaces: MissionWorkspace,
                 approval: ApprovalAuthority | None = None) -> None:
        self.registry = registry
        self.policy = policy
        self.audit = audit
        self.workspaces = workspaces
        self.approval = approval or ApprovalAuthority()
        self._active_processes: dict[str, multiprocessing.Process] = {}

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

        # PASO 4: Ejecutar con timeout (subproceso cuando es viable, hilo si no)
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
        """Elige el camino de ejecucion segun la picklabilidad del handler."""
        if self._subprocess_safe(handler, request):
            return self._run_in_subprocess(handler, request, timeout_seconds, mission_id)
        return self._run_in_thread(handler, request, timeout_seconds)

    @staticmethod
    def _subprocess_safe(handler: Callable, request: dict) -> bool:
        """True si handler y payload (sin on_progress) son pickleables."""
        probe = dict(request)
        probe.pop("on_progress", None)
        try:
            pickle.dumps((handler, probe))
            return True
        except Exception:
            return False

    def _run_in_subprocess(self, handler: Callable, request: dict,
                           timeout_seconds: int, mission_id: str) -> ExecutionResult:
        """Ejecuta en subproceso con kill duro y progreso reenviado al padre."""
        user_progress = request.get("on_progress")
        result_queue: multiprocessing.Queue = multiprocessing.Queue()

        # El on_progress del usuario no puede cruzar a otro proceso: se
        # sustituye por un stub pickleable que encola los eventos.
        child_request = dict(request)
        if user_progress is not None:
            child_request["on_progress"] = partial(_queue_progress, result_queue)
        else:
            child_request.pop("on_progress", None)

        process = multiprocessing.Process(
            target=_run_handler_in_subprocess,
            args=(handler, child_request, result_queue),
        )
        self._active_processes[mission_id] = process
        try:
            process.start()
        except Exception as exc:
            # El probe deberia haberlo evitado, pero ante cualquier sorpresa
            # del pickler de spawn se degrada a hilo en vez de fallar.
            self._active_processes.pop(mission_id, None)
            logger.warning("Subproceso no arranco (%s); se ejecuta en hilo", exc)
            return self._run_in_thread(handler, request, timeout_seconds)

        deadline = time.monotonic() + timeout_seconds
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._terminate(process)
                    logger.warning(
                        "Proceso de mision %s matado por timeout (%ss)",
                        mission_id[:8], timeout_seconds,
                    )
                    raise TimeoutException()

                try:
                    message = result_queue.get(timeout=min(remaining, 0.2))
                except queue.Empty:
                    if not process.is_alive():
                        # Murio sin dejar resultado encolado.
                        raise TimeoutException("El subproceso termino sin entregar resultado")
                    continue

                status = message[0]
                if status == _PROGRESS:
                    _, pct, msg = message
                    if user_progress is not None:
                        user_progress(pct, msg)
                    continue
                if status == _SUCCESS:
                    return message[1]
                if status == _ERROR:
                    _, exc, child_traceback = message
                    if child_traceback:
                        logger.error("Fallo en subproceso (traceback del hijo):\n%s", child_traceback)
                    raise exc
                logger.warning("Mensaje desconocido del subproceso: %r", status)
        finally:
            self._active_processes.pop(mission_id, None)
            self._terminate(process)

    @staticmethod
    def _terminate(process: multiprocessing.Process) -> None:
        if process is None or not process.is_alive():
            return
        process.terminate()
        process.join(timeout=2)
        if process.is_alive():
            process.kill()
            process.join(timeout=2)

    @staticmethod
    def _run_in_thread(handler: Callable, request: dict,
                       timeout_seconds: int) -> ExecutionResult:
        """Ejecuta en hilo daemon: timeout soft, el hilo no se puede matar."""
        container: dict[str, Any] = {"result": None, "exception": None}

        def run() -> None:
            try:
                container["result"] = handler(request)
            except Exception as exc:
                container["exception"] = exc

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        thread.join(timeout=timeout_seconds)

        if thread.is_alive():
            logger.warning(
                "Handler no pickleable agoto el timeout de %ss en hilo; "
                "el hilo queda finalizando (Python no puede matar hilos).",
                timeout_seconds,
            )
            raise TimeoutException()

        if container["exception"] is not None:
            raise container["exception"]

        return container["result"]
