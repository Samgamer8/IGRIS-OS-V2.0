from __future__ import annotations

import base64
import json
import os
import tempfile
import urllib.error
import urllib.request
import uuid
import winsound
from pathlib import Path
from typing import Any

from .windows import WindowsVoice


class FishAudioVoice:
    """Fish Audio backend for IGRIS.

    Design: remote API if an API key is configured; safe fallback to the native
    Windows TTS engine whenever there is no key or the remote request fails.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        reference_id: str | None = None,
        base_url: str | None = None,
        fallback: Any | None = None,
    ) -> None:
        self.api_key = (api_key or os.environ.get("IGRIS_FISH_AUDIO_API_KEY") or os.environ.get("FISH_AUDIO_API_KEY") or "").strip()
        self.model = (model or os.environ.get("IGRIS_FISH_AUDIO_MODEL") or "s2.1-pro-free").strip()
        self.reference_id = (
            reference_id or os.environ.get("IGRIS_FISH_AUDIO_REFERENCE_ID") or os.environ.get("FISH_AUDIO_REFERENCE_ID")
        )
        self.base_url = (base_url or os.environ.get("IGRIS_FISH_AUDIO_BASE_URL") or "https://api.fish.audio").rstrip("/")
        self._fallback = fallback or WindowsVoice()

    def get_installed_voices(self) -> list[str]:
        if self.api_key:
            return ["IGRIS Jarvis-inspired (Fish Audio)"]
        return ["Windows SAPI (fallback)"]

    def speak(self, text: str, voice_name: str | None = None) -> bool:
        if not text or not str(text).strip():
            return False
        clean = self._clean_text(text)
        if not clean:
            return False
        if not self.api_key:
            return self._fallback.speak(clean, voice_name)

        payload: dict[str, Any] = {
            "text": clean,
            "format": "wav",
            "sample_rate": 24000,
            "normalize": True,
            "latency": "normal",
            "prosody": {"speed": 0.95, "volume": 0, "normalize_loudness": True},
            "temperature": 0.6,
            "top_p": 0.7,
            "chunk_length": 300,
            "max_new_tokens": 1024,
            "repetition_penalty": 1.2,
            "min_chunk_length": 50,
            "condition_on_previous_chunks": True,
            "early_stop_threshold": 1,
        }
        if self.reference_id:
            payload["reference_id"] = self.reference_id
        if voice_name:
            payload["reference_id"] = voice_name

        request = urllib.request.Request(
            f"{self.base_url}/v1/tts",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "model": self.model,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                payload_bytes = response.read()
                content_type = response.headers.get_content_type() if hasattr(response.headers, "get_content_type") else ""
                audio = self._decode_audio_payload(payload_bytes, content_type)
        except Exception:
            return self._fallback.speak(clean, voice_name)

        if not audio:
            return self._fallback.speak(clean, voice_name)

        path = Path(tempfile.gettempdir()) / f"igris_fish_{uuid.uuid4().hex}.wav"
        try:
            path.write_bytes(audio)
            winsound.PlaySound(str(path), winsound.SND_FILENAME)
            return True
        except Exception:
            return self._fallback.speak(clean, voice_name)

    @staticmethod
    def _decode_audio_payload(raw: bytes, content_type: str | None) -> bytes:
        if not raw:
            return b""
        if content_type == "application/json":
            try:
                data = json.loads(raw.decode("utf-8"))
            except Exception:
                return b""
            for key in ("audio", "data", "audio_data", "result", "output"):
                value = data.get(key) if isinstance(data, dict) else None
                if isinstance(value, str):
                    if value.startswith("data:audio"):
                        _, _, b64 = value.partition(",")
                        return base64.b64decode(b64)
                    if value.startswith("http://") or value.startswith("https://"):
                        try:
                            return urllib.request.urlopen(value, timeout=30).read()
                        except Exception:
                            return b""
                    try:
                        return base64.b64decode(value)
                    except Exception:
                        return b""
                if isinstance(value, dict):
                    for nested_key in ("audio", "data", "wav", "bytes"):
                        nested = value.get(nested_key)
                        if isinstance(nested, str):
                            try:
                                return base64.b64decode(nested)
                            except Exception:
                                return b""
            return b""
        return raw

    @staticmethod
    def _clean_text(text: str) -> str:
        value = str(text).strip()
        if not value:
            return ""
        return value[:1500]
