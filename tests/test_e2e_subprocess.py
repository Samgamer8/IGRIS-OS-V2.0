"""E2E test: verify AI subprocess separation works end-to-end.

Tests the full chain: IgrisDaemon → AIProcessRunner → subprocess → AIDaemon → Ollama.

This verifies the architecture works WITHOUT needing a display server or Qt.
The actual Qt integration is tested by the headless panel test (test_e2e_panel.py).

Run with: python -m pytest tests/test_e2e_subprocess.py -v
Requires: Ollama running (for generate test).
"""

from __future__ import annotations

import time


class TestE2ESubprocessChain:
    """Full chain: IgrisDaemon → AIProcessRunner → subprocess."""

    def test_full_chain_health(self):
        """IgrisDaemon with AIProcessRunner reports all subsystems healthy."""
        from igris_os.core.igrisd import IgrisDaemon
        from igris_os.ai.daemon_process import AIProcessRunner

        runner = AIProcessRunner(timeout=10)
        runner.start()
        assert runner.is_alive()

        igrisd = IgrisDaemon(ai_runner=runner)
        health = igrisd.health_all()

        assert health["ok"] is True, f"health_all failed: {health}"
        assert health["subsystems"]["ai"]["ok"] is True
        assert health["healthy_count"] >= 3  # at least ai, voice, memory

        igrisd.close()
        assert not runner.is_alive()

    def test_full_chain_chat(self):
        """IgrisDaemon.chat routes through AI subprocess."""
        from igris_os.core.igrisd import IgrisDaemon
        from igris_os.ai.daemon_process import AIProcessRunner

        runner = AIProcessRunner(timeout=15)
        runner.start()

        igrisd = IgrisDaemon(ai_runner=runner)

        # Chat routes through conversation daemon (in-process)
        # but AI calls within it go through the subprocess
        result = igrisd.execute("responde solo: OK")
        assert isinstance(result, dict)
        assert "ok" in result
        assert result["latency_ms"] >= 0

        igrisd.close()

    def test_full_chain_memory(self):
        """IgrisDaemon.remember/recall works alongside subprocess AI."""
        from igris_os.core.igrisd import IgrisDaemon
        from igris_os.ai.daemon_process import AIProcessRunner
        import tempfile
        from pathlib import Path

        runner = AIProcessRunner(timeout=10)
        runner.start()

        # Create igrisd with custom memory path
        igrisd = IgrisDaemon(ai_runner=runner)
        # Override memory with temp path
        from igris_os.memory.daemon import MemoryDaemon
        tmp = Path(tempfile.mkdtemp()) / "e2e_test.db"
        igrisd._memory = MemoryDaemon(db_path=tmp)

        # Remember (verified) and recall
        rem = igrisd.remember("e2e_test", {"key": "value"}, verified=True)
        assert rem["ok"] is True

        rec = igrisd.recall("e2e_test")
        assert rec["ok"] is True
        assert rec["count"] >= 1

        # AI still works alongside memory
        health = igrisd.health_all()
        assert health["subsystems"]["ai"]["ok"] is True
        assert health["subsystems"]["memory"]["ok"] is True

        igrisd.close()

        # Cleanup
        import gc, shutil
        gc.collect()
        shutil.rmtree(tmp.parent, ignore_errors=True)

    def test_subprocess_survives_rapid_calls(self):
        """Multiple rapid calls don't crash the subprocess."""
        from igris_os.ai.daemon_process import AIProcessRunner

        runner = AIProcessRunner(timeout=10)
        runner.start()

        for i in range(5):
            result = runner.health()
            assert result.get("ok") is True, f"Call {i} failed: {result}"

        assert runner.is_alive()
        runner.stop()

    def test_subprocess_restart_after_crash(self):
        """If subprocess dies, next call auto-restarts it."""
        from igris_os.ai.daemon_process import AIProcessRunner

        runner = AIProcessRunner(timeout=10)
        runner.start()
        assert runner.is_alive()

        # Get the PID
        old_pid = runner._process.pid

        # Kill it
        runner._process.terminate()
        runner._process.join(timeout=3)
        assert not runner.is_alive()

        # Next call should auto-restart
        result = runner.health()
        assert result.get("ok") is True
        assert runner.is_alive()
        assert runner._process.pid != old_pid  # new PID

        runner.stop()
