import json
from datetime import datetime, timezone
from pathlib import Path

from igris_os.domain import ExecutionResult, Mission


class AuditLog:
    def __init__(self, path: Path) -> None:
        self.path = path

    def record(self, mission: Mission, capability: str, result: ExecutionResult) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mission_id": mission.id,
            "capability": capability,
            "ok": result.ok,
            "code": result.code,
        }
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")

