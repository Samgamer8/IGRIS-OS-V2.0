import collections
import hashlib
import json
import threading
import urllib.error
import urllib.request

from .ollama import ModelReply, _ResponseCache


class LMStudioClient:
    """Client for LM Studio's OpenAI-compatible API (localhost:1234).

    Same interface as OllamaClient so it can be used as a drop-in replacement.
    """

    def __init__(self, endpoint: str = "http://127.0.0.1:1234",
                 timeout: float = 120) -> None:
        if not endpoint.startswith(("http://127.0.0.1", "http://localhost")):
            raise ValueError("LM Studio debe usar loopback")
        self.endpoint = endpoint.rstrip("/")
        self.timeout = timeout
        self._cache = _ResponseCache(max_size=256)
        self._opener = self._build_opener()

    @staticmethod
    def _build_opener() -> urllib.request.OpenerDirector:
        return urllib.request.build_opener(
            urllib.request.HTTPHandler(),
            urllib.request.HTTPSHandler(),
        )

    @staticmethod
    def _hash_prompt(prompt: str) -> str:
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    def _post_json(self, path: str, body: dict,
                   timeout: float | None = None) -> dict | None:
        data = json.dumps(body).encode()
        request = urllib.request.Request(
            self.endpoint + path, data=data,
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with self._opener.open(
                    request, timeout=timeout or self.timeout) as response:
                return json.load(response)
        except (OSError, ValueError, urllib.error.URLError):
            return None

    def _get_json(self, path: str, timeout: float = 3) -> dict | None:
        request = urllib.request.Request(self.endpoint + path)
        try:
            with self._opener.open(request, timeout=timeout) as response:
                return json.load(response)
        except (OSError, ValueError, urllib.error.URLError):
            return None

    def models(self) -> tuple[str, ...]:
        data = self._get_json("/v1/models")
        if not data:
            return ()
        return tuple(
            item["id"] for item in data.get("data", [])
            if isinstance(item, dict) and item.get("id"))

    def generate(self, prompt: str, model: str) -> ModelReply:
        if not prompt.strip() or not model.strip():
            return ModelReply(False, "", model, "Solicitud incompleta")

        prompt_hash = self._hash_prompt(prompt)
        cached = self._cache.get(prompt_hash, model, 0.0)
        if cached is not None:
            return ModelReply(True, cached, model)

        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "temperature": 0.0,
        }
        data = self._post_json("/v1/chat/completions", body)
        if data is None:
            return ModelReply(False, "", model, "LM Studio no responde")
        try:
            text = data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError):
            return ModelReply(False, "", model, "Respuesta malformada")
        if text:
            self._cache.put(prompt_hash, model, 0.0, text)
        return ModelReply(bool(text), text, model,
                          "" if text else "Respuesta vacia")

    def generate_stream(self, prompt: str, model: str,
                        temperature: float = 0.0) -> collections.abc.Iterator[str]:
        if not prompt.strip() or not model.strip():
            return

        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            "temperature": temperature,
        }
        data = json.dumps(body).encode()
        request = urllib.request.Request(
            self.endpoint + "/v1/chat/completions", data=data,
            headers={"Content-Type": "application/json"}, method="POST")

        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                for line in response:
                    line = line.decode("utf-8", errors="replace").strip()
                    if not line or not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    if payload == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload)
                        delta = chunk["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError,
                            TypeError):
                        continue
        except (OSError, ValueError, urllib.error.URLError):
            return

    def embed(self, texts: list[str], model: str) -> tuple[bool, list[list[float]]]:
        if not texts or not model.strip():
            return False, []
        body = {"model": model, "input": texts}
        data = self._post_json("/v1/embeddings", body)
        if data is None:
            return False, []
        try:
            vectors = [item["embedding"] for item in data["data"]]
            return True, vectors
        except (KeyError, IndexError, TypeError):
            return False, []

    def select_embedding_model(self) -> str | None:
        available = set(self.models())
        if not available:
            return None
        preferred = ("nomic-embed-text", "mxbai-embed-large",
                     "all-minilm", "bge-m3")
        candidates = [name for name in preferred if name in available]
        candidates += [name for name in sorted(available)
                       if any(hint in name for hint in
                              ("embed", "minilm", "bge", "mxbai"))]
        seen: set[str] = set()
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            ok, _ = self.embed([".", "test"], candidate)
            if ok:
                return candidate
        return None
