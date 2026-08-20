"""Tests for AIProcessRunner (step 7 / N — real subprocess separation)."""

from __future__ import annotations

import importlib
import time


class TestAIProcessRunnerImport:
    """Verify module imports cleanly with no side effects."""

    def test_import_creates_no_subprocesses(self):
        import subprocess as _sp
        _orig = _sp.Popen
        spawned: list[str] = []
        def _track(*a, **kw):
            spawned.append(str(a[0] if a else "?"))
            return _orig(*a, **kw)
        _sp.Popen = _track  # type: ignore[assignment]
        try:
            mod = importlib.import_module("igris_os.ai.daemon_process")
            importlib.reload(mod)
            assert spawned == [], f"Import spawned: {spawned}"
        finally:
            _sp.Popen = _orig  # type: ignore[assignment]

    def test_runner_class_exists(self):
        from igris_os.ai.daemon_process import AIProcessRunner
        r = AIProcessRunner()
        for method in ("start", "stop", "is_alive", "health", "generate", "chat"):
            assert hasattr(r, method), f"Missing: {method}"
        assert not r.is_alive()


class TestAIProcessRunnerLifecycle:
    """start/stop/is_alive."""

    def test_start_and_stop(self):
        from igris_os.ai.daemon_process import AIProcessRunner
        r = AIProcessRunner()
        result = r.start()
        assert result["ok"] is True
        assert r.is_alive()
        r.stop()
        assert not r.is_alive()

    def test_double_start_is_idempotent(self):
        from igris_os.ai.daemon_process import AIProcessRunner
        r = AIProcessRunner()
        r.start()
        result = r.start()
        assert result["ok"] is True
        assert "already running" in result.get("reason", "")
        r.stop()

    def test_stop_when_not_started(self):
        from igris_os.ai.daemon_process import AIProcessRunner
        r = AIProcessRunner()
        r.stop()  # should not raise


class TestAIProcessRunnerHealth:
    """health() via subprocess."""

    def test_health_returns_ok(self):
        from igris_os.ai.daemon_process import AIProcessRunner
        r = AIProcessRunner()
        r.start()
        result = r.health()
        assert "ok" in result
        assert result["latency_ms"] >= 0
        r.stop()

    def test_health_auto_restarts_dead_process(self):
        from igris_os.ai.daemon_process import AIProcessRunner
        r = AIProcessRunner()
        r.start()
        # Kill the subprocess
        if r._process is not None:
            r._process.terminate()
            r._process.join(timeout=3)
        assert not r.is_alive()
        # Next call should auto-restart
        result = r.health()
        assert result.get("ok") is True
        assert r.is_alive()
        r.stop()


class TestAIProcessRunnerGenerate:
    """generate() via subprocess — requires Ollama running."""

    def test_generate_returns_dict(self):
        from igris_os.ai.daemon_process import AIProcessRunner
        r = AIProcessRunner(timeout=15)
        r.start()
        result = r.generate("responde con OK")
        assert isinstance(result, dict)
        assert "ok" in result
        assert "latency_ms" in result
        r.stop()

    def test_timeout_returns_error(self):
        """A very short timeout should return ok=False, not hang."""
        from igris_os.ai.daemon_process import AIProcessRunner
        r = AIProcessRunner(timeout=0.01)
        r.start()
        result = r.generate("este prompt no importa")
        # Either timeout or LLM error — both return ok=False
        assert result["ok"] is False
        r.stop()
