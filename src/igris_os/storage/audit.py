import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from igris_os.domain import ExecutionResult, Mission


class AuditLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def record(self, mission: Mission, capability: str, result: ExecutionResult) -> None:
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mission_id": mission.id,
            "capability": capability,
            "ok": result.ok,
            "code": result.code,
        }
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event, ensure_ascii=False) + "\n")
                stream.flush()

    def recent(self, limit: int = 20) -> list[dict]:
        if limit < 1 or limit > 500:
            raise ValueError("Limite invalido")
        if not self.path.is_file():
            return []
        events = []
        with self._lock:
            for line in self.path.read_text(encoding="utf-8").splitlines():
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(value, dict):
                    events.append(value)
        return list(reversed(events[-limit:]))
