import json
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


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
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.RLock()
        self._jobs = self._load()
        recovered = False
        for job in self._jobs:
            if job.state == "running":
                job.state = "pending"
                job.message = "Recuperada tras reinicio"
                job.progress = 0
                recovered = True
        if recovered:
            self._save()

    def enqueue(self, objective: str, kind: str, capability: str = "",
                payload: dict | None = None) -> QueuedMission:
        if not objective.strip() or kind not in {"chat", "capability"}:
            raise ValueError("Mision en cola invalida")
        job = QueuedMission(
            uuid4().hex, objective, kind, capability, dict(payload or {}),
            created_at=datetime.now(timezone.utc).isoformat())
        with self._lock:
            self._jobs.append(job)
            self._save()
        return job

    def next(self) -> QueuedMission | None:
        with self._lock:
            job = next((item for item in self._jobs if item.state == "pending"), None)
            if job:
                job.state = "running"
                job.progress = max(job.progress, 1)
                job.attempts += 1
                self._save()
            return job

    def finish(self, job_id: str, ok: bool, message: str = "") -> None:
        with self._lock:
            job = self._get(job_id)
            if job.state == "cancelled":
                return
            job.state = "completed" if ok else "failed"
            job.message = message[:1000]
            job.progress = 100
            self._save()

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
            self._save()

    def request_active_cancellation(self) -> bool:
        with self._lock:
            job = next((item for item in self._jobs if item.state == "running"), None)
            if not job:
                return False
            job.cancellation_requested = True
            job.message = "Cancelacion solicitada, esperando punto seguro"
            self._save()
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
            self._save()
            return True

    def cancel_at_safe_point(self, job_id: str) -> bool:
        with self._lock:
            job = self._get(job_id)
            if job.state != "running" or not job.cancellation_requested:
                return False
            job.state = "cancelled"
            job.progress = 100
            job.message = "Cancelada en punto seguro"
            self._save()
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
            self._save()
        return count

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

    def _load(self) -> list[QueuedMission]:
        if not self.path.is_file():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return [QueuedMission(**item) for item in data if isinstance(item, dict)]
        except (OSError, ValueError, TypeError):
            return []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(
            [asdict(job) for job in self._jobs], ensure_ascii=False, indent=2),
            encoding="utf-8")
        temporary.replace(self.path)
