"""IGRIS OS V3.0 — Contratos formales del núcleo (Paso 1).

Superficie estable que todo módulo que cruce la frontera del orquestador
debe respetar: ``Request``, ``Response``, ``Error``, ``Health``, ``Event``
y ``JobState``.

Reglas:
  * Sin estado a nivel de módulo.
  * Sin IO en el import.
  * Dataclasses ``frozen`` y ``slots`` con validación en ``__post_init__``.
  * Los métodos de fábrica nunca lanzan excepciones por entrada inválida
    en los payloads heredados; la validación estricta queda en los
    constructores directos.

Este módulo NO cambia el comportamiento de los daemons existentes: es la
superficie contractual sobre la que se hará el cableado en pasos
posteriores.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


class ErrorCode(str, Enum):
    """Códigos de error estándar del núcleo."""

    BAD_REQUEST = "bad_request"
    NOT_FOUND = "not_found"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    DENIED = "denied"
    INVALID_MODEL = "invalid_model"
    INTERNAL = "internal"


class JobState(str, Enum):
    """Máquina de estados de una petición en el orquestador."""

    RECEIVED = "received"
    UNDERSTANDING = "understanding"
    PLANNED = "planned"
    APPROVAL_REQUIRED = "approval_required"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLED_BACK = "rolled_back"

    def can_transition_to(self, next_state: "JobState") -> bool:
        """True si la transición self → next_state es válida."""
        allowed = _JOB_TRANSITIONS.get(self.value, frozenset())
        return next_state.value in allowed


# Mapa de transiciones válidas por valor. Vive fuera de la clase porque en
# Python los nombres con un solo guion bajo inicial (p. ej. ``_TRANSITIONS``)
# sí se convierten en miembros del Enum.
_JOB_TRANSITIONS: dict[str, frozenset[str]] = {
    "received": frozenset({"understanding", "cancelled"}),
    "understanding": frozenset({"planned", "failed", "cancelled"}),
    "planned": frozenset({"approval_required", "executing", "failed", "cancelled"}),
    "approval_required": frozenset({"executing", "cancelled"}),
    "executing": frozenset({"verifying", "failed", "cancelled", "rolled_back"}),
    "verifying": frozenset({"completed", "failed", "rolled_back"}),
    "completed": frozenset(),
    "failed": frozenset(),
    "cancelled": frozenset(),
    "rolled_back": frozenset(),
}


class EventType(str, Enum):
    """Tipos de eventos emitidos por el núcleo."""

    RECEIVED = "received"
    PLANNED = "planned"
    STARTED = "started"
    PROGRESS = "progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DENIED = "denied"
    ROLLED_BACK = "rolled_back"
    HEALTH_CHANGED = "health_changed"


# ----------------------------------------------------------------------
# Error
# ----------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Error:
    """Error estructurado del núcleo."""

    code: ErrorCode
    message: str
    detail: str | None = None
    recoverable: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.code, ErrorCode):
            raise ValueError(f"code debe ser ErrorCode, got {type(self.code)}")
        if not self.message or not self.message.strip():
            raise ValueError("Error.message no puede estar vacio")

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "message": self.message,
            "detail": self.detail,
            "recoverable": self.recoverable,
        }


# ----------------------------------------------------------------------
# Request / Response
# ----------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Request:
    """Petición hacia el orquestador o un daemon."""

    method: str
    payload: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid4()))
    trace_id: str | None = None
    timeout_ms: int = 30_000
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not self.method or not self.method.strip():
            raise ValueError("Request.method no puede estar vacio")
        if self.timeout_ms < 0:
            raise ValueError("Request.timeout_ms no puede ser negativo")


@dataclass(frozen=True, slots=True)
class Response:
    """Respuesta estándar del orquestador o un daemon."""

    ok: bool
    request_id: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    error: Error | None = None
    latency_ms: float = 0.0

    def __post_init__(self) -> None:
        if self.ok and self.error is not None:
            raise ValueError("Una respuesta ok no puede llevar error")
        if not self.ok and self.error is None:
            raise ValueError("Una respuesta fallida requiere error")

    @classmethod
    def ok_response(
        cls,
        request_id: str = "",
        data: dict[str, Any] | None = None,
    ) -> "Response":
        return cls(ok=True, request_id=request_id, data=data or {})

    @classmethod
    def error_response(
        cls,
        code: ErrorCode,
        message: str,
        request_id: str = "",
        detail: str | None = None,
        recoverable: bool = False,
    ) -> "Response":
        return cls(
            ok=False,
            request_id=request_id,
            error=Error(code=code, message=message, detail=detail,
                        recoverable=recoverable),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "request_id": self.request_id,
            "data": self.data,
            "error": None if self.error is None else self.error.to_dict(),
            "latency_ms": self.latency_ms,
        }


def response_from_payload(payload: dict[str, Any], request_id: str = "") -> Response:
    """Normaliza el dict heredado de los daemons a un ``Response``.

    ``data`` preserva TODO el payload salvo la envoltura (``ok``,
    ``error``/``reason``, ``latency_ms`` y metadatos de cola).  No hay
    whitelist: un campo nuevo del daemon (p. ej. ``models``) cruza la
    frontera sin pérdida, que es lo que exige el IPC contractual.
    """
    ok = bool(payload.get("ok"))
    error = payload.get("error") or payload.get("reason") or ""
    envelope = {"ok", "error", "reason", "latency_ms", "request_id", "id"}
    data = {k: v for k, v in payload.items() if k not in envelope}
    if not ok:
        code = ErrorCode.INTERNAL
        message = str(error) if error else "Fallo sin detalle"
        return Response.error_response(code, message, request_id=request_id)
    return Response.ok_response(request_id=request_id, data=data)


# ----------------------------------------------------------------------
# Health
# ----------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Health:
    """Estado de salud de un componente."""

    component: str
    ok: bool
    checks: dict[str, bool] = field(default_factory=dict)
    latency_ms: float = 0.0
    version: str = ""

    @property
    def all_ok(self) -> bool:
        return self.ok and all(self.checks.values())

    @classmethod
    def aggregate(
        cls,
        component: str,
        items: dict[str, dict[str, Any]],
        latency_ms: float = 0.0,
    ) -> "Health":
        """Construye Health a partir de {nombre: {ok: bool, ...}}."""
        checks = {name: bool(item.get("ok")) for name, item in items.items()}
        ok = bool(checks) and all(checks.values())
        return cls(component=component, ok=ok, checks=checks,
                   latency_ms=latency_ms)

    def to_dict(self) -> dict[str, Any]:
        return {
            "component": self.component,
            "ok": self.ok,
            "checks": self.checks,
            "latency_ms": self.latency_ms,
            "version": self.version,
        }


# ----------------------------------------------------------------------
# Event / JobStatus
# ----------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Event:
    """Evento inmutable emitido por el núcleo."""

    type: EventType
    job_id: str = ""
    trace_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    occurred_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not isinstance(self.type, EventType):
            raise ValueError(f"type debe ser EventType, got {type(self.type)}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "job_id": self.job_id,
            "trace_id": self.trace_id,
            "payload": self.payload,
            "occurred_at": self.occurred_at,
        }


@dataclass(frozen=True, slots=True)
class JobStatus:
    """Estado observable de una petición en el orquestador."""

    job_id: str
    state: JobState
    progress: int = 0
    message: str = ""
    updated_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not self.job_id:
            raise ValueError("JobStatus.job_id no puede estar vacio")
        if not isinstance(self.state, JobState):
            raise ValueError(f"state debe ser JobState, got {type(self.state)}")
        if self.progress < 0 or self.progress > 100:
            raise ValueError("JobStatus.progress fuera de [0, 100]")

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "state": self.state.value,
            "progress": self.progress,
            "message": self.message,
            "updated_at": self.updated_at,
        }
