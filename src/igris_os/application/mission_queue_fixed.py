"""Cola de misiones con recuperación atómica y validación de tamaño."""
import json
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import tempfile


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


class MissionQueue:
    MAX_QUEUE_SIZE = 1000
    MAX_PAYLOAD_SIZE = 1024 * 1024  # 1MB
    
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.RLock()
        self._jobs = self._load_atomic()
        self._recover_running_jobs()
        
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
                job.state = "pending"
                job.message = "Recuperada tras reinicio"
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
            self._jobs.append(job)
            self._save_atomic()
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
    
    def finish(self, job_id: str, ok: bool, message: str = "") -> None:
        with self._lock:
            job = self._get(job_id)
            if job.state == "cancelled":
                return
            job.state = "completed" if ok else "failed"
            job.message = message[:1000]
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
                if job.state == "pending":
                    job.state = "cancelled"
                    job.message = "Cancelada por el usuario"
                    job.progress = 100
                    count += 1
            self._save_atomic()
        return count
    
    def recent(self, limit: int = 10) -> list[QueuedMission]:
        with self._lock:
            return list(self._jobs[-limit:])
    
    def summary(self) -> dict[str, int]:
        result = {state: 0 for state in (
            "pending", "running", "completed", "failed", "cancelled")}
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
                self.path.replace(backup)
            
            # Reemplazar archivo original con temporal
            Path(temp_path).replace(self.path)
            
        except Exception as e:
            # Limpiar archivo temporal si hay error
            try:
                Path(temp_path).unlink()
            except Exception:
                pass
            raise e
