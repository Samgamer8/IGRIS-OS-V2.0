from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping
from uuid import uuid4


class ActionRisk(str, Enum):
    READ_ONLY = "read_only"
    WRITE_WORKSPACE = "write_workspace"
    EXTERNAL = "external"
    DESTRUCTIVE = "destructive"


class MissionState(str, Enum):
    RECEIVED = "received"
    RUNNING = "running"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"


class MissionBranch(str, Enum):
    PROGRAMMING = "programming"
    ARTIFICIAL_INTELLIGENCE = "artificial_intelligence"
    GAMES = "games"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENTS = "documents"
    SYSTEMS = "systems"
    GENERAL = "general"


@dataclass(frozen=True, slots=True)
class Mission:
    objective: str
    id: str = field(default_factory=lambda: uuid4().hex)

    def __post_init__(self) -> None:
        if not self.objective.strip():
            raise ValueError("La mision necesita un objetivo")


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    ok: bool
    message: str
    code: str = "OK"
    data: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def success(cls, message: str, **data: Any) -> "ExecutionResult":
        return cls(True, message, data=data)

    @classmethod
    def failure(cls, message: str, code: str) -> "ExecutionResult":
        return cls(False, message, code)


CapabilityHandler = Callable[[Mapping[str, Any]], ExecutionResult]


@dataclass(frozen=True, slots=True)
class CapabilitySpec:
    name: str
    description: str
    risk: ActionRisk
    requires_confirmation: bool = False


@dataclass(frozen=True, slots=True)
class MissionPlan:
    mission_id: str
    branch: MissionBranch
    steps: tuple[str, ...]
    acceptance: tuple[str, ...]
    needs_clarification: bool = False
