"""Proveedor de modelos intercambiable para IGRIS OS.

Inspirado en patrones de agentes frontier (Kimi K3/Xinference), no en sus pesos:
- endpoint abstracto;
- razonamiento configurable;
- salida JSON estricta cuando el proveedor la soporta;
- preservacion opaca del mensaje completo para sesiones con tool-calling;
- fallback local sin convertir fallos de backend en falsos positivos.

El contenido de razonamiento de un proveedor nunca se registra ni se devuelve como
texto visible. Solo se conserva de forma opaca en memoria dentro de FrontierSession
cuando el protocolo del proveedor exige reenviar el mensaje completo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
import time
from typing import Any, Callable, Iterable, Mapping, Sequence
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from .ollama import ModelReply, OllamaClient


KIMI_ALIAS = "moonshot/kimi-k3"
XINFERENCE_PREFIX = "xinference/"
REMOTE_OPENAI_PREFIX = "remote-openai/"


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes", "si", "sí", "on"}


def _loopback_v1(url: str) -> bool:
    try:
        parsed = urlsplit(url.rstrip("/"))
        return (
            parsed.scheme == "http"
            and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
            and parsed.username is None
            and parsed.password is None
            and not parsed.query
            and not parsed.fragment
            and (parsed.port is None or 1 <= parsed.port <= 65535)
        )
    except ValueError:
        return False


@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(slots=True)
class FrontierTurn:
    """Resultado de una llamada conversacional con herramientas.

    ``assistant_message`` es opaco: puede contener campos privados del proveedor
    (por ejemplo reasoning_content). No debe persistirse en logs ni mostrarse.
    """

    ok: bool
    content: str
    model: str
    backend: str
    tool_calls: tuple[ToolCall, ...] = ()
    assistant_message: dict[str, Any] | None = field(default=None, repr=False)
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def public_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "content": self.content,
            "model": self.model,
            "backend": self.backend,
            "tool_calls": [
                {"id": item.id, "name": item.name, "arguments": item.arguments}
                for item in self.tool_calls
            ],
            "error": self.error,
            "metadata": dict(self.metadata),
        }


class FrontierGateway:
    """Cliente compatible con la interfaz historica ``OllamaClient``.

    Politica por defecto:
    - local siempre disponible mediante ``OllamaClient``;
    - Xinference solo loopback, si responde;
    - Kimi remoto solo cuando ``IGRIS_ALLOW_CLOUD_MODELS=1`` y existe
      ``MOONSHOT_API_KEY``.
    """

    def __init__(self, *, timeout: float = 180,
                 local: OllamaClient | None = None,
                 opener: urllib.request.OpenerDirector | None = None) -> None:
        self.timeout = float(timeout)
        self.local = local or OllamaClient(timeout=timeout)
        self._opener = opener or urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            urllib.request.HTTPHandler(),
            urllib.request.HTTPSHandler(),
        )
        self.output_token_limit = 8192
        self.context_window = 32768
        self._xin_cache: tuple[str, ...] = ()
        self._xin_cache_at = 0.0
        self._remote_cache: tuple[str, ...] = ()
        self._remote_cache_at = 0.0

    # ------------------------------------------------------------------
    # Discovery / routing
    # ------------------------------------------------------------------
    def models(self) -> tuple[str, ...]:
        names: list[str] = list(self.local.models())
        if self._cloud_enabled() and os.environ.get("MOONSHOT_API_KEY", "").strip():
            names.append(KIMI_ALIAS)
        names.extend(self._xinference_models())
        names.extend(self._remote_openai_models())
        return tuple(dict.fromkeys(name for name in names if name))

    def list_models(self) -> list[str]:
        return list(self.models())

    def backends(self) -> tuple[tuple[str, str], ...]:
        result = list(getattr(self.local, "backends", lambda: ())())
        endpoint = self._xinference_endpoint()
        if endpoint and self._xinference_models():
            result.append(("xinference", endpoint))
        if self._cloud_enabled() and os.environ.get("MOONSHOT_API_KEY", "").strip():
            result.append(("moonshot", "https://api.moonshot.ai/v1"))
        endpoint, _api_key = self._remote_openai_config()
        if endpoint and self._remote_openai_models():
            result.append(("remote-openai", endpoint))
        return tuple(result)

    @staticmethod
    def _cloud_enabled() -> bool:
        return _truthy(os.environ.get("IGRIS_ALLOW_CLOUD_MODELS"))

    @staticmethod
    def _xinference_endpoint() -> str:
        explicit = os.environ.get("IGRIS_XINFERENCE_ENDPOINT", "").strip()
        enabled = _truthy(os.environ.get("IGRIS_ENABLE_XINFERENCE")) or bool(explicit)
        if not enabled:
            return ""
        raw = explicit or "http://127.0.0.1:9997/v1"
        raw = raw.rstrip("/")
        if not _loopback_v1(raw):
            return ""
        return raw

    def _xinference_models(self) -> tuple[str, ...]:
        now = time.monotonic()
        if now - self._xin_cache_at < 10:
            return self._xin_cache
        endpoint = self._xinference_endpoint()
        if not endpoint:
            self._xin_cache = ()
            self._xin_cache_at = now
            return ()
        try:
            data = self._request_json("GET", endpoint + "/models", timeout=min(self.timeout, 0.8))
        except (OSError, ValueError, urllib.error.URLError):
            self._xin_cache = ()
            self._xin_cache_at = now
            return ()
        items = data.get("data", []) if isinstance(data, dict) else []
        result: list[str] = []
        for item in items if isinstance(items, list) else []:
            if isinstance(item, Mapping):
                model = str(item.get("id") or item.get("model") or "").strip()
                if model:
                    result.append(XINFERENCE_PREFIX + model)
        self._xin_cache = tuple(dict.fromkeys(result))
        self._xin_cache_at = now
        return self._xin_cache

    @staticmethod
    def _remote_openai_config() -> tuple[str, str]:
        """Require opt-in, HTTPS and an auth token before contacting a remote server."""
        enabled = _truthy(os.environ.get("IGRIS_ALLOW_REMOTE_MODELS"))
        endpoint = os.environ.get("IGRIS_REMOTE_OPENAI_ENDPOINT", "").strip().rstrip("/")
        api_key = os.environ.get("IGRIS_REMOTE_OPENAI_API_KEY", "").strip()
        if not enabled or not endpoint or not api_key:
            return "", ""
        try:
            parsed = urlsplit(endpoint)
            valid_port = parsed.port is None or 1 <= parsed.port <= 65535
            valid_path = parsed.path.rstrip("/").endswith("/v1")
            if (parsed.scheme != "https" or not parsed.hostname or not valid_port
                    or not valid_path or parsed.username or parsed.password
                    or parsed.query or parsed.fragment):
                return "", ""
        except ValueError:
            return "", ""
        return endpoint, api_key

    def _remote_openai_models(self) -> tuple[str, ...]:
        now = time.monotonic()
        if now - self._remote_cache_at < 10:
            return self._remote_cache
        endpoint, api_key = self._remote_openai_config()
        if not endpoint:
            self._remote_cache = ()
            self._remote_cache_at = now
            return ()
        try:
            data = self._request_json(
                "GET", endpoint + "/models",
                headers={"Authorization": "Bearer " + api_key},
                timeout=min(self.timeout, 1.5))
        except (OSError, ValueError, urllib.error.URLError):
            self._remote_cache = ()
            self._remote_cache_at = now
            return ()
        items = data.get("data", []) if isinstance(data, dict) else []
        models = []
        for item in items if isinstance(items, list) else []:
            if isinstance(item, Mapping):
                model = str(item.get("id") or item.get("model") or "").strip()
                if model:
                    models.append(REMOTE_OPENAI_PREFIX + model)
        self._remote_cache = tuple(dict.fromkeys(models))
        self._remote_cache_at = now
        return self._remote_cache

    # ------------------------------------------------------------------
    # Drop-in generation API
    # ------------------------------------------------------------------
    def generate(self, prompt: str, model: str, *, thinking: bool = False) -> ModelReply:
        if self._is_kimi(model):
            return self._remote_generate(
                prompt, model, structured_schema=None,
                reasoning_effort="high" if thinking else "low")
        if model.startswith((XINFERENCE_PREFIX, REMOTE_OPENAI_PREFIX)):
            return self._remote_generate(
                prompt, model, structured_schema=None,
                reasoning_effort="high" if thinking else "low")
        self._sync_local_limits()
        return self.local.generate(prompt, model, thinking=thinking)

    def generate_json(self, prompt: str, model: str, schema: dict) -> ModelReply:
        if self._is_kimi(model) or model.startswith((XINFERENCE_PREFIX, REMOTE_OPENAI_PREFIX)):
            effort = self._reasoning_effort(prompt, schema)
            return self._remote_generate(
                prompt, model, structured_schema=schema,
                reasoning_effort=effort)
        self._sync_local_limits()
        return self.local.generate_json(prompt, model, schema)

    def _sync_local_limits(self) -> None:
        self.local.output_token_limit = self.output_token_limit
        self.local.context_window = self.context_window

    @staticmethod
    def _is_kimi(model: str) -> bool:
        low = str(model or "").casefold()
        return low in {KIMI_ALIAS, "kimi-k3"} or low.endswith("/kimi-k3")

    def _reasoning_effort(self, prompt: str, schema: Mapping[str, Any]) -> str:
        explicit = os.environ.get("IGRIS_REASONING_EFFORT", "").strip().casefold()
        if explicit in {"low", "high", "max"}:
            return explicit
        props = schema.get("properties", {}) if isinstance(schema, Mapping) else {}
        # Clasificar intencion debe ser rapido; programacion/review necesita mas.
        if isinstance(props, Mapping) and {"domain", "intent", "confidence"}.issubset(props):
            return "low"
        if isinstance(props, Mapping) and ("approved" in props or "tool" in props):
            return "high"
        low = prompt.casefold()
        if any(marker in low for marker in ("revisor", "arquitect", "repara", "debug", "pruebas")):
            return "high"
        return "high"

    def _remote_generate(self, prompt: str, model: str, *,
                         structured_schema: dict | None,
                         reasoning_effort: str) -> ModelReply:
        backend, endpoint, remote_model, api_key = self._remote_target(model)
        if not endpoint:
            return ModelReply(False, "", model, "Proveedor remoto no configurado", backend=backend)

        body: dict[str, Any] = {
            "model": remote_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        if backend == "moonshot":
            body["reasoning_effort"] = reasoning_effort
            body["max_completion_tokens"] = max(1024, int(self.output_token_limit))
        else:
            body["temperature"] = 0.0
            body["max_tokens"] = max(1024, int(self.output_token_limit))

        if structured_schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "igris_response",
                    "strict": True,
                    "schema": self._strict_schema(structured_schema),
                },
            }

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = "Bearer " + api_key

        try:
            data = self._request_json(
                "POST", endpoint.rstrip("/") + "/chat/completions",
                body=body, headers=headers, timeout=self.timeout)
        except urllib.error.HTTPError as exc:
            # Algunos backends OpenAI-compatible no soportan json_schema.
            # Se reintenta solo en local Xinference, nunca degradamos el
            # contrato de Kimi que si lo documenta oficialmente.
            if structured_schema is not None and backend == "xinference" and exc.code in {400, 404, 422}:
                body.pop("response_format", None)
                schema_text = json.dumps(structured_schema, ensure_ascii=False, separators=(",", ":"))
                body["messages"] = [{"role": "user", "content": (
                    prompt + "\nDevuelve SOLO JSON valido que cumpla este esquema:\n" + schema_text)}]
                try:
                    data = self._request_json(
                        "POST", endpoint.rstrip("/") + "/chat/completions",
                        body=body, headers=headers, timeout=self.timeout)
                except (OSError, ValueError, urllib.error.URLError) as retry_exc:
                    return ModelReply(False, "", model, str(retry_exc), backend=backend)
            else:
                return ModelReply(False, "", model, self._http_error(exc), backend=backend)
        except (OSError, ValueError, urllib.error.URLError) as exc:
            return ModelReply(False, "", model, str(exc), backend=backend)

        try:
            choice = data["choices"][0]
            message = choice["message"]
            text = str(message.get("content") or "").strip()
            raw_reasoning = str(message.get("reasoning_content") or "")
            finish = str(choice.get("finish_reason") or "")
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            return ModelReply(False, "", model, "Respuesta remota malformada: " + str(exc), backend=backend)

        if finish == "length":
            return ModelReply(False, "", model, "Respuesta truncada por limite de tokens", backend=backend)
        metadata = {
            "reasoning_effort": reasoning_effort,
            "reasoning_present": bool(raw_reasoning),
            "reasoning_characters": len(raw_reasoning),
            "finish_reason": finish,
            "structured": structured_schema is not None,
        }
        # Nunca exponer el monologo interno en ModelReply.reasoning.
        return ModelReply(bool(text), text, model,
                          "" if text else "Respuesta vacia", "", backend, metadata)

    # ------------------------------------------------------------------
    # Native tool-calling session API (optional, provider-neutral)
    # ------------------------------------------------------------------
    def chat_turn(self, messages: Sequence[Mapping[str, Any]], *, model: str,
                  tools: Sequence[Mapping[str, Any]] = (),
                  tool_choice: str | Mapping[str, Any] | None = None,
                  reasoning_effort: str = "high") -> FrontierTurn:
        if not (self._is_kimi(model) or model.startswith((XINFERENCE_PREFIX, REMOTE_OPENAI_PREFIX))):
            return FrontierTurn(False, "", model, "local", error=(
                "El tool-calling nativo requiere un backend OpenAI-compatible configurado; "
                "las misiones locales usan el contrato JSON seguro de IGRIS."))
        backend, endpoint, remote_model, api_key = self._remote_target(model)
        body: dict[str, Any] = {
            "model": remote_model,
            "messages": [dict(item) for item in messages],
            "stream": False,
        }
        if tools:
            body["tools"] = [dict(item) for item in tools]
        if tool_choice is not None:
            body["tool_choice"] = tool_choice
        if backend == "moonshot":
            body["reasoning_effort"] = reasoning_effort if reasoning_effort in {"low", "high", "max"} else "high"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = "Bearer " + api_key
        try:
            data = self._request_json("POST", endpoint.rstrip("/") + "/chat/completions",
                                      body=body, headers=headers, timeout=self.timeout)
            choice = data["choices"][0]
            message = dict(choice["message"])
            content = str(message.get("content") or "")
            raw_reasoning = str(message.get("reasoning_content") or "")
            parsed_calls: list[ToolCall] = []
            for item in message.get("tool_calls") or []:
                function = item.get("function") or {}
                raw_args = function.get("arguments") or "{}"
                args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
                if not isinstance(args, dict):
                    raise ValueError("Los argumentos de tool_call deben ser un objeto")
                parsed_calls.append(ToolCall(
                    id=str(item.get("id") or ""),
                    name=str(function.get("name") or ""),
                    arguments=args,
                ))
            return FrontierTurn(
                True, content, model, backend, tuple(parsed_calls), message,
                metadata={
                    "reasoning_present": bool(raw_reasoning),
                    "reasoning_characters": len(raw_reasoning),
                    "finish_reason": choice.get("finish_reason"),
                })
        except (OSError, ValueError, KeyError, IndexError, TypeError, urllib.error.URLError) as exc:
            return FrontierTurn(False, "", model, backend, error=str(exc))

    def _remote_target(self, model: str) -> tuple[str, str, str, str]:
        if self._is_kimi(model):
            if not self._cloud_enabled():
                return "moonshot", "", "kimi-k3", ""
            key = os.environ.get("MOONSHOT_API_KEY", "").strip()
            return "moonshot", "https://api.moonshot.ai/v1", "kimi-k3", key
        if model.startswith(XINFERENCE_PREFIX):
            remote = model[len(XINFERENCE_PREFIX):]
            return "xinference", self._xinference_endpoint(), remote, ""
        if model.startswith(REMOTE_OPENAI_PREFIX):
            endpoint, api_key = self._remote_openai_config()
            remote = model[len(REMOTE_OPENAI_PREFIX):]
            return ("remote-openai", endpoint, remote, api_key) if endpoint else (
                "remote-openai", "", remote, "")
        return "", "", model, ""

    @staticmethod
    def _strict_schema(schema: Mapping[str, Any]) -> dict[str, Any]:
        """Copia el esquema y fija additionalProperties=False en objetos.

        Kimi/OpenAI strict JSON schema requiere contratos cerrados para evitar
        que el agente invente campos que el kernel no conoce.
        """
        def close(value: Any) -> Any:
            if isinstance(value, dict):
                out = {str(k): close(v) for k, v in value.items()}
                if out.get("type") == "object":
                    out.setdefault("additionalProperties", False)
                    props = out.get("properties")
                    if isinstance(props, dict) and "required" not in out:
                        out["required"] = list(props)
                return out
            if isinstance(value, list):
                return [close(item) for item in value]
            return value
        return close(dict(schema))

    def _request_json(self, method: str, url: str, *, body: Mapping[str, Any] | None = None,
                      headers: Mapping[str, str] | None = None,
                      timeout: float | None = None) -> dict[str, Any]:
        payload = None if body is None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=payload,
                                     headers=dict(headers or {}), method=method)
        with self._opener.open(req, timeout=timeout or self.timeout) as response:
            parsed = json.load(response)
        if not isinstance(parsed, dict):
            raise ValueError("Respuesta HTTP no es un objeto JSON")
        if parsed.get("error"):
            raise ValueError(str(parsed["error"]))
        return parsed

    @staticmethod
    def _http_error(exc: urllib.error.HTTPError) -> str:
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
        except Exception:
            detail = ""
        return f"HTTP {exc.code}: {detail or exc.reason}"


class FrontierSession:
    """Sesion multi-turno que preserva estado completo solo en RAM.

    Para Kimi K3 esto permite reenviar el mensaje del asistente sin eliminar
    reasoning_content/tool_calls, tal como exige su protocolo. La API publica
    de la clase nunca expone reasoning_content.
    """

    def __init__(self, gateway: FrontierGateway, model: str,
                 system: str = "") -> None:
        self.gateway = gateway
        self.model = model
        self._messages: list[dict[str, Any]] = []
        if system:
            self._messages.append({"role": "system", "content": system})

    def ask(self, content: str, *, tools: Sequence[Mapping[str, Any]] = (),
            tool_choice: str | Mapping[str, Any] | None = None,
            reasoning_effort: str = "high") -> FrontierTurn:
        self._messages.append({"role": "user", "content": content})
        turn = self.gateway.chat_turn(
            self._messages, model=self.model, tools=tools,
            tool_choice=tool_choice, reasoning_effort=reasoning_effort)
        if turn.ok and turn.assistant_message is not None:
            self._messages.append(dict(turn.assistant_message))
        return turn

    def add_tool_result(self, call_id: str, content: str) -> None:
        self._messages.append({
            "role": "tool", "tool_call_id": str(call_id), "content": str(content)})

    def public_history(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for item in self._messages:
            clean = {k: v for k, v in item.items()
                     if k not in {"reasoning_content", "reasoning", "thinking"}}
            if "tool_calls" in clean:
                # Los tool calls son acciones auditables, no razonamiento privado.
                clean["tool_calls"] = clean["tool_calls"]
            result.append(clean)
        return result


def build_model_client(*, timeout: float = 180) -> FrontierGateway:
    """Fabrica unica usada por UI y ProgrammingTeam."""
    return FrontierGateway(timeout=timeout)
