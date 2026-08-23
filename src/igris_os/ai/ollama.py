import collections
import hashlib
import json
import os
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
    reasoning: str = ""
    backend: str = ""


# Module-level cached backend detection (probes once, shared by all instances).
# Puede haber varios backends alcanzables a la vez: el cliente agrega los
# modelos de todos ellos y despacha cada llamada al backend propietario.
_backend_probed = False
_detected_backends: list[tuple[str, str]] = [("ollama", "http://127.0.0.1:11434")]
_detected_backend: str = "ollama"  # backend primario (retrocompat)
_detected_endpoint: str = "http://127.0.0.1:11434"
_detection_lock = threading.Lock()

_DEFAULT_OPENAI_PORT = 30000

# Candidatos locales fijos; el servidor OpenAI-compatible se anade en
# ``_probe_backends()`` desde la configuracion (IGRIS_OPENAI_PORT/ENDPOINT).
_BACKEND_CANDIDATES: tuple[tuple[str, str, str], ...] = (
    ("ollama", "http://127.0.0.1:11434", "/api/tags"),
    ("lmstudio", "http://127.0.0.1:1234", "/v1/models"),
)


def _openai_endpoint_from_env() -> str:
    """Endpoint OpenAI-compatible configurable (por defecto puerto 30000).

    ``IGRIS_OPENAI_ENDPOINT`` gana si esta definido; si no, se usa
    ``IGRIS_OPENAI_PORT``. Solo se aceptan URLs de loopback (seguridad):
    cualquier otro valor cae al puerto por defecto.
    """
    explicit = os.environ.get("IGRIS_OPENAI_ENDPOINT", "").strip()
    if explicit:
        if explicit.startswith(("http://127.0.0.1", "http://localhost")):
            return explicit.rstrip("/")
        return f"http://127.0.0.1:{_DEFAULT_OPENAI_PORT}"
    raw_port = os.environ.get("IGRIS_OPENAI_PORT", "").strip()
    if raw_port:
        try:
            port = int(raw_port)
        except ValueError:
            port = _DEFAULT_OPENAI_PORT
    else:
        port = _DEFAULT_OPENAI_PORT
    return f"http://127.0.0.1:{port}"


def _probe_backends() -> list[tuple[str, str]]:
    """Detecta todos los backends alcanzables en orden de preferencia.

    Ollama (11434) y LM Studio (1234) locales primero; despues el servidor
    OpenAI-compatible configurable. Si ninguno responde, se mantiene el
    fallback local de Ollama.
    """
    opener = urllib.request.build_opener(
        urllib.request.HTTPHandler(), urllib.request.HTTPSHandler())
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    candidates: list[tuple[str, str, str]] = list(_BACKEND_CANDIDATES) + [
        ("openai", _openai_endpoint_from_env(), "/v1/models")]
    for name, endpoint, path in candidates:
        if endpoint in seen:
            continue
        try:
            req = urllib.request.Request(endpoint + path)
            with opener.open(req, timeout=1) as resp:
                if resp.status == 200:
                    found.append((name, endpoint))
                    seen.add(endpoint)
        except (OSError, ValueError, urllib.error.URLError):
            continue
    return found or [("ollama", "http://127.0.0.1:11434")]


def reset_backend_detection() -> None:
    """Solo para tests: fuerza la re-deteccion en la siguiente instancia."""
    global _backend_probed, _detected_backends, _detected_backend, _detected_endpoint
    with _detection_lock:
        _backend_probed = False
        _detected_backends = [("ollama", "http://127.0.0.1:11434")]
        _detected_backend = "ollama"
        _detected_endpoint = "http://127.0.0.1:11434"


class _ResponseCache:
    """Bounded LRU cache keyed by (prompt_hash, model, temperature, thinking)."""

    def __init__(self, max_size: int = 256) -> None:
        self._max_size = max_size
        self._cache: dict[tuple[str, str, float, bool], str] = {}
        self._order: collections.OrderedDict = collections.OrderedDict()
        self._lock = threading.Lock()

    def get(self, prompt_hash: str, model: str, temperature: float, thinking: bool = False) -> str | None:
        key = (prompt_hash, model, temperature, thinking)
        with self._lock:
            if key in self._cache:
                self._order.move_to_end(key)
                return self._cache[key]
        return None

    def put(self, prompt_hash: str, model: str, temperature: float, thinking: bool, value: str) -> None:
        key = (prompt_hash, model, temperature, thinking)
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
        self._model_index: dict[str, tuple[str, str]] = {}
        self._backends: list[tuple[str, str]] = [("ollama", endpoint.rstrip("/"))]
        if endpoint == "http://127.0.0.1:11434":
            self._detect_backends()
        self.endpoint = self._backends[0][1]
        self._backend = self._backends[0][0]

    @staticmethod
    def _build_opener() -> urllib.request.OpenerDirector:
        opener = urllib.request.build_opener(
            urllib.request.HTTPHandler(),
            urllib.request.HTTPSHandler(),
        )
        return opener

    def _detect_backends(self) -> None:
        global _backend_probed, _detected_backends, _detected_backend, _detected_endpoint
        with _detection_lock:
            if not _backend_probed:
                _detected_backends = _probe_backends()
                _detected_backend, _detected_endpoint = _detected_backends[0]
                _backend_probed = True
        self._backends = list(_detected_backends)
        self.endpoint = self._backends[0][1]
        self._backend = self._backends[0][0]

    def _backend_for(self, model: str) -> tuple[str, str]:
        """(backend, endpoint) propietario de un modelo; si no se conoce,
        el backend primario (fallback local)."""
        found = self._model_index.get(model)
        if found is not None:
            return found
        return self._backends[0]

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
        """Agrega los modelos de todos los backends alcanzables.

        Construye el indice modelo -> (backend, endpoint) que usa
        ``_backend_for()`` para despachar cada llamada. Si un backend deja de
        responder, se omite (fallback local intacto).
        """
        result: list[str] = []
        index: dict[str, tuple[str, str]] = {}
        for name, endpoint in self._backends:
            try:
                if name == "ollama":
                    with self._opener.open(endpoint + "/api/tags",
                                           timeout=3) as response:
                        data = json.load(response)
                    names = [item["name"] for item in data.get("models", [])
                             if isinstance(item, dict) and item.get("name")]
                else:
                    with self._opener.open(endpoint + "/v1/models",
                                           timeout=3) as response:
                        data = json.load(response)
                    names = [item["id"] for item in data.get("data", [])
                             if isinstance(item, dict) and item.get("id")]
            except (OSError, ValueError, urllib.error.URLError):
                continue
            for model in names:
                if model not in index:
                    index[model] = (name, endpoint)
                    result.append(model)
        self._model_index = index
        return tuple(result)

    def backends(self) -> list[tuple[str, str]]:
        """Backends alcanzables (nombre, endpoint), en orden de preferencia."""
        return [(name, endpoint) for name, endpoint in self._backends]

    def generate_stream(self, prompt: str, model: str,
                        temperature: float = 0.0) -> collections.abc.Iterator[str]:
        """Yield text chunks as they arrive from the LLM API."""
        if not prompt.strip() or not model.strip():
            return

        backend, endpoint = self._backend_for(model)
        if backend == "ollama":
            yield from self._stream_ollama(prompt, model, temperature,
                                           endpoint=endpoint)
        else:
            yield from self._stream_openai(prompt, model, temperature,
                                           endpoint=endpoint)

    def _stream_openai(self, prompt: str, model: str,
                       temperature: float,
                       endpoint: str | None = None) -> collections.abc.Iterator[str]:
        target = endpoint or self.endpoint
        body = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            "temperature": temperature,
        }).encode()
        request = urllib.request.Request(
            target + "/v1/chat/completions", data=body,
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
                       temperature: float,
                       endpoint: str | None = None) -> collections.abc.Iterator[str]:
        target = endpoint or self.endpoint
        body = json.dumps({
            "model": model,
            "prompt": prompt,
            "stream": True,
            "options": {"temperature": temperature}
        }).encode()
        request = urllib.request.Request(
            target + "/api/generate", data=body,
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

    def generate(self, prompt: str, model: str, *, thinking: bool = False) -> ModelReply:
        if not prompt.strip() or not model.strip():
            return ModelReply(False, "", model, "Solicitud incompleta")

        backend, endpoint = self._backend_for(model)
        prompt_hash = self._hash_prompt(prompt)
        cached = self._cache.get(prompt_hash, model, 0.0, thinking)
        if cached is not None:
            return ModelReply(True, cached, model, backend=backend)

        if backend == "ollama":
            return self._generate_ollama(prompt, model, prompt_hash, thinking,
                                         endpoint=endpoint, backend=backend)
        return self._generate_openai(prompt, model, prompt_hash, thinking,
                                     endpoint=endpoint, backend=backend)

    def _generate_openai(self, prompt: str, model: str,
                         prompt_hash: str,
                         thinking: bool = False,
                         endpoint: str | None = None,
                         backend: str = "openai") -> ModelReply:
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "temperature": 0.0,
        }
        if thinking:
            body["chat_template_kwargs"] = {"thinking": True}
        data = self._post_json("/v1/chat/completions", body, endpoint=endpoint)
        if data is None:
            return ModelReply(False, "", model, "Servidor OpenAI-compatible no responde")
        try:
            message = data["choices"][0]["message"]
            text = (message.get("content") or "").strip()
            reasoning = (message.get("reasoning_content") or "").strip()
        except (KeyError, IndexError, TypeError):
            return ModelReply(False, "", model, "Respuesta malformada")
        if text:
            self._cache.put(prompt_hash, model, 0.0, thinking, text)
        return ModelReply(bool(text), text, model,
                          "" if text else "Respuesta vacia", reasoning,
                          backend)

    def _generate_ollama(self, prompt: str, model: str,
                         prompt_hash: str,
                         thinking: bool = False,
                         endpoint: str | None = None,
                         backend: str = "ollama") -> ModelReply:
        target = endpoint or self.endpoint
        options = {}
        if "Eres IGRIS en una conversacion real" in prompt:
            options = {
                "temperature": 0.65,
                "top_p": 0.9,
                "repeat_penalty": 1.15,
                "num_predict": 256,
            }
        body = json.dumps({"model": model, "prompt": prompt, "stream": False,
                           "options": options}).encode()
        request = urllib.request.Request(
            target + "/api/generate", data=body,
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                data = json.load(response)
            text = str(data.get("response", "")).strip()
            if text:
                self._cache.put(prompt_hash, model, 0.0, thinking, text)
            return ModelReply(bool(text), text, model,
                              "" if text else "Respuesta vacia",
                              "", backend)
        except (OSError, ValueError, urllib.error.URLError) as exc:
            return ModelReply(False, "", model, str(exc), backend=backend)

    def _post_json(self, path: str, body: dict,
                   endpoint: str | None = None) -> dict | None:
        target = endpoint or self.endpoint
        data = json.dumps(body).encode()
        request = urllib.request.Request(
            target + path, data=data,
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
        backend, endpoint = self._backend_for(model)
        if backend == "ollama":
            return self._embed_ollama(texts, model, endpoint=endpoint)
        return self._embed_openai(texts, model, endpoint=endpoint)

    def _embed_openai(self, texts: list[str], model: str,
                      endpoint: str | None = None) -> tuple[bool, list[list[float]]]:
        body = {"model": model, "input": texts}
        data = self._post_json("/v1/embeddings", body, endpoint=endpoint)
        if data is None:
            return False, []
        try:
            vectors = [item["embedding"] for item in data["data"]]
            return True, vectors
        except (KeyError, IndexError, TypeError):
            return False, []

    def _embed_ollama(self, texts: list[str], model: str,
                      endpoint: str | None = None) -> tuple[bool, list[list[float]]]:
        target = endpoint or self.endpoint
        body = json.dumps({"model": model, "input": texts}).encode()
        request = urllib.request.Request(
            target + "/api/embed", data=body,
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
