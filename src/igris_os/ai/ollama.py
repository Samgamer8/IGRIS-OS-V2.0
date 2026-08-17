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
        self.endpoint = endpoint.rstrip("/")
        self.timeout = timeout
        self._cache = _ResponseCache(max_size=256)
        self._opener = self._build_opener()

    @staticmethod
    def _build_opener() -> urllib.request.OpenerDirector:
        opener = urllib.request.build_opener(
            urllib.request.HTTPHandler(),
            urllib.request.HTTPSHandler(),
        )
        return opener

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
        if not stripped:
            return False
        for end_ch, start_ch in (("}", "{"), ("]", "[")):
            if stripped.endswith(end_ch):
                depth = 0
                for ch in stripped:
                    if ch == start_ch:
                        depth += 1
                    elif ch == end_ch:
                        depth -= 1
                        if depth == 0:
                            return True
                return False
        return False

    def _urlopen_with_timeouts(self, request: urllib.request.Request,
                                timeout: float) -> urllib.response.addinfo:
        """Open URL using persistent opener. Timeout applies to both connect and read."""
        return self._opener.open(request, timeout=timeout)

    def models(self) -> tuple[str, ...]:
        try:
            with self._opener.open(self.endpoint + "/api/tags", timeout=3) as response:
                data = json.load(response)
            return tuple(item["name"] for item in data.get("models", [])
                         if isinstance(item, dict) and item.get("name"))
        except (OSError, ValueError, urllib.error.URLError):
            return ()

    def generate_stream(self, prompt: str, model: str,
                        temperature: float = 0.0) -> collections.abc.Iterator[str]:
        """Yield text chunks as they arrive from Ollama's streaming API."""
        if not prompt.strip() or not model.strip():
            return

        body = json.dumps({
            "model": model,
            "prompt": prompt,
            "stream": True,
            "options": {"temperature": temperature}
        }).encode()

        request = urllib.request.Request(
            self.endpoint + "/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

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

    def embed(self, texts: list[str], model: str) -> tuple[bool, list[list[float]]]:
        """Vectoriza textos con un modelo de embeddings local (loopback)."""
        if not texts or not model.strip():
            return False, []
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
