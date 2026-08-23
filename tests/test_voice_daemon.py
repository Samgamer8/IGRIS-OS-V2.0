"""Tests for VoiceDaemon facade (step 2 / N process separation)."""

from __future__ import annotations

import importlib
import sys
import types


class TestVoiceDaemonImport:
    """Verify module imports cleanly with no side effects."""

    def test_import_does_not_spawn_subprocesses(self):
        """Import must not create any subprocess or Popen object."""
        import subprocess as _sp

        _orig_popen = _sp.Popen
        spawned: list[str] = []

        def _tracking_popen(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", ["?"])
            spawned.append(str(cmd))
            return _orig_popen(*args, **kwargs)

        _sp.Popen = _tracking_popen  # type: ignore[assignment]
        try:
            mod = importlib.import_module("igris_os.voice.daemon")
            importlib.reload(mod)
            assert spawned == []
        finally:
            _sp.Popen = _orig_popen  # type: ignore[assignment]

    def test_daemon_class_exists(self):
        from igris_os.voice.daemon import VoiceDaemon

        assert VoiceDaemon is not None
        daemon = VoiceDaemon()
        assert hasattr(daemon, "health")
        assert hasattr(daemon, "speak")
        assert hasattr(daemon, "list_voices")
        assert hasattr(daemon, "close")


def test_speech_text_normalizes_markup_and_line_breaks():
    from igris_os.voice.windows import WindowsVoice

    result = WindowsVoice._speech_text("[IGRIS]\nHola **señor**.\n\n¿Todo bien?")
    assert result == "Hola señor. ¿Todo bien?"


def test_speech_text_removes_technical_symbols():
    from igris_os.voice.windows import WindowsVoice

    result = WindowsVoice._speech_text("Uso 75% en C:/tmp/a.txt; ¿de acuerdo?")
    assert result == "Uso 75 por ciento en C tmp a.txt ¿de acuerdo?"


def test_speak_replaces_pending_audio_without_interleaving():
    from igris_os.voice.windows import WindowsVoice

    voice = WindowsVoice()
    voice._speech_queue.put_nowait(("respuesta antigua", None))
    assert voice.speak("respuesta nueva") is True
    assert voice._speech_queue.get_nowait()[0] == "respuesta nueva"
    voice.close()


class TestVoiceDaemonHealth:
    """health() must return a well-formed dict."""

    def test_health_returns_dict_with_ok_field(self):
        from igris_os.voice.daemon import VoiceDaemon

        daemon = VoiceDaemon()
        result = daemon.health()
        assert isinstance(result, dict)
        assert "ok" in result
        assert "latency_ms" in result
        assert result["latency_ms"] >= 0
        daemon.close()

    def test_health_without_windowsvoice(self):
        """When WindowsVoice import fails, health returns ok=False."""
        from igris_os.voice.daemon import VoiceDaemon

        # Create daemon then break engine so _ensure_engine raises
        daemon = VoiceDaemon()
        daemon._engine_class = None  # type: ignore[assignment]
        result = daemon.health()
        assert result["ok"] is False
        assert "reason" in result
        daemon.close()


class TestVoiceDaemonSpeak:
    """speak() must validate input and return structured dict."""

    def test_speak_empty_text_returns_ok_false(self):
        from igris_os.voice.daemon import VoiceDaemon

        daemon = VoiceDaemon()
        result = daemon.speak("")
        assert result["ok"] is False
        assert "reason" in result
        daemon.close()

    def test_speak_whitespace_only_returns_ok_false(self):
        from igris_os.voice.daemon import VoiceDaemon

        daemon = VoiceDaemon()
        result = daemon.speak("   ")
        assert result["ok"] is False
        daemon.close()

    def test_speak_returns_dict_with_latency(self):
        from igris_os.voice.daemon import VoiceDaemon

        daemon = VoiceDaemon()
        result = daemon.speak("test")
        assert isinstance(result, dict)
        assert "ok" in result
        assert "latency_ms" in result
        daemon.close()


class TestVoiceDaemonListVoices:
    """list_voices() must return structured dict."""

    def test_list_voices_returns_dict(self):
        from igris_os.voice.daemon import VoiceDaemon

        daemon = VoiceDaemon()
        result = daemon.list_voices()
        assert isinstance(result, dict)
        assert "ok" in result
        assert "latency_ms" in result
        daemon.close()
