from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from uuid import uuid4


_STAGES = frozenset({"plan", "write", "deliver"})


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    request_id: str
    objective: str
    capability: str
    stage: str
    status: str
    operator: str = ""
    created_at: str = ""
    decided_at: str = ""


class SamadminStore:
    """Registro persistente de autorizaciones que IGRIS no puede autoaprobar."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "samadmin.sqlite3"
        self._initialize()

    def create(self, objective: str, capability: str, stage: str) -> ApprovalRequest:
        if not objective.strip() or not capability.strip():
            raise ValueError("Objetivo y capacidad son obligatorios")
        if stage not in _STAGES:
            raise ValueError("Fase Samadmin no permitida")
        request = ApprovalRequest(
            uuid4().hex, objective.strip(), capability.strip(), stage,
            "pending", created_at=self._now())
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO approvals "
                "(request_id, objective, capability, stage, status, operator, created_at, decided_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (request.request_id, request.objective, request.capability,
                 request.stage, request.status, request.operator,
                 request.created_at, request.decided_at))
        return request

    def get(self, request_id: str) -> ApprovalRequest | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT request_id, objective, capability, stage, status, operator, created_at, decided_at "
                "FROM approvals WHERE request_id = ?", (request_id,)).fetchone()
        return ApprovalRequest(*row) if row else None

    def decide(self, request_id: str, *, approved: bool, operator: str) -> ApprovalRequest | None:
        if not operator.strip():
            raise ValueError("Samadmin requiere un operador identificado")
        status = "approved" if approved else "rejected"
        with self._connect() as connection:
            updated = connection.execute(
                "UPDATE approvals SET status = ?, operator = ?, decided_at = ? "
                "WHERE request_id = ? AND status = 'pending'",
                (status, operator.strip(), self._now(), request_id)).rowcount
        return self.get(request_id) if updated else None

    def consume(self, request_id: str, objective: str, capability: str, stage: str) -> bool:
        """Autoriza una sola ejecución únicamente con el vínculo exacto aprobado."""
        with self._connect() as connection:
            updated = connection.execute(
                "UPDATE approvals SET status = 'consumed' "
                "WHERE request_id = ? AND objective = ? AND capability = ? "
                "AND stage = ? AND status = 'approved'",
                (request_id, objective, capability, stage)).rowcount
        return bool(updated)

    def pending(self) -> tuple[ApprovalRequest, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT request_id, objective, capability, stage, status, operator, created_at, decided_at "
                "FROM approvals WHERE status = 'pending' ORDER BY created_at").fetchall()
        return tuple(ApprovalRequest(*row) for row in rows)

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS approvals ("
                "request_id TEXT PRIMARY KEY, objective TEXT NOT NULL, "
                "capability TEXT NOT NULL, stage TEXT NOT NULL, status TEXT NOT NULL, "
                "operator TEXT NOT NULL, created_at TEXT NOT NULL, decided_at TEXT NOT NULL)")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=5)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()