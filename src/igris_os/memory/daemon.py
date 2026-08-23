"""MemoryDaemon — facade for MemoryStore (step 3 / N process separation).

Exposes the surface that any IPC boundary will need:

    health()                       -> {ok, db_path, total_bytes, latency_ms}
    remember(category, content)    -> {ok, memory_id, latency_ms}
    recall(category, limit)        -> {ok, memories, count, latency_ms}
    stats()                        -> {ok, total_memories, total_bytes, categories}

No side-effects on import.  All methods return dicts (no raises).
"""

from __future__ import annotations

import time
import logging
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class MemoryDaemon:
    """Thin facade over MemoryStore for eventual process isolation."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._store: Any = None
        self._store_class: Any = None
        self._db_path: Path | None = Path(db_path) if db_path else None
        # Lazy import — no side effects on module load
        try:
            from igris_os.memory.store import MemoryStore
            self._store_class = MemoryStore
        except Exception as exc:
            logger.debug("MemoryStore import deferred: %s", exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def health(self) -> dict[str, Any]:
        """Check memory store accessibility."""
        t0 = time.monotonic()
        try:
            store = self._ensure_store()
            total_bytes = store.get_total_size_bytes()
            latency = round((time.monotonic() - t0) * 1000, 1)
            return {
                "ok": True,
                "db_path": str(store.path),
                "total_bytes": total_bytes,
                "total_mb": round(total_bytes / (1024 * 1024), 2),
                "latency_ms": latency,
            }
        except Exception as exc:
            latency = round((time.monotonic() - t0) * 1000, 1)
            return {
                "ok": False,
                "reason": str(exc),
                "latency_ms": latency,
            }

    def remember(self, category: str, content: dict, *, verified: bool = False) -> dict[str, Any]:
        """Store a memory entry."""
        if not category or not category.strip():
            return {"ok": False, "reason": "empty category", "latency_ms": 0}
        if not content:
            return {"ok": False, "reason": "empty content", "latency_ms": 0}
        t0 = time.monotonic()
        try:
            store = self._ensure_store()
            memory_id = store.remember(category.strip(), content, verified=verified)
            latency = round((time.monotonic() - t0) * 1000, 1)
            return {
                "ok": True,
                "memory_id": memory_id,
                "category": category.strip(),
                "latency_ms": latency,
            }
        except Exception as exc:
            latency = round((time.monotonic() - t0) * 1000, 1)
            return {
                "ok": False,
                "reason": str(exc),
                "latency_ms": latency,
            }

    def recall(self, category: str, *, limit: int = 20, verified_only: bool = True) -> dict[str, Any]:
        """Retrieve memories from a category."""
        if not category or not category.strip():
            return {"ok": False, "reason": "empty category", "latency_ms": 0}
        t0 = time.monotonic()
        try:
            store = self._ensure_store()
            memories = store.recall(category.strip(), verified_only=verified_only, limit=limit)
            latency = round((time.monotonic() - t0) * 1000, 1)
            return {
                "ok": True,
                "memories": memories,
                "count": len(memories),
                "category": category.strip(),
                "latency_ms": latency,
            }
        except Exception as exc:
            latency = round((time.monotonic() - t0) * 1000, 1)
            return {
                "ok": False,
                "reason": str(exc),
                "latency_ms": latency,
            }

    def stats(self) -> dict[str, Any]:
        """Get memory store statistics."""
        t0 = time.monotonic()
        try:
            store = self._ensure_store()
            total_bytes = store.get_total_size_bytes()
            # Count all verified memories
            categories: dict[str, int] = {}
            for cat in ["conversation", "task", "fact", "code", "error"]:
                try:
                    cnt = store.count(cat, verified_only=False)
                    if cnt > 0:
                        categories[cat] = cnt
                except Exception:
                    pass
            total_memories = sum(categories.values())
            latency = round((time.monotonic() - t0) * 1000, 1)
            return {
                "ok": True,
                "total_memories": total_memories,
                "total_bytes": total_bytes,
                "total_mb": round(total_bytes / (1024 * 1024), 2),
                "categories": categories,
                "latency_ms": latency,
            }
        except Exception as exc:
            latency = round((time.monotonic() - t0) * 1000, 1)
            return {
                "ok": False,
                "reason": str(exc),
                "latency_ms": latency,
            }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _ensure_store(self) -> Any:
        """Lazy-instantiate MemoryStore (no disk I/O until first call)."""
        if self._store is None:
            if self._store_class is None:
                raise RuntimeError("MemoryStore not importable")
            path = self._db_path or Path(tempfile.gettempdir()) / "igris_memory" / "memories.db"
            self._store = self._store_class(path)
        return self._store

    def close(self) -> None:
        """Release memory store resources."""
        if self._store is not None:
            try:
                self._store.close()
            except Exception:
                pass
            self._store = None
