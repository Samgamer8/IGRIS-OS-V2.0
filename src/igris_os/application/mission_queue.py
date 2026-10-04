"""Cola de misiones con recuperación atómica y validación de tamaño."""
import json
import logging
import shutil
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import tempfile

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class QueuedMission:
    id: str
    objective: str
    kind: str
    capability: str
    payload: dict
    state: str = "pending"
    attempts: int = 0
    created_at: str = ""
    message: str = ""
    progress: int = 0
    cancellation_requested: bool = False
    result: dict = field(default_factory=dict)


class MissionQueue:
    MAX_QUEUE_SIZE = 1000
    MAX_PAYLOAD_SIZE = 1024 * 1024  # 1MB
    
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.RLock()
        self._jobs = self._load_atomic()
        self._recover_running_jobs()
        self._recover_programming_questions()

    def _recover_programming_questions(self) -> None:
        """Recupera preguntas que rc4 no conservaba al guardar la cola."""
        from .programming_followup import recovered_input
        changed = False
        for job in self._jobs:
            if job.capability != 'programming.mission' or job.state not in {'failed', 'awaiting_input'}:
                continue
            data = recovered_input(job, self.path.parent)
            if data and (job.result.get('work_status') != 'needs_input' or job.state != 'awaiting_input'):
                job.result.update(data)
                job.state = 'awaiting_input'
                changed = True
        if changed:
            self._save_atomic()
        
    def _load_atomic(self) -> list[QueuedMission]:
        """Carga de forma atómica usando archivo temporal."""
        if not self.path.is_file():
            return []
        
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                return []
            
            jobs = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                try:
                    job = QueuedMission(**item)
                    # Validar payload size
                    payload_str = json.dumps(job.payload)
                    if len(payload_str.encode('utf-8')) > self.MAX_PAYLOAD_SIZE:
                        logger.warning(f"Payload demasiado grande para misión {job.id[:8]}, omitiendo")
                        continue
                    jobs.append(job)
                except (TypeError, ValueError):
                    continue
            return jobs
        except (OSError, ValueError, TypeError):
            # Si hay corrupción, intentar backup
            backup = self.path.with_suffix(".bak")
            if backup.is_file():
                try:
                    data = json.loads(backup.read_text(encoding="utf-8"))
                    return [QueuedMission(**item) for item in data if isinstance(item, dict)]
                except Exception:
                    pass
            return []
    
    def _recover_running_jobs(self) -> None:
        """Recupera misiones en estado running de forma segura."""
        recovered = False
        for job in self._jobs:
            if job.state == "running":
                interrupted_game = job.capability in {"games.godot.scaffold", "games.godot.resume",
                                                      "programming.mission", "programming.deliver"}
                job.state = "failed" if interrupted_game else "pending"
                job.message = ("Interrumpida al cerrar IGRIS. Reanuda el proyecto para recuperar el avance."
                               if interrupted_game else "Recuperada tras reinicio")
                job.progress = 0
                recovered = True
        if recovered:
            self._save_atomic()
    
    def enqueue(self, objective: str, kind: str, capability: str = "",
                payload: dict | None = None) -> QueuedMission:
        if not objective.strip() or kind not in {"chat", "capability"}:
            raise ValueError("Mision en cola invalida")
        
        # Validar tamaño de payload
        payload_str = json.dumps(payload or {})
        if len(payload_str.encode('utf-8')) > self.MAX_PAYLOAD_SIZE:
            raise ValueError(f"Payload excede {self.MAX_PAYLOAD_SIZE} bytes")
        
        # Validar tamaño de cola
        with self._lock:
            if len(self._jobs) >= self.MAX_QUEUE_SIZE:
                raise ValueError(f"Cola llena (max {self.MAX_QUEUE_SIZE})")
        
        job = QueuedMission(
            uuid4().hex, objective, kind, capability, dict(payload or {}),
            created_at=datetime.now(timezone.utc).isoformat())
        with self._lock:
            parent_id = job.payload.get('continuation_of')
            parent_snapshot = None
            if parent_id:
                parent = self._get(parent_id)
                if parent.objective != objective or parent.capability != 'programming.mission':
                    raise ValueError('La continuacion no corresponde al encargo original')
                if parent.state in {'cancelled', 'continued'} or parent.result.get('continued_by'):
                    raise ValueError('Ese encargo ya fue continuado o cancelado')
                if capability not in {'programming.mission', 'programming.deliver'}:
                    raise ValueError('Continuacion de programacion no valida')
                parent_snapshot = (parent, parent.state, dict(parent.result))
                parent.result['continued_by'] = job.id
                parent.state = 'continued'
            self._jobs.append(job)
            try:
                self._save_atomic()
            except (OSError, ValueError, TypeError):
                self._jobs.remove(job)
                if parent_snapshot:
                    parent, parent.state, parent.result = parent_snapshot
                raise
        return job
    
    def next(self) -> QueuedMission | None:
        with self._lock:
            job = next((item for item in self._jobs if item.state == "pending"), None)
            if job:
                job.state = "running"
                job.progress = max(job.progress, 1)
                job.attempts += 1
                self._save_atomic()
            return job

    def await_supervision(self, job_id: str, request_id: str) -> None:
        """Retiene una misión hasta que Samadmin apruebe la solicitud."""
        with self._lock:
            job = self._get(job_id)
            if job.state != "pending":
                raise ValueError("La misión no está pendiente")
            job.state = "awaiting_supervision"
            job.message = "Esperando Samadmin: " + request_id[:16]
            self._save_atomic()

    def release_supervision(self, job_id: str) -> None:
        with self._lock:
            job = self._get(job_id)
            if job.state != "awaiting_supervision":
                raise ValueError("La misión no espera supervisión")
            job.state = "pending"
            job.message = "Autorizada por Samadmin"
            self._save_atomic()
    
    def finish(self, job_id: str, ok: bool, message: str = "", result: dict | None = None) -> None:
        with self._lock:
            job = self._get(job_id)
            if job.state == "cancelled":
                return
            continued_by = job.result.get('continued_by')
            work_status = (result or {}).get('work_status')
            job.state = ('continued' if continued_by else
                         'awaiting_input' if work_status == 'needs_input' else
                         'awaiting_review' if work_status == 'ready_for_review' else
                         'awaiting_downloads' if work_status == 'needs_download_approval' else
                         'completed' if ok else 'failed')
            job.message = message[:1000]
            job.result = {key: str(value)[:2000] for key, value in (result or {}).items()
                          if key in {"project", "output", "diagnostic_report", "code",
                                     "staged_project", "executable", "partial_project", "checkpoint"}}
            # Keep the typed continuation contract, never stringify questions or
            # silently drop the report that points to the existing files.
            keys = {'work_status', 'questions', 'input_kind', 'understanding', 'report',
                    'work_delivery', 'requested_tools', 'project_candidates', 'model_calls', 'delivery_contract',
                    'budget', 'stop_reason', 'last_failure', 'phase', 'error_type', 'error_detail', 'artifact'}
            details = {k: v for k, v in (result or {}).items() if k in keys}
            encoded = json.dumps(details, ensure_ascii=False)
            if len(encoded.encode('utf-8')) > self.MAX_PAYLOAD_SIZE:
                raise ValueError('El resultado excede el tamano permitido para la cola')
            job.result.update(json.loads(encoded))
            if continued_by:
                job.result['continued_by'] = continued_by
            job.progress = 100
            self._save_atomic()
    
    def update_progress(self, job_id: str, progress: int, message: str = "") -> None:
        if not 0 <= progress <= 100:
            raise ValueError("Progreso invalido")
        with self._lock:
            job = self._get(job_id)
            if job.state != "running":
                raise ValueError("La mision no esta en ejecucion")
            job.progress = max(job.progress, progress)
            if message:
                job.message = message[:1000]
    
    def request_active_cancellation(self) -> bool:
        with self._lock:
            job = next((item for item in self._jobs if item.state == "running"), None)
            if not job:
                return False
            job.cancellation_requested = True
            job.message = "Cancelacion solicitada, esperando punto seguro"
            self._save_atomic()
            return True
    
    def cancellation_requested(self, job_id: str) -> bool:
        with self._lock:
            return self._get(job_id).cancellation_requested
    
    def cancel_at_safe_point(self, job_id: str) -> bool:
        with self._lock:
            job = self._get(job_id)
            if job.state != "running" or not job.cancellation_requested:
                return False
            job.state = "cancelled"
            job.progress = 100
            job.message = "Cancelada en punto seguro"
            self._save_atomic()
            return True
    
    def cancel_pending(self) -> int:
        count = 0
        with self._lock:
            for job in self._jobs:
                if job.state in {"pending", "awaiting_supervision", 'awaiting_input',
                                 'awaiting_downloads', 'awaiting_review'}:
                    job.state = "cancelled"
                    job.message = "Cancelada por el usuario"
                    job.progress = 100
                    count += 1
            self._save_atomic()
        return count
    
    def recent(self, limit: int = 10) -> list[QueuedMission]:
        with self._lock:
            return list(self._jobs[-limit:])

    def defer(self, job_id: str) -> QueuedMission:
        with self._lock:
            job = self._get(job_id)
            if job.state not in {'pending', 'awaiting_input', 'awaiting_review',
                                 'awaiting_downloads', 'awaiting_supervision', 'failed'}:
                raise ValueError('No se puede dejar pendiente una mision en ejecucion o finalizada')
            previous = (job.state, job.message, dict(job.result))
            job.result['deferred_state'] = job.state
            job.state = 'deferred'
            job.message = 'Dejada pendiente por el usuario; archivos y resultado conservados'
            try:
                self._save_atomic()
            except Exception:
                job.state, job.message, job.result = previous
                raise
            return job

    def restore_deferred(self, job_id: str) -> QueuedMission:
        with self._lock:
            job = self._get(job_id)
            if job.state != 'deferred':
                raise ValueError('La mision no esta dejada pendiente')
            previous = (job.state, job.message, dict(job.result))
            state = job.result.get('deferred_state')
            if state not in {'pending', 'awaiting_input', 'awaiting_review',
                             'awaiting_downloads', 'awaiting_supervision', 'failed'}:
                raise ValueError('El estado anterior no es recuperable')
            job.state = state
            job.result.pop('deferred_state')
            job.message = 'Encargo recuperado; pendiente de continuar su fase anterior'
            try:
                self._save_atomic()
            except Exception:
                job.state, job.message, job.result = previous
                raise
            return job

    def continue_in_place(self, job_id: str, payload: dict | None = None) -> QueuedMission:
        """Reusa la misma misión pendiente para continuar con una aclaración."""
        with self._lock:
            job = self._get(job_id)
            if payload is None:
                payload = {}
            if not isinstance(payload, dict):
                raise ValueError('La continuidad necesita un payload valido')

            merged = dict(job.payload)
            merged.update(payload)
            job.payload = merged
            job.state = 'pending'
            job.progress = 0
            job.message = 'Continuacion reactivada'
            if 'continuation_of' in payload:
                job.payload['continuation_of'] = payload['continuation_of']
            if 'objective' in payload and str(payload['objective']).strip():
                job.objective = str(payload['objective'])
            self._save_atomic()
            return job
    
    def summary(self) -> dict[str, int]:
        result = {state: 0 for state in (
            "pending", "awaiting_supervision", "running", "completed", "failed", "cancelled",
            'awaiting_input', 'awaiting_review', 'awaiting_downloads', 'continued', 'deferred')}
        with self._lock:
            for job in self._jobs:
                result[job.state] = result.get(job.state, 0) + 1
        return result
    
    def _get(self, job_id: str) -> QueuedMission:
        job = next((item for item in self._jobs if item.id == job_id), None)
        if not job:
            raise KeyError(job_id)
        return job
    
    def _save_atomic(self) -> None:
        """Guarda de forma atómica usando archivo temporal."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        
        # Crear archivo temporal en el mismo directorio
        temp_fd, temp_path = tempfile.mkstemp(
            dir=self.path.parent,
            prefix=f"{self.path.stem}.tmp",
            suffix=".json"
        )
        
        try:
            # Escribir datos al archivo temporal
            with open(temp_fd, 'w', encoding='utf-8') as f:
                json.dump([asdict(job) for job in self._jobs], f, ensure_ascii=False, indent=2)
            
            # Crear backup del archivo actual
            if self.path.is_file():
                backup = self.path.with_suffix(".bak")
                shutil.copy2(self.path, backup)
            
            # Reemplazar archivo original con temporal
            Path(temp_path).replace(self.path)
            
        except Exception as e:
            # Limpiar archivo temporal si hay error
            try:
                Path(temp_path).unlink()
            except Exception:
                pass
            raise e
