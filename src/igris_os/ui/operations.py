# -*- coding: utf-8 -*-
"""Estado operativo del panel: aprobaciones pendientes y entregables.

- ``ApprovalQueue``: misiones que esperan la confirmacion explicita del
  usuario (permisos pendientes). Nada se ejecuta sin aprobacion.
- ``DeliverableRegistry``: entregas verificadas de la sesion, con deshacer
  seguro (solo elimina rutas dentro de la raiz permitida).
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class PendingApproval:
    id: str
    objective: str
    capability: str
    risk: str
    requires_confirmation: bool
    payload: dict = field(default_factory=dict)
    plan: tuple[str, ...] = ()


class ApprovalQueue:
    """Cola de permisos pendientes de confirmacion del usuario."""

    def __init__(self) -> None:
        self._items: list[PendingApproval] = []

    def add(self, objective: str, capability: str, risk: str = "",
            *, requires_confirmation: bool = True,
            payload: dict | None = None,
            plan: tuple[str, ...] = ()) -> PendingApproval:
        approval = PendingApproval(
            uuid4().hex[:8], objective, capability, risk,
            requires_confirmation, dict(payload or {}), tuple(plan))
        self._items.append(approval)
        return approval

    def pending(self) -> tuple[PendingApproval, ...]:
        return tuple(self._items)

    def pending_count(self) -> int:
        return len(self._items)

    def approve(self, approval_id: str) -> PendingApproval | None:
        return self._pop(approval_id)

    def reject(self, approval_id: str) -> PendingApproval | None:
        return self._pop(approval_id)

    def clear(self) -> int:
        count = len(self._items)
        self._items.clear()
        return count

    def _pop(self, approval_id: str) -> PendingApproval | None:
        for index, item in enumerate(self._items):
            if item.id == approval_id:
                return self._items.pop(index)
        return None


@dataclass(frozen=True, slots=True)
class Deliverable:
    mission_id: str
    objective: str
    kind: str
    path: str
    created_at: str = ""


class DeliverableRegistry:
    """Entregas verificadas de la sesion, con deshacer seguro."""

    def __init__(self) -> None:
        self._items: list[Deliverable] = []

    def record(self, mission_id: str, objective: str, kind: str,
               path: str) -> Deliverable | None:
        if not path or not Path(path).exists():
            return None
        item = Deliverable(mission_id, objective, kind, str(path),
                           datetime.now(timezone.utc).isoformat())
        self._items.append(item)
        return item

    def list(self) -> tuple[Deliverable, ...]:
        return tuple(self._items)

    def count(self) -> int:
        return len(self._items)

    def last(self) -> Deliverable | None:
        return self._items[-1] if self._items else None

    def undo_last(self) -> Deliverable | None:
        if not self._items:
            return None
        return self._items.pop()

    @staticmethod
    def discard(deliverable: Deliverable, root: Path) -> bool:
        """Elimina la entrega solo si esta dentro de la raiz permitida."""
        root = root.resolve()
        target = Path(deliverable.path).resolve()
        if not target.is_relative_to(root):
            return False
        try:
            if target.is_dir() and not target.is_symlink():
                shutil.rmtree(target)
                return True
            if target.is_file() and not target.is_symlink():
                target.unlink()
                return True
        except OSError:
            return False
        return False
