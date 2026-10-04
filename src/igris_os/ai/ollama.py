import collections
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ModelReply:
    ok: bool
    text: str
    model: str
    error: str = ""
    reasoning: str = ""
    backend: str = ""
    metadata: dict = field(default_factory=dict)


# Module-level cached backend detection (probes once, shared by all instances).
# Puede haber varios backends alcanzables a la vez: el cliente agrega los
# modelos de todos ellos y despacha cada llamada al backend propietario.
_backend_probed = False
_detected_backends: list[tuple[str, str]] = [("ollama", "http://127.0.0.1:11434")]
_detected_backend: str = "ollama"  # backend primario (retrocompat)
_detected_endpoint: str = "http://127.0.0.1:11434"
_detection_lock = threading.Lock()
_detection_time = 0.0
_DEFAULT_BACKENDS: tuple[tuple[str, str], ...] = (
    ("ollama", "http://127.0.0.1:11434"),
)

_DEFAULT_OPENAI_PORT = 30000
_CONVERSATION_OUTPUT_LIMIT = 1024
_MAX_OUTPUT_LIMIT = 8192

# Candidatos locales fijos; el servidor OpenAI-compatible se anade en
# ``_probe_backends()`` desde la configuracion (IGRIS_OPENAI_PORT/ENDPOINT).
_BACKEND_CANDIDATES: tuple[tuple[str, str, str], ...] = (
    ("ollama", "http://127.0.0.1:11434", "/api/tags"),
    ("lmstudio", "http://127.0.0.1:1234", "/v1/models"),
)


def _is_loopback_endpoint(endpoint: str) -> bool:
    try:
        url = urlsplit(endpoint)
        return (url.scheme == "http" and url.hostname in {"127.0.0.1", "localhost", "::1"}
                and url.username is None and url.password is None
                and not url.query and not url.fragment and url.path in {"", "/"}
                and (url.port is None or 1 <= url.port <= 65535))
    except ValueError:
        return False


def _openai_endpoint_from_env() -> str:
    """Endpoint OpenAI-compatible configurable (por defecto puerto 30000).

    ``IGRIS_OPENAI_ENDPOINT`` gana si esta definido; si no, se usa
    ``IGRIS_OPENAI_PORT``. Solo se aceptan URLs de loopback (seguridad):
    cualquier otro valor cae al puerto por defecto.
    """
    explicit = os.environ.get("IGRIS_OPENAI_ENDPOINT", "").strip()
    if explicit:
        # Accept the customary /v1 base URL without sending /v1/v1/models.
        explicit = explicit.rstrip("/").removesuffix("/v1")
        if _is_loopback_endpoint(explicit):
            return explicit.rstrip("/")
        return f"http://127.0.0.1:{_DEFAULT_OPENAI_PORT}"
    raw_port = os.environ.get("IGRIS_OPENAI_PORT", "").strip()
    if raw_port:
        try:
            port = int(raw_port)
            if not 1 <= port <= 65535:
                raise ValueError("Puerto invalido")
        except ValueError:
            port = _DEFAULT_OPENAI_PORT
    else:
        port = _DEFAULT_OPENAI_PORT
    return f"http://127.0.0.1:{port}"


def _probe_backends() -> list[tuple[str, str]]:
    """Detecta todos los backends alcanzables en orden de preferencia.

    La ausencia de servidor nunca cuenta como un backend disponible.
    """
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    candidates: list[tuple[str, str, str]] = list(_BACKEND_CANDIDATES) + [
        ("openai", _openai_endpoint_from_env(), "/v1/models")]
    preferred = os.environ.get('IGRIS_PREFERRED_BACKEND', '').strip().lower()
    exclusive = os.environ.get('IGRIS_EXCLUSIVE_BACKEND', '').strip().lower() in {'1', 'true', 'yes'}
    if exclusive and preferred in {'ollama', 'lmstudio', 'openai'}:
        candidates = [candidate for candidate in candidates if candidate[0] == preferred]

    def probe(candidate):
        name, endpoint, path = candidate
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            urllib.request.HTTPHandler(), urllib.request.HTTPSHandler())
        try:
            req = urllib.request.Request(endpoint + path)
            with opener.open(req, timeout=1) as resp:
                if resp.status == 200:
                    return name, endpoint
        except (OSError, ValueError, urllib.error.URLError):
            pass
        return None

    with ThreadPoolExecutor(max_workers=len(candidates)) as executor:
        for result in executor.map(probe, candidates):
            if result is not None and result[1] not in seen:
                found.append(result)
                seen.add(result[1])
    if preferred in {'ollama', 'lmstudio', 'openai'}:
        found.sort(key=lambda backend: backend[0] != preferred)
    return found


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
        if not _is_loopback_endpoint(endpoint):
            raise ValueError("Ollama debe usar loopback")
        self.timeout = timeout
        self._cache = _ResponseCache(max_size=256)
        self._opener = self._build_opener()
        self._model_index: dict[str, tuple[str, str]] = {}
        self._reachable_backends: list[tuple[str, str]] = []
        self._auto_detect = endpoint.rstrip("/") == "http://127.0.0.1:11434"
        self._backends: list[tuple[str, str]] = [("ollama", endpoint.rstrip("/"))]
        if endpoint == "http://127.0.0.1:11434":
            self._detect_backends()
        self.endpoint = self._backends[0][1]
        self._backend = self._backends[0][0]

    @staticmethod
    def _build_opener() -> urllib.request.OpenerDirector:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            urllib.request.HTTPHandler(),
            urllib.request.HTTPSHandler(),
        )
        return opener

    def _detect_backends(self) -> None:
        global _backend_probed, _detected_backends, _detected_backend, _detected_endpoint
        global _detection_time
        with _detection_lock:
            if not _backend_probed or time.monotonic() - _detection_time >= 5:
                _detected_backends = _probe_backends()
                if _detected_backends:
                    _detected_backend, _detected_endpoint = _detected_backends[0]
                else:
                    _detected_backend, _detected_endpoint = _DEFAULT_BACKENDS[0]
                _backend_probed = True
                _detection_time = time.monotonic()
        if _detected_backends:
            self._backends = list(_detected_backends)
        else:
            self._backends = list(_DEFAULT_BACKENDS)
        self.endpoint = self._backends[0][1]
        self._backend = self._backends[0][0]

    def _backend_for(self, model: str) -> tuple[str, str]:
        """(backend, endpoint) propietario de un modelo; si no se conoce,
        el backend primario (fallback local)."""
        found = self._model_index.get(model)
        if found is None:
            self.models()
            found = self._model_index.get(model)
        if found is not None:
            return found
        return self._backends[0] if self._backends else ("ollama", self.endpoint)

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
        """Devuelve exclusivamente modelos anunciados por servidores locales."""
        if self._auto_detect:
            self._detect_backends()
        result: list[str] = []
        index: dict[str, tuple[str, str]] = {}
        reachable: list[tuple[str, str]] = []
        for name, endpoint in self._backends:
            try:
                if name == "ollama":
                    with self._opener.open(endpoint + "/api/tags",
                                           timeout=3) as response:
                        data = json.load(response)
                    if not isinstance(data, dict) or not isinstance(data.get("models"), list):
                        continue
                    names = [item["name"] for item in data.get("models", [])
                             if isinstance(item, dict) and item.get("name")]
                else:
                    with self._opener.open(endpoint + "/v1/models",
                                           timeout=3) as response:
                        data = json.load(response)
                    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
                        continue
                    names = [item["id"] for item in data.get("data", [])
                             if isinstance(item, dict) and item.get("id")]
            except (OSError, ValueError, urllib.error.URLError):
                continue
            reachable.append((name, endpoint))
            for model in names:
                if isinstance(model, str) and model not in index:
                    index[model] = (name, endpoint)
                    result.append(model)
        self._model_index = index
        self._reachable_backends = reachable
        if not reachable:
            self._cache.clear()
        return tuple(result)

    def backends(self) -> list[tuple[str, str]]:
        """Backends alcanzables (nombre, endpoint), en orden de preferencia."""
        self.models()
        return list(self._reachable_backends)

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
        return self.generate_strict(prompt, model, thinking=thinking)

    def generate_strict(
            self, prompt: str, model: str, *,
            thinking: bool = False) -> ModelReply:
        """Generate without disguising backend failure as offline prose."""
        if not prompt.strip() or not model.strip():
            return ModelReply(False, "", model, "Solicitud incompleta")
        backend, endpoint = self._backend_for(model)
        prompt_hash = self._hash_prompt(prompt)
        cached = self._cache.get(prompt_hash, model, 0.0, thinking)
        if cached is not None:
            return ModelReply(True, cached, model, backend=backend)
        if backend == "ollama":
            reply = self._generate_ollama(
                prompt, model, prompt_hash, thinking,
                endpoint=endpoint, backend=backend)
            # Conversation is the only free-form path with a deliberately
            # compact budget. If Ollama consumes it, repeat the complete
            # request once with more room instead of exposing partial text as
            # a failed delivery. Structured/code calls manage their own
            # bounded retry budget at a higher layer.
            if ("Eres IGRIS en una conversacion real" in prompt
                    and not reply.ok
                    and reply.metadata.get("done_reason") == "length"):
                initial_limit = int(reply.metadata.get(
                    "requested_output_limit") or _CONVERSATION_OUTPUT_LIMIT)
                retry_limit = min(
                    _MAX_OUTPUT_LIMIT, max(_CONVERSATION_OUTPUT_LIMIT * 2,
                                           initial_limit * 2))
                if retry_limit > initial_limit:
                    retried = self._generate_ollama(
                        prompt, model, prompt_hash, thinking,
                        endpoint=endpoint, backend=backend,
                        output_limit=retry_limit)
                    metadata = dict(retried.metadata)
                    metadata.update(
                        retried_after_truncation=True,
                        initial_output_limit=initial_limit,
                    )
                    return ModelReply(
                        retried.ok, retried.text, retried.model,
                        retried.error, retried.reasoning, retried.backend,
                        metadata)
            return reply
        return self._generate_openai(
            prompt, model, prompt_hash, thinking,
            endpoint=endpoint, backend=backend)

    def generate_json(self, prompt: str, model: str, schema: dict) -> ModelReply:
        """Solicita JSON estructurado cuando el backend local lo soporta."""
        if not prompt.strip() or not model.strip() or not isinstance(schema, dict):
            return ModelReply(False, "", model, "Solicitud JSON incompleta")
        backend, endpoint = self._backend_for(model)
        marker = json.dumps(schema, sort_keys=True, separators=(",", ":"))
        prompt_hash = self._hash_prompt(prompt + "\n[JSON_SCHEMA]" + marker)
        cached = self._cache.get(prompt_hash, model, 0.0, False)
        if cached is not None:
            return ModelReply(True, cached, model, backend=backend)
        if backend != "ollama":
            reply = self._generate_openai(prompt, model, prompt_hash,
                                        endpoint=endpoint, backend=backend,
                                        response_format=schema)
        else:
            reply = self._generate_ollama(prompt, model, prompt_hash,
                                        endpoint=endpoint, backend=backend,
                                        response_format=schema, structured=True)
        # Structured generation is a production input. Never disguise an
        # unreachable model as successful JSON: callers must repair or escalate.
        return reply

    def _generate_openai(self, prompt: str, model: str,
                         prompt_hash: str,
                         thinking: bool = False,
                         endpoint: str | None = None,
                         backend: str = "openai",
                         response_format: dict | None = None) -> ModelReply:
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "temperature": 0.0,
            "max_tokens": (_CONVERSATION_OUTPUT_LIMIT if
                           'Eres IGRIS en una conversacion real' in prompt else 4096),
        }
        if response_format is not None:
            body['response_format'] = {'type': 'json_schema', 'json_schema': {
                'name': 'igris_response', 'strict': True, 'schema': response_format}}
        if thinking:
            body["chat_template_kwargs"] = {"thinking": True}
        if getattr(self, "output_token_limit", None):
            body["max_tokens"] = min(8192, max(256, int(self.output_token_limit)))
        target = endpoint or self.endpoint
        try:
            data = self._post_json("/v1/chat/completions", body,
                                   endpoint=target, raise_errors=True)
        except (OSError, ValueError, urllib.error.URLError) as exc:
            return ModelReply(False, "", model,
                              f"{backend} · {target} · modelo {model}: {self._error_detail(exc)}",
                              backend=backend)
        if data is None:
            return ModelReply(False, "", model, "Servidor OpenAI-compatible no responde", backend=backend)
        if isinstance(data, dict) and data.get("error"):
            return ModelReply(False, "", model,
                              f"{backend} · {target} · modelo {model}: {data['error']}", backend=backend)
        try:
            choice = data["choices"][0]
            if choice.get("finish_reason") == "length":
                return ModelReply(False, "", model, "Respuesta truncada por el limite de tokens", backend=backend)
            message = choice["message"]
            text = (message.get("content") or "").strip()
            reasoning = (message.get("reasoning_content") or "").strip()
        except (KeyError, IndexError, TypeError, AttributeError):
            return ModelReply(False, "", model, "Respuesta malformada", backend=backend)
        if text:
            self._cache.put(prompt_hash, model, 0.0, thinking, text)
        return ModelReply(bool(text), text, model,
                          "" if text else "Respuesta vacia", reasoning,
                          backend)

    def _generate_ollama(self, prompt: str, model: str,
                         prompt_hash: str,
                         thinking: bool = False,
                         endpoint: str | None = None,
                         backend: str = "ollama",
                         response_format: dict | None = None,
                         structured: bool = False,
                         output_limit: int | None = None) -> ModelReply:
        target = endpoint or self.endpoint
        options = {}
        if "Eres IGRIS en una conversacion real" in prompt:
            options = {
                "temperature": 0.65,
                "top_p": 0.9,
                "repeat_penalty": 1.15,
                "num_predict": _CONVERSATION_OUTPUT_LIMIT,
            }
        if structured:
            options = {
                "temperature": 0,
                "seed": 42,
                "num_predict": 4096,
            }
        configured_limit = (output_limit if output_limit is not None
                            else getattr(self, "output_token_limit", None))
        if configured_limit:
            options["num_predict"] = min(
                _MAX_OUTPUT_LIMIT, max(256, int(configured_limit)))
        if getattr(self, 'context_window', None):
            options['num_ctx'] = min(32768, max(4096, int(self.context_window)))
        body_data = {"model": model, "prompt": prompt, "stream": False,
                     "options": options}
        # Omitting think lets Ollama enable it by default. Respect the caller's
        # final-answer-only request, including structured and raw code attempts.
        # GPT-OSS supports levels instead of disabling thinking entirely.
        family = model.rsplit("/", 1)[-1].split(":", 1)[0].lower()
        body_data["think"] = ("high" if thinking else "low") if family == "gpt-oss" else thinking
        if response_format is not None:
            body_data["format"] = response_format
        body = json.dumps(body_data).encode()
        request = urllib.request.Request(
            target + "/api/generate", data=body,
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                data = json.load(response)
            if not isinstance(data, dict):
                raise ValueError("Respuesta del servidor malformada")
            if data.get("error"):
                raise ValueError(str(data["error"]))
            if not isinstance(data.get("response"), str):
                raise ValueError("El servidor no devolvio texto")
            text = data["response"].strip()
            metadata = {key: data[key] for key in (
                "done", "done_reason", "eval_count", "prompt_eval_count",
                "total_duration", "load_duration", "eval_duration")
                if isinstance(data.get(key), (str, int, float, bool))}
            reasoning = data.get("thinking")
            metadata.update(response_characters=len(text),
                            thinking_characters=len(reasoning) if isinstance(reasoning, str) else 0,
                            requested_think=body_data["think"],
                            requested_output_limit=options.get("num_predict"))
            error = ""
            if data.get("done_reason") == "length":
                error = "Respuesta truncada por el limite de tokens; no se acepta como entrega"
            elif data.get("done") is False:
                error = "Respuesta incompleta: el servidor no confirmo la finalizacion"
            elif not text:
                error = "Respuesta vacia"
            if error:
                if metadata["thinking_characters"] and not text:
                    error += "; el servidor devolvio thinking sin respuesta final"
                error += (f" (done={data.get('done', 'no informado')}; "
                          f"done_reason={data.get('done_reason', 'no informado')}; "
                          f"eval_count={data.get('eval_count', 'no informado')}; "
                          f"num_predict={options.get('num_predict', 'predeterminado')})")
                # Keep partial code as diagnostic evidence only, never as success.
                if text:
                    metadata["partial_response"] = text
                return ModelReply(False, "", model,
                                  f"{backend} · {target} · modelo {model}: {error}",
                                  backend=backend, metadata=metadata)
            if text:
                self._cache.put(prompt_hash, model, 0.0, thinking, text)
            return ModelReply(True, text, model, backend=backend, metadata=metadata)
        except (OSError, ValueError, urllib.error.URLError) as exc:
            detail = self._error_detail(exc)
            return ModelReply(False, "", model,
                              f"{backend} · {target} · modelo {model}: {detail}",
                              backend=backend)

    @staticmethod
    def _error_detail(exc: Exception) -> str:
        detail = str(exc)
        if isinstance(exc, urllib.error.HTTPError):
            try:
                body = json.loads(exc.read(8192))
                error = body.get("error", "") if isinstance(body, dict) else ""
                if isinstance(error, dict):
                    error = error.get("message", "")
                if error:
                    detail += ": " + str(error)[:1500]
            except (OSError, ValueError):
                pass
        return detail

    def _post_json(self, path: str, body: dict,
                   endpoint: str | None = None, *, raise_errors: bool = False) -> dict | None:
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
            if raise_errors:
                raise
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
