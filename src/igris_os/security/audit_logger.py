"""Registro JSONL de decisiones de permisos; no es almacenamiento inmutable."""
from __future__ import annotations

import json
import re
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class SecurityAuditEvent:
    timestamp: str
    event_type: str
    severity: str
    capability: str
    allowed: bool
    reason: str
    risk_level: str
    details: dict[str, Any]


class SecurityAuditLogger:
    _lock = threading.Lock()
    _sensitive = re.compile(r"password|passwd|secret|token|credential|authorization|api.?key|private.?key", re.I)

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path or "runtime/logs/security_audit.jsonl")

    @classmethod
    def _sanitize(cls, value):
        if isinstance(value, dict):
            return {str(k): "[REDACTED]" if cls._sensitive.search(str(k))
                    else cls._sanitize(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._sanitize(v) for v in value]
        return value

    def log(self, event_type: str, severity: str, capability: str,
            allowed: bool, reason: str, risk_level: str,
            details: dict[str, Any] | None = None) -> SecurityAuditEvent:
        event = SecurityAuditEvent(
            datetime.now(timezone.utc).isoformat(), event_type, severity,
            capability, allowed, reason, risk_level, self._sanitize(details or {}))
        line = json.dumps(asdict(event), ensure_ascii=False, default=str) + "\n"
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(line)
                stream.flush()
        return event
