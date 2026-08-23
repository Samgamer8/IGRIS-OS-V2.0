"""Auditoria reforzada con payload completo y compatibilidad backward."""
import json
import logging
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from igris_os.domain.models import ExecutionResult, Mission

logger = logging.getLogger(__name__)

class AuditLog:
    # Rotación simple: el archivo actual nunca supera MAX_BYTES; al alcanzar
    # el límite se archiva a .1 y se abre uno nuevo. Evita crecimiento
    # ilimitado del JSONL en sesiones largas.
    MAX_BYTES = 5 * 1024 * 1024
    _ARCHIVE_SUFFIX = ".1"

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # MÉTODO ANTIGUO (backward compatibility)
    def record(self, mission: Mission, capability: str, result: ExecutionResult) -> None:
        """Compatibilidad con tests antiguos."""
        self.record_execution(
            mission.id, capability, result.ok, result.code, result.message,
            payload_output=result.payload_output,
            stack_trace=result.stack_trace,
            duration_ms=result.duration_ms
        )

    # MÉTODO NUEVO (refactorizado)
    def record_execution(self, mission_id: str, capability: str, ok: bool, 
                        code: str, message: str, payload_input: dict[str, Any] | None = None,
                        payload_output: dict[str, Any] | None = None, 
                        stack_trace: str | None = None, duration_ms: float | None = None,
                        user_id: str | None = None) -> None:
        """Registra ejecución COMPLETA."""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mission_id": mission_id,
            "capability": capability,
            "ok": ok,
            "code": code,
            "message": self._redact_text(message),
            "user_id": user_id,
            "duration_ms": duration_ms,
            "payload_input": self._sanitize(payload_input),
            "payload_output": self._sanitize(payload_output),
            "stack_trace": self._redact_text(stack_trace),
        }
        
        with self._lock:
            try:
                self._rotate_if_needed()
                with self.path.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
                    stream.flush()
            except Exception as e:
                logger.error(f"Fallo escribiendo audit: {e}")

    def _rotate_if_needed(self) -> None:
        """Archiva el JSONL actual si supera el limite de tamaño."""
        try:
            if self.path.exists() and self.path.stat().st_size >= self.MAX_BYTES:
                archive = self.path.with_suffix(self.path.suffix + self._ARCHIVE_SUFFIX)
                archive.unlink(missing_ok=True)
                self.path.replace(archive)
        except OSError as exc:
            logger.warning("No se pudo rotar audit: %s", exc)

    def record_denial(self, mission_id: str, capability: str, reason: str, 
                     code: str = "DENIED", user_id: str | None = None) -> None:
        """Registra INTENTO DE ACCESO DENEGADO."""
        self.record_execution(
            mission_id, capability, ok=False, code=code, 
            message=reason, user_id=user_id
        )

    _SECRET_PATTERNS = (
        re.compile(r"(sk|pk|api[_-]?key|token|secret|password|passwd)", re.I),
        re.compile(r"(Bearer\s+)[A-Za-z0-9._~+/-]+=*"),
        re.compile(r"(AKIA|ASIA)[A-Z0-9]{16}"),
        re.compile(r"(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}"),
        re.compile(r"\b[0-9a-fA-F]{40,}\b"),
    )

    @classmethod
    def _redact_text(cls, text: str | None) -> str | None:
        """Redacta secretos incrustados en texto libre (mensajes y trazas)."""
        if not text:
            return text
        redacted = text
        for pattern in cls._SECRET_PATTERNS:
            redacted = pattern.sub("***REDACTED***", redacted)
        return redacted

    @staticmethod
    def _sanitize(data: dict[str, Any] | None) -> dict[str, Any] | None:
        """Elimina datos sensibles."""
        if not data:
            return None
        filtered = {}
        sensitive_keys = {"password", "token", "secret", "api_key", "private_key"}
        for k, v in data.items():
            if k.lower() in sensitive_keys:
                filtered[k] = "***REDACTED***"
            elif isinstance(v, dict):
                filtered[k] = AuditLog._sanitize(v)
            elif isinstance(v, list):
                filtered[k] = [
                    AuditLog._sanitize(item) if isinstance(item, dict) else item
                    for item in v
                ]
            else:
                filtered[k] = v
        return filtered

    def recent(self, limit: int = 20) -> list[dict]:
        """Lee últimos N eventos."""
        if limit < 1 or limit > 500:
            raise ValueError("Limite invalido")
        if not self.path.is_file():
            return []
        
        events = []
        with self._lock:
            try:
                for line in self.path.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    try:
                        event = json.loads(line)
                        if isinstance(event, dict):
                            events.append(event)
                    except json.JSONDecodeError:
                        logger.warning(f"Linea de audit invalida")
            except Exception as e:
                logger.error(f"Fallo leyendo audit: {e}")
        
        return list(reversed(events[-limit:]))