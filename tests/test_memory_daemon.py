"""Tests for MemoryDaemon facade (step 3 / N process separation)."""

from __future__ import annotations

import gc
import importlib
import shutil
import tempfile
from pathlib import Path


class TestMemoryDaemonImport:
    """Verify module imports cleanly with no side effects."""

    def test_import_does_not_create_files(self):
        """Import must not create any database or directory."""
        import os

        before = set(Path(tempfile.gettempdir()).rglob("igris_memory*"))
        mod = importlib.import_module("igris_os.memory.daemon")
        importlib.reload(mod)
        after = set(Path(tempfile.gettempdir()).rglob("igris_memory*"))
        # No new files/dirs should appear on import
        assert len(after - before) == 0, (
            f"Import created new paths: {after - before}"
        )

    def test_daemon_class_exists(self):
        from igris_os.memory.daemon import MemoryDaemon

        assert MemoryDaemon is not None
        daemon = MemoryDaemon()
        assert hasattr(daemon, "health")
        assert hasattr(daemon, "remember")
        assert hasattr(daemon, "recall")
        assert hasattr(daemon, "stats")
        assert hasattr(daemon, "close")


class TestMemoryDaemonHealth:
    """health() must return a well-formed dict."""

    def test_health_returns_dict_with_ok_field(self):
        from igris_os.memory.daemon import MemoryDaemon

        # Use temp dir to avoid touching OneDrive
        tmp = Path(tempfile.mkdtemp()) / "test_memory.db"
        daemon = MemoryDaemon(db_path=tmp)
        result = daemon.health()
        assert isinstance(result, dict)
        assert "ok" in result
        assert "latency_ms" in result
        assert result["latency_ms"] >= 0
        daemon.close()
        gc.collect()
        shutil.rmtree(tmp.parent, ignore_errors=True)

    def test_health_without_memorystore(self):
        """When MemoryStore import fails, health returns ok=False."""
        from igris_os.memory.daemon import MemoryDaemon

        daemon = MemoryDaemon()
        daemon._store_class = None  # type: ignore[assignment]
        result = daemon.health()
        assert result["ok"] is False
        assert "reason" in result
        daemon.close()


class TestMemoryDaemonRemember:
    """remember() must store and return structured dict."""

    def test_remember_empty_category_returns_ok_false(self):
        from igris_os.memory.daemon import MemoryDaemon

        tmp = Path(tempfile.mkdtemp()) / "test_memory.db"
        daemon = MemoryDaemon(db_path=tmp)
        result = daemon.remember("", {"key": "value"})
        assert result["ok"] is False
        assert "reason" in result
        daemon.close()
        gc.collect()
        shutil.rmtree(tmp.parent, ignore_errors=True)

    def test_remember_empty_content_returns_ok_false(self):
        from igris_os.memory.daemon import MemoryDaemon

        tmp = Path(tempfile.mkdtemp()) / "test_memory.db"
        daemon = MemoryDaemon(db_path=tmp)
        result = daemon.remember("test", {})
        assert result["ok"] is False
        daemon.close()
        gc.collect()
        shutil.rmtree(tmp.parent, ignore_errors=True)

    def test_remember_and_recall_roundtrip(self):
        from igris_os.memory.daemon import MemoryDaemon

        tmp = Path(tempfile.mkdtemp()) / "test_memory.db"
        daemon = MemoryDaemon(db_path=tmp)
        # Remember
        store_result = daemon.remember("test", {"msg": "hello"}, verified=True)
        assert store_result["ok"] is True
        assert "memory_id" in store_result
        # Recall
        recall_result = daemon.recall("test")
        assert recall_result["ok"] is True
        assert recall_result["count"] >= 1
        assert recall_result["memories"][0]["content"]["msg"] == "hello"
        daemon.close()
        gc.collect()
        shutil.rmtree(tmp.parent, ignore_errors=True)


class TestMemoryDaemonStats:
    """stats() must return structured dict."""

    def test_stats_returns_dict(self):
        from igris_os.memory.daemon import MemoryDaemon

        tmp = Path(tempfile.mkdtemp()) / "test_memory.db"
        daemon = MemoryDaemon(db_path=tmp)
        result = daemon.stats()
        assert isinstance(result, dict)
        assert "ok" in result
        assert "total_memories" in result
        assert "total_bytes" in result
        assert "latency_ms" in result
        daemon.close()
        gc.collect()
        shutil.rmtree(tmp.parent, ignore_errors=True)
