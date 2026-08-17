from __future__ import annotations

import json
import re
import time
import urllib.request
import urllib.error
from typing import Any


class ContextCompressor:
    def __init__(self, ollama_url: str = "http://127.0.0.1:11434") -> None:
        if not ollama_url.startswith(("http://127.0.0.1", "http://localhost")):
            raise ValueError("Ollama debe usar loopback")
        self.ollama_url = ollama_url.rstrip("/")
        self._ollama_available: bool | None = None
        self._ollama_check_time: float = 0.0

    def estimate_tokens(self, text: str) -> int:
        ratio = 2.0 if re.search(r"[áéíóúñÁÉÍÓÚÑüÜ]", text) else 4.0
        return max(1, int(len(text) / ratio))

    def prune_oldest(self, conversation: list[dict], keep_last: int = 10) -> list[dict]:
        if len(conversation) <= keep_last:
            return conversation
        old = conversation[:-keep_last]
        recent = conversation[-keep_last:]
        summary = self.fallback_summarize(old)
        return [{"role": "system", "text": f"[Contexto comprimido]\n{summary}"}] + recent

    def compress(self, conversation: list[dict], max_tokens: int,
                 model: str = "qwen2.5-coder:1.5b") -> str:
        flat = self._flatten(conversation)
        if self.estimate_tokens(flat) <= max_tokens:
            return flat
        summary = self.summarize_with_ollama(conversation, max_tokens, model)
        if summary:
            return summary
        return self.fallback_summarize(conversation)

    def summarize_with_ollama(self, messages: list[dict],
                              max_tokens: int, model: str) -> str | None:
        if not self._is_ollama_available():
            return None
        prompt = (
            "Resume la conversacion siguiente en menos de "
            f"{max_tokens} tokens. Conserva solo informacion clave: "
            "preguntas, decisiones, hechos y estado actual.\n\n"
            + "\n".join(f"{m.get('role', 'user')}: {m.get('text', '')}" for m in messages)
        )
        payload = json.dumps({
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": max_tokens},
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{self.ollama_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("response", "").strip()
        except (urllib.error.URLError, urllib.error.HTTPError,
                json.JSONDecodeError, TimeoutError, OSError):
            self._ollama_available = False
            return None

    def fallback_summarize(self, messages: list[dict]) -> str:
        total = len(messages)
        if total <= 2:
            return "\n".join(f"{m.get('role', 'user')}: {m.get('text', '')}" for m in messages)
        tail = messages[-2:]
        kept = "\n".join(f"{m.get('role', 'user')}: {m.get('text', '')}" for m in tail)
        older = total - len(tail)
        return f"... [{older} mensaje(s) anteriores resumidos]\n{kept}"

    def _flatten(self, conversation: list[dict]) -> str:
        return "\n".join(f"{m.get('role', 'user')}: {m.get('text', '')}" for m in conversation)

    def _is_ollama_available(self) -> bool:
        now = time.monotonic()
        if self._ollama_available is not None and (now - self._ollama_check_time) < 30:
            return self._ollama_available
        try:
            with urllib.request.urlopen(f"{self.ollama_url}/api/tags", timeout=3) as resp:
                self._ollama_available = resp.status == 200
        except (urllib.error.URLError, urllib.error.HTTPError,
                TimeoutError, OSError):
            self._ollama_available = False
        self._ollama_check_time = now
        return self._ollama_available


__all__ = ["ContextCompressor"]
