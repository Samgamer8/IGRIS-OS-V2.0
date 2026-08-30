"""VoiceDaemon — facade for WindowsVoice (step 2 / N process separation).

Exposes the same surface that any IPC boundary will need:

    health()     -> {ok, engine, voices, latency_ms}
    speak(text)  -> {ok, text, latency_ms}
    list_voices() -> {ok, voices}

No side-effects on import.  All methods return dicts (no raises).
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)


class VoiceDaemon:
    """Thin facade over the active voice backend for eventual process isolation."""

    def __init__(self) -> None:
        self._engine: Any = None
        self._engine_class: Any = None
        self._engine_name = "WindowsVoice"
        # Lazy import — no side effects on module load
        try:
            from igris_os.voice.windows import WindowsVoice
            self._engine_class = WindowsVoice
        except Exception as exc:
            logger.debug("WindowsVoice import deferred: %s", exc)

        # Prefer Fish Audio when configured; otherwise stay on Windows SAPI.
        fish_key = os.environ.get("IGRIS_FISH_AUDIO_API_KEY") or os.environ.get("FISH_AUDIO_API_KEY")
        if fish_key:
            try:
                from igris_os.voice.fish import FishAudioVoice
                self._engine_class = FishAudioVoice
                self._engine_name = "FishAudioVoice"
            except Exception as exc:
                logger.debug("FishAudioVoice import deferred: %s", exc)

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
                "engine": self._engine_name,
                "voices": voices,
                "voice_count": len(voices),
                "latency_ms": latency,
            }
        except Exception as exc:
            latency = round((time.monotonic() - t0) * 1000, 1)
            return {
                "ok": False,
                "engine": self._engine_name,
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
        """Lazy-instantiate the active voice backend."""
        if self._engine is None:
            if self._engine_class is None:
                raise RuntimeError("Voice engine not importable")
            self._engine = self._engine_class()
            self._engine_name = self._engine.__class__.__name__
        return self._engine

    def close(self) -> None:
        """Release voice engine resources."""
        if self._engine is not None:
            try:
                self._engine.close()
            except Exception:
                pass
            self._engine = None
