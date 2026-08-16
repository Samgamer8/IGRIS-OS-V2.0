"""IGRIS OS V2.O - Domain Models (COMPLETO Y CORRECTO)"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable
from uuid import uuid4


class ActionRisk(str, Enum):
    """Clasificación de riesgo de una capacidad."""
    READ_ONLY = "read_only"
    WRITE_WORKSPACE = "write_workspace"
    EXTERNAL = "external"
    DESTRUCTIVE = "destructive"


class MissionState(str, Enum):
    """Estado de una misión."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MissionBranch(str, Enum):
    """Rama de ejecución de una misión (especialidad)."""
    GENERAL = "general"
    GAMES = "games"
    VIDEO = "video"
    AUDIO = "audio"
    IMAGE = "image"
    ARTIFICIAL_INTELLIGENCE = "artificial_intelligence"
    PROGRAMMING = "programming"
    DOCUMENTS = "documents"
    SYSTEMS = "systems"


@dataclass(frozen=True, slots=True)
class CapabilitySpec:
    """Especificación de una capacidad."""
    name: str
    description: str
    risk: ActionRisk
    requires_confirmation: bool = False
    timeout_seconds: int = 300
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self):
        if not self.name or len(self.name) < 3:
            raise ValueError(f"Nombre invalido: {self.name}")
        if not isinstance(self.risk, ActionRisk):
            raise ValueError(f"Risk debe ser ActionRisk, got {type(self.risk)}")
        if self.timeout_seconds < 1 or self.timeout_seconds > 3600:
            raise ValueError("Timeout fuera de rango [1, 3600]")


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Resultado de ejecución de una capacidad."""
    ok: bool
    code: str
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    payload_output: dict[str, Any] = field(default_factory=dict)
    stack_trace: str | None = None
    duration_ms: float | None = None

    @classmethod
    def success(cls, message: str = "", **data) -> ExecutionResult:
        return cls(ok=True, code="SUCCESS", message=message, data=data)

    @classmethod
    def failure(cls, message: str, code: str, stack_trace: str | None = None) -> ExecutionResult:
        return cls(ok=False, code=code, message=message, stack_trace=stack_trace)

    @classmethod
    def denied(cls, reason: str) -> ExecutionResult:
        return cls(ok=False, code="DENIED", message=reason)

    @classmethod
    def timeout(cls, seconds: int) -> ExecutionResult:
        return cls(ok=False, code="TIMEOUT", message=f"Timeout despues de {seconds}s")


@dataclass(frozen=True, slots=True)
class MissionPlan:
    """Plan de ejecución de una misión con pasos y criterios de aceptación."""
    mission_id: str
    branch: MissionBranch
    steps: tuple[str, ...] = field(default_factory=tuple)
    acceptance: tuple[str, ...] = field(default_factory=tuple)
    needs_clarification: bool = False


@dataclass(frozen=True, slots=True)
class Mission:
    """Misión (tarea de usuario)."""
    objective: str
    id: str = field(default_factory=lambda: str(uuid4())[:8])
    state: MissionState = MissionState.PENDING
    user_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.objective or len(self.objective) < 3:
            raise ValueError("Objetivo muy corto")


# Type aliases
CapabilityHandler = Callable[[dict[str, Any]], ExecutionResult]