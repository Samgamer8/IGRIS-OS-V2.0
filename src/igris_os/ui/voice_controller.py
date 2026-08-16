from __future__ import annotations

import logging
from typing import Any

from igris_os.voice.windows import WindowsVoice


logger = logging.getLogger(__name__)


class VoiceController:
    def __init__(
        self,
        voice_engine: WindowsVoice,
        settings: dict[str, Any],
        executor: Any,
    ) -> None:
        self._voice = voice_engine
        self._settings = settings
        self._executor = executor
        self._enabled: bool = bool(self._settings.get("voice_enabled", True))

    def speak(self, text: str) -> None:
        if not self._enabled or not text.strip():
            return
        voice_name = self._settings.get("voice_name")
        try:
            self._voice.speak(text, voice_name)
        except (OSError, ValueError, RuntimeError):
            logger.debug("Voice speak failed", exc_info=True)

    def listen(self) -> str:
        if not self._enabled:
            return ""
        try:
            future = self._executor.submit(self._voice.listen)
            return future.result(timeout=12)
        except Exception:
            logger.debug("Voice listen failed", exc_info=True)
            return ""

    def toggle(self) -> bool:
        self._enabled = not self._enabled
        self._settings["voice_enabled"] = self._enabled
        return self._enabled

    def cleanup(self) -> None:
        try:
            self._voice.close()
        except (OSError, ValueError, RuntimeError):
            pass
        try:
            self._executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass
