import collections
import hashlib
import json
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelReply:
    ok: bool
    text: str
    model: str
    error: str = ""


# Module-level cached backend detection (probes once, shared by all instances)
_backend_probed = False
_detected_backend: str = "ollama"
_detection_lock = threading.Lock()
_detected_endpoint: str = "http://127.0.0.1:11434"


class _ResponseCache:
    """Bounded LRU cache keyed by (prompt_hash, model, temperature)."""

    def __init__(self, max_size: int = 256) -> None:
        self._max_size = max_size
        self._cache: dict[tuple[str, str, float], str] = {}
        self._order: collections.OrderedDict = collections.OrderedDict()
        self._lock = threading.Lock()

    def get(self, prompt_hash: str, model: str, temperature: float) -> str | None:
        key = (prompt_hash, model, temperature)
        with self._lock:
            if key in self._cache:
                self._order.move_to_end(key)
                return self._cache[key]
        return None

    def put(self, prompt_hash: str, model: str, temperature: float, value: str) -> None:
        key = (prompt_hash, model, temperature)
        with self._lock:
            if key in self._cache:
                self._order.move_to_end(key)
            else:
                if len(self._cache) >= self._max_size:
                    evict_key, _ = self._order.popitem(last=False)
                    del self._cache[evict_key]
                self._order[key] = True
            self._cache[key] = value

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._order.clear()


class OllamaClient:
    def __init__(self, endpoint: str = "http://127.0.0.1:11434",
                 timeout: float = 120) -> None:
        if not endpoint.startswith(("http://127.0.0.1", "http://localhost")):
            raise ValueError("Ollama debe usar loopback")
        self.timeout = timeout
        self._cache = _ResponseCache(max_size=256)
        self._opener = self._build_opener()
        self.endpoint = endpoint.rstrip("/")
        self._backend = "ollama"
        if endpoint == "http://127.0.0.1:11434":
            self._detect_backend()

    @staticmethod
    def _build_opener() -> urllib.request.OpenerDirector:
        opener = urllib.request.build_opener(
            urllib.request.HTTPHandler(),
            urllib.request.HTTPSHandler(),
        )
        return opener

    def _detect_backend(self) -> None:
        global _backend_probed, _detected_backend, _detected_endpoint
        with _detection_lock:
            if _backend_probed:
                pass
            else:
                opener = self._build_opener()
                try:
                    req = urllib.request.Request("http://127.0.0.1:11434/api/tags")
                    with opener.open(req, timeout=1) as resp:
                        if resp.status == 200:
                            _detected_backend = "ollama"
                            _detected_endpoint = "http://127.0.0.1:11434"
                            _backend_probed = True
                except (OSError, urllib.error.URLError):
                    pass
                if not _backend_probed:
                    try:
                        req = urllib.request.Request("http://127.0.0.1:1234/v1/models")
                        with opener.open(req, timeout=1) as resp:
                            if resp.status == 200:
                                _detected_backend = "lmstudio"
                                _detected_endpoint = "http://127.0.0.1:1234"
                                _backend_probed = True
                    except (OSError, urllib.error.URLError):
                        pass
                if not _backend_probed:
                    _detected_backend = "ollama"
                    _detected_endpoint = "http://127.0.0.1:11434"
                    _backend_probed = True
        self.endpoint = _detected_endpoint
        self._backend = _detected_backend

    @staticmethod
    def _hash_prompt(prompt: str) -> str:
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough token estimation: ~4 chars/token English, ~2 chars/token Spanish."""
        if not text:
            return 0
        spanish_hints = set("áéíóúüñ¿¡")
        if any(c in spanish_hints for c in text.lower()):
            chars_per_token = 2.0
        else:
            chars_per_token = 4.0
        return max(1, int(len(text) / chars_per_token))

    @staticmethod
    def _is_complete_json(buffer: str) -> bool:
        """Heuristic: detect if buffer contains a complete JSON value."""
        stripped = buffer.strip()
        if not stripped or stripped[-1] not in ("}", "]"):
            return False
        try:
            json.loads(stripped)
            return True
        except (json.JSONDecodeError, ValueError):
            return False

    def _urlopen_with_timeouts(self, request: urllib.request.Request,
                                timeout: float) -> urllib.response.addinfo:
        """Open URL using persistent opener. Timeout applies to both connect and read."""
        return self._opener.open(request, timeout=timeout)

    def models(self) -> tuple[str, ...]:
        try:
            if self._backend == "lmstudio":
                with self._opener.open(self.endpoint + "/v1/models",
                                       timeout=3) as response:
                    data = json.load(response)
                return tuple(item["id"] for item in data.get("data", [])
                             if isinstance(item, dict) and item.get("id"))
            else:
                with self._opener.open(self.endpoint + "/api/tags",
                                       timeout=3) as response:
                    data = json.load(response)
                return tuple(item["name"] for item in data.get("models", [])
                             if isinstance(item, dict) and item.get("name"))
        except (OSError, ValueError, urllib.error.URLError):
            return ()

    def generate_stream(self, prompt: str, model: str,
                        temperature: float = 0.0) -> collections.abc.Iterator[str]:
        """Yield text chunks as they arrive from the LLM API."""
        if not prompt.strip() or not model.strip():
            return

        if self._backend == "lmstudio":
            yield from self._stream_openai(prompt, model, temperature)
        else:
            yield from self._stream_ollama(prompt, model, temperature)

    def _stream_openai(self, prompt: str, model: str,
                       temperature: float) -> collections.abc.Iterator[str]:
        body = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            "temperature": temperature,
        }).encode()
        request = urllib.request.Request(
            self.endpoint + "/v1/chat/completions", data=body,
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

    def _stream_ollama(self, prompt: str, model: str,
                       temperature: float) -> collections.abc.Iterator[str]:
        body = json.dumps({
            "model": model,
            "prompt": prompt,
            "stream": True,
            "options": {"temperature": temperature}
        }).encode()
        request = urllib.request.Request(
            self.endpoint + "/api/generate", data=body,
            headers={"Content-Type": "application/json"}, method="POST")
        buffer = ""
        is_json_mode = prompt.strip().lower().startswith(
            ("json", "```json", "{")
        )
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                for line in response:
                    line = line.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    try:
                        chunk_data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    chunk_text = chunk_data.get("response", "")
                    if chunk_text:
                        buffer += chunk_text
                        yield chunk_text
                    if chunk_data.get("done", False):
                        break
                    if is_json_mode and self._is_complete_json(buffer):
                        break
        except (OSError, ValueError, urllib.error.URLError):
            return

    def generate(self, prompt: str, model: str) -> ModelReply:
        if not prompt.strip() or not model.strip():
            return ModelReply(False, "", model, "Solicitud incompleta")

        prompt_hash = self._hash_prompt(prompt)
        cached = self._cache.get(prompt_hash, model, 0.0)
        if cached is not None:
            return ModelReply(True, cached, model)

        if self._backend == "lmstudio":
            return self._generate_openai(prompt, model, prompt_hash)
        return self._generate_ollama(prompt, model, prompt_hash)

    def _generate_openai(self, prompt: str, model: str,
                         prompt_hash: str) -> ModelReply:
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

    def _generate_ollama(self, prompt: str, model: str,
                         prompt_hash: str) -> ModelReply:
        body = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
        request = urllib.request.Request(
            self.endpoint + "/api/generate", data=body,
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                data = json.load(response)
            text = str(data.get("response", "")).strip()
            if text:
                self._cache.put(prompt_hash, model, 0.0, text)
            return ModelReply(bool(text), text, model,
                              "" if text else "Respuesta vacia")
        except (OSError, ValueError, urllib.error.URLError) as exc:
            return ModelReply(False, "", model, str(exc))

    def _post_json(self, path: str, body: dict) -> dict | None:
        data = json.dumps(body).encode()
        request = urllib.request.Request(
            self.endpoint + path, data=data,
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with self._opener.open(
                    request, timeout=self.timeout) as response:
                return json.load(response)
        except (OSError, ValueError, urllib.error.URLError):
            return None

    def embed(self, texts: list[str], model: str) -> tuple[bool, list[list[float]]]:
        """Vectoriza textos con un modelo de embeddings local (loopback)."""
        if not texts or not model.strip():
            return False, []
        if self._backend == "lmstudio":
            return self._embed_openai(texts, model)
        return self._embed_ollama(texts, model)

    def _embed_openai(self, texts: list[str], model: str) -> tuple[bool, list[list[float]]]:
        body = {"model": model, "input": texts}
        data = self._post_json("/v1/embeddings", body)
        if data is None:
            return False, []
        try:
            vectors = [item["embedding"] for item in data["data"]]
            return True, vectors
        except (KeyError, IndexError, TypeError):
            return False, []

    def _embed_ollama(self, texts: list[str], model: str) -> tuple[bool, list[list[float]]]:
        body = json.dumps({"model": model, "input": texts}).encode()
        request = urllib.request.Request(
            self.endpoint + "/api/embed", data=body,
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                data = json.load(response)
            vectors = data.get("embeddings")
            if not isinstance(vectors, list) or not all(
                    isinstance(item, list) for item in vectors):
                return False, []
            return True, [[float(value) for value in item] for item in vectors]
        except (OSError, ValueError, urllib.error.URLError, TypeError):
            return False, []
    def select_embedding_model(self) -> str | None:
        available = set(self.models())
        if not available:
            return None
        preferred = ("nomic-embed-text", "mxbai-embed-large",
                     "all-minilm", "bge-m3", "granite-embedding:278m")
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
