"""VoiceDaemon — facade for WindowsVoice (step 2 / N process separation).

Exposes the same surface that any IPC boundary will need:

    health()     -> {ok, engine, voices, latency_ms}
    speak(text)  -> {ok, text, latency_ms}
    list_voices() -> {ok, voices}

No side-effects on import.  All methods return dicts (no raises).
"""

from __future__ import annotations

import time
import logging
from typing import Any

logger = logging.getLogger(__name__)


class VoiceDaemon:
    """Thin facade over WindowsVoice for eventual process isolation."""

    def __init__(self) -> None:
        self._engine: Any = None
        self._engine_class: Any = None
        # Lazy import — no side effects on module load
        try:
            from igris_os.voice.windows import WindowsVoice
            self._engine_class = WindowsVoice
        except Exception as exc:
            logger.debug("WindowsVoice import deferred: %s", exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def health(self) -> dict[str, Any]:
        """Check voice engine availability."""
        t0 = time.monotonic()
        try:
            engine = self._ensure_engine()
            voices = engine.get_installed_voices()
            latency = round((time.monotonic() - t0) * 1000, 1)
            return {
                "ok": True,
                "engine": "WindowsVoice",
                "voices": voices,
                "voice_count": len(voices),
                "latency_ms": latency,
            }
        except Exception as exc:
            latency = round((time.monotonic() - t0) * 1000, 1)
            return {
                "ok": False,
                "engine": "WindowsVoice",
                "reason": str(exc),
                "latency_ms": latency,
            }

    def speak(self, text: str, voice_name: str | None = None) -> dict[str, Any]:
        """Speak text through the voice engine."""
        if not text or not text.strip():
            return {"ok": False, "reason": "empty text", "latency_ms": 0}
        t0 = time.monotonic()
        try:
            engine = self._ensure_engine()
            result = engine.speak(text.strip(), voice_name=voice_name)
            latency = round((time.monotonic() - t0) * 1000, 1)
            return {
                "ok": bool(result),
                "text": text.strip()[:200],  # truncate for safety
                "voice_name": voice_name,
                "latency_ms": latency,
            }
        except Exception as exc:
            latency = round((time.monotonic() - t0) * 1000, 1)
            return {
                "ok": False,
                "reason": str(exc),
                "latency_ms": latency,
            }

    def list_voices(self) -> dict[str, Any]:
        """List installed TTS voices."""
        t0 = time.monotonic()
        try:
            engine = self._ensure_engine()
            voices = engine.get_installed_voices()
            latency = round((time.monotonic() - t0) * 1000, 1)
            return {
                "ok": True,
                "voices": voices,
                "voice_count": len(voices),
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

    def _ensure_engine(self) -> Any:
        """Lazy-instantiate WindowsVoice (no subprocess until first call)."""
        if self._engine is None:
            if self._engine_class is None:
                raise RuntimeError("WindowsVoice not importable")
            self._engine = self._engine_class()
        return self._engine

    def close(self) -> None:
        """Release voice engine resources."""
        if self._engine is not None:
            try:
                self._engine.close()
            except Exception:
                pass
            self._engine = None
