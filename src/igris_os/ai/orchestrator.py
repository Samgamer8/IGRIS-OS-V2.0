"""Enrutamiento local y explicable hacia modelos especialistas.

La clasificacion y la seleccion son ligeras y no necesitan GPU. El modulo solo
elige modelos que el cliente local anuncia; nunca instala ni inventa modelos.
"""
from __future__ import annotations

import re
import threading
import time
import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable


class ModelPurpose(str, Enum):
    GENERAL = "general"
    PROGRAMMING = "programming"
    REASONING = "reasoning"
    REVIEW = "review"


@dataclass(frozen=True, slots=True)
class ModelRoute:
    purpose: ModelPurpose
    model: str
    reason: str
    considered: tuple[str, ...] = ()
    resources: dict | None = None
    fallback: str | None = None
    backend: str | None = None


class ModelOrchestrator:
    """Enruta conversaciones a los modelos locales instalados y aptos.

    El limite de parametros evita elegir por accidente modelos grandes como
    DeepSeek-R1 32B en este perfil local. Puede cambiarse con
    ``IGRIS_ORCHESTRATOR_MAX_PARAMS_B`` tras medir el hardware.
    """

    CANDIDATES: dict[ModelPurpose, tuple[str, ...]] = {
        ModelPurpose.PROGRAMMING: (
            "qwen2.5-coder:7b", "deepseek-coder:6.7b",
            "qwen2.5-coder:1.5b", "qwen2.5-coder:1.5b-base",
            "llama3.1:8b", "deepseek-r1:8b",
        ),
        ModelPurpose.REASONING: (
            "deepseek-r1:8b", "llama3.1:8b", "qwen2.5-coder:7b",
            "qwen2.5-coder:1.5b", "qwen2.5-coder:1.5b-base",
        ),
        # El revisor prioriza una familia distinta al modelo de razonamiento
        # principal cuando ambos estan instalados, para reducir sesgo comun.
        ModelPurpose.REVIEW: (
            "llama3.1:8b", "deepseek-r1:8b", "qwen2.5-coder:7b",
            "qwen2.5-coder:1.5b", "qwen2.5-coder:1.5b-base",
        ),
        ModelPurpose.GENERAL: (
            "llama3.1:8b", "qwen2.5-coder:7b", "deepseek-r1:8b",
            "qwen2.5-coder:1.5b", "qwen2.5-coder:1.5b-base",
        ),
    }

    def __init__(self, client: Any, max_params_b: float | None = None):
        self.client = client
        self.max_params_b = self._configured_limit() if max_params_b is None else float(max_params_b)
        if self.max_params_b <= 0:
            raise ValueError("El limite de parametros debe ser mayor que cero")
        self._metadata_cache: dict[str, tuple[float, dict]] = {}
        self._metadata_lock = threading.Lock()

    @staticmethod
    def _configured_limit() -> float:
        import os
        raw = os.environ.get("IGRIS_ORCHESTRATOR_MAX_PARAMS_B", "8")
        try:
            value = float(raw)
        except ValueError:
            value = 8.0
        return value if value > 0 else 8.0

    @staticmethod
    def infer_purpose(objective: str, branch: str = "") -> ModelPurpose:
        text = unicodedata.normalize("NFKD", str(objective or "").casefold())
        text = "".join(char for char in text if not unicodedata.combining(char))
        review_markers = (
            "revisa", "revisar", "audita", "auditoria", "verifica", "verificar",
            "critica", "encuentra errores", "busca errores", "contrasta",
        )
        architecture_markers = (
            "arquitectura", "disena", "disea", "plan de trabajo", "hoja de ruta",
            "planifica", "estrategia", "razona", "debate", "compara enfoques",
        )
        if any(marker in text for marker in review_markers):
            return ModelPurpose.REVIEW
        if any(marker in text for marker in architecture_markers):
            return ModelPurpose.REASONING
        code_markers = (
            "codigo", "programa", "programar", "programacion", "bug", "error",
            "refactor", "compila", "implementa", "funcion", "clase", "software",
        )
        if branch in {"programming", "games", "artificial_intelligence"} or any(
            marker in text for marker in code_markers
        ):
            return ModelPurpose.PROGRAMMING
        return ModelPurpose.GENERAL

    def available_models(self) -> tuple[str, ...]:
        return tuple(name for name in self.discovered_models() if self._is_usable(name))

    def discovered_models(self) -> tuple[str, ...]:
        """Return backend-advertised names; selection still applies local policy."""
        try:
            models = self.client.models()
        except Exception:
            return ()
        return tuple(dict.fromkeys(
            str(name) for name in models if isinstance(name, str) and name.strip()))

    def route(self, purpose: ModelPurpose, *, available: Iterable[str] | None = None,
              preferred_model: str = "",
              resource_snapshot: dict | None = None) -> ModelRoute:
        purpose = ModelPurpose(purpose)
        models = tuple(available) if available is not None else self.discovered_models()
        usable = tuple(name for name in models if self._is_usable(name))
        
        try:
            from igris_os.ai.resources import get_system_resources, estimate_model_requirement, resource_fit
            resources_info = (dict(resource_snapshot) if resource_snapshot is not None
                              else get_system_resources())
            resources_info.pop("model_assessments", None)
        except ImportError:
            resources_info = {"ram_free_gb": None, "vram_free_gb": None, "uncertain": True}
            from igris_os.ai.resources import resource_fit
            estimate_model_requirement = lambda b: b * 0.8 + 1.5
        
        assessments: dict[str, dict] = {}

        def is_resource_safe(name: str) -> bool:
            req, source = self._model_requirement(name, estimate_model_requirement)
            if req is None:
                assessments[name] = {"safe": False, "source": source, "reason": "tamaño desconocido"}
                return False
            safe, reason = resource_fit(req, resources_info)
            assessments[name] = {
                "safe": safe, "source": source,
                "estimated_requirement_gb": round(req, 2), "reason": reason,
            }
            return safe

        resource_safe_models = [name for name in usable if is_resource_safe(name)]
        resources_info = {**resources_info, "model_assessments": assessments}

        if not resource_safe_models and self._remote_fallback_enabled():
            remote_candidates = tuple(
                name for name in models
                if str(name).casefold().startswith("remote-openai/")
                and self._is_opted_in_remote(name)
            ) + tuple(
                name for name in models
                if self._is_opted_in_remote(name)
                and not str(name).casefold().startswith("remote-openai/")
            )
            remote = next(iter(remote_candidates), "")
            if remote:
                backend = self._remote_backend_name(remote)
                resources_info.update({
                    "execution_scope": "external",
                    "external_backend": backend,
                    "external_data_notice": "El prompt y su contexto se enviarán al proveedor remoto.",
                    "external_cost_notice": "El proveedor puede aplicar límites o cargos propios.",
                })
                return ModelRoute(
                    purpose, remote,
                    "no hay modelo local apto; alternativa remota habilitada explícitamente; "
                    "el prompt y el contexto se enviarán al servidor configurado",
                    tuple(name for name in models if self._is_opted_in_remote(name)),
                    resources_info, remote, backend,
                )
        
        ordered: list[str] = []
        configured_preference = str(preferred_model or "").strip()
        if configured_preference:
            configured = next(
                (name for name in resource_safe_models
                 if name.casefold() == configured_preference.casefold()), None)
            if configured:
                ordered.append(configured)
        for candidate_preference in self.CANDIDATES[purpose]:
            match = next((name for name in resource_safe_models if self._matches(candidate_preference, name)), None)
            if match and match not in ordered:
                ordered.append(match)
                
        if ordered:
            chosen = ordered[0]
            backend = self._backend_name(chosen)
            assessment = assessments.get(chosen, {})
            uncertainty = "; estimación por etiqueta de parámetros" if assessment.get("source") == "parameter_tag_estimate" else ""
            if resources_info.get("uncertain"):
                uncertainty += "; alguna medición de recursos no está disponible"
            primary = next((
                name for name in resource_safe_models
                if self._matches(self.CANDIDATES[purpose][0], name)), "")
            fallback = chosen if chosen != primary else None
            if configured_preference and chosen.casefold() == configured_preference.casefold():
                reason = "modelo configurado disponible y apto para los recursos locales"
            elif configured_preference:
                reason = ("modelo configurado ausente o no apto; alternativa local "
                          "seleccionada con comprobación de recursos")
            else:
                reason = self._reason(purpose)
            if fallback and not configured_preference:
                reason = "especialista preferido no disponible con recursos suficientes; alternativa local segura"
            return ModelRoute(purpose, chosen, reason + uncertainty, usable, resources_info, fallback, backend)
        
        # No hay especialista resource_safe. Busca alternativa en resource_safe
        fallback_model = next((name for name in resource_safe_models if self._parameter_size(name) is not None), "")
        if fallback_model:
            reason = "especialista no instalado o excede memoria; alternativa segura disponible"
            return ModelRoute(purpose, fallback_model, reason, usable, resources_info, fallback_model, self._backend_name(fallback_model))
            
        # Nunca presentar un candidato que no tenga una comprobacion de memoria.
        reason = "no hay un modelo local apto para memoria disponible; no se fuerza fallback" if usable else "no hay un modelo local apto instalado"
        return ModelRoute(purpose, "", reason, usable, resources_info, None, None)

    def _backend_name(self, model: str) -> str | None:
        if self._is_opted_in_remote(model):
            return self._remote_backend_name(model)
        owner = getattr(self.client, "_backend_for", None)
        if not callable(owner):
            return None
        try:
            backend, _endpoint = owner(model)
            return str(backend)
        except Exception:
            return None

    @staticmethod
    def _remote_fallback_enabled() -> bool:
        import os
        truthy = {"1", "true", "yes", "si", "sí", "on"}
        return any(str(os.environ.get(name, "")).strip().casefold() in truthy for name in (
            "IGRIS_ALLOW_CLOUD_MODELS", "IGRIS_ALLOW_REMOTE_MODELS"))

    @staticmethod
    def _is_opted_in_remote(name: str) -> bool:
        import os
        low = str(name or "").casefold()
        truthy = {"1", "true", "yes", "si", "sí", "on"}
        if low.startswith("remote-openai/"):
            return str(os.environ.get("IGRIS_ALLOW_REMOTE_MODELS", "")).strip().casefold() in truthy
        return low == "moonshot/kimi-k3" and (
            str(os.environ.get("IGRIS_ALLOW_CLOUD_MODELS", "")).strip().casefold() in truthy)

    @classmethod
    def _remote_backend_name(cls, name: str) -> str:
        return "remote-openai" if str(name).casefold().startswith("remote-openai/") else "moonshot"

    def _model_requirement(self, name: str, estimate_model_requirement) -> tuple[float | None, str]:
        """Use size reported by the local backend when available, else tag estimate."""
        metadata = self._model_metadata(name)
        size_bytes = metadata.get("size_bytes")
        parameter_size = self._metadata_parameter_size(metadata)
        disk_estimate = None
        if isinstance(size_bytes, (int, float)) and size_bytes > 0:
            # Disk size is a lower bound; reserve headroom for runtime
            # allocations, dequantization and KV/context separately.
            disk_estimate = (size_bytes / (1024 ** 3)) * 1.2 + 1.5
        parameter_estimate = estimate_model_requirement(parameter_size) if parameter_size else None
        estimates = [value for value in (disk_estimate, parameter_estimate) if value is not None]
        if estimates:
            return max(estimates), str(metadata.get("source", "backend_metadata"))
        size_b = self._parameter_size(name)
        if size_b is None:
            return None, "unknown"
        return estimate_model_requirement(size_b), "parameter_tag_estimate"

    def _model_metadata(self, name: str) -> dict:
        """Cache backend metadata briefly so role routing does not repeat HTTP calls."""
        now = time.monotonic()
        with self._metadata_lock:
            cached = self._metadata_cache.get(name)
            if cached and now - cached[0] < 30:
                return cached[1]
        reader = getattr(self.client, "model_metadata", None)
        try:
            metadata = reader(name) if callable(reader) else None
            value = metadata if isinstance(metadata, dict) else {}
        except Exception:
            value = {}
        with self._metadata_lock:
            self._metadata_cache[name] = (now, value)
        return value

    @staticmethod
    def _metadata_parameter_size(metadata: dict) -> float | None:
        details = metadata.get("details", {})
        raw = details.get("parameter_size") if isinstance(details, dict) else None
        match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*([KMBT])", str(raw or "").upper())
        if not match:
            return None
        value = float(match.group(1))
        return value * {"K": 1e-6, "M": 1e-3, "B": 1.0, "T": 1000.0}[match.group(2)]

    @staticmethod
    def _reason(purpose: ModelPurpose) -> str:
        return {
            ModelPurpose.PROGRAMMING: "modelo local priorizado para programacion",
            ModelPurpose.REASONING: "modelo local priorizado para razonamiento y revision",
            ModelPurpose.REVIEW: "modelo local de otra familia priorizado para revision",
            ModelPurpose.GENERAL: "modelo local priorizado para conversacion general",
        }[purpose]

    @staticmethod
    def purpose_for_role(role: str) -> ModelPurpose:
        normalized = str(role or "").casefold()
        if any(token in normalized for token in (
            "implementador", "programador", "ingeniero_de_pruebas", "devops", "qa",
        )):
            return ModelPurpose.PROGRAMMING
        if any(token in normalized for token in ("revisor", "reviewer", "seguridad", "auditor")):
            return ModelPurpose.REVIEW
        if any(token in normalized for token in (
            "arquitect", "mission_commander", "investigador", "evaluador",
            "disenador", "diseador", "editor", "control_de_calidad",
        )):
            return ModelPurpose.REASONING
        return ModelPurpose.GENERAL

    def _is_usable(self, name: str) -> bool:
        lowered = str(name).casefold()
        if not lowered or any(tag in lowered for tag in (
                ":cloud", "cloud/", "moonshot/", "remote-openai/")):
            return False
        if any(tag in lowered for tag in ("embed", "minilm", "bge-", "mmproj")):
            return False
        size = self._reported_parameter_size(name) or self._parameter_size(lowered)
        return size is not None and size <= self.max_params_b

    def _reported_parameter_size(self, name: str) -> float | None:
        return self._metadata_parameter_size(self._model_metadata(name))

    @staticmethod
    def _parameter_size(name: str) -> float | None:
        match = re.search(r"(?:[:/\-_])([0-9]+(?:\.[0-9]+)?)b(?:\b|[-_])", name.casefold())
        if not match:
            # Ollama tags such as qwen2.5-coder:7b end at the size token.
            match = re.search(r":([0-9]+(?:\.[0-9]+)?)b$", name.casefold())
        return float(match.group(1)) if match else None

    @staticmethod
    def _matches(preferred: str, installed: str) -> bool:
        preferred = preferred.casefold()
        installed = installed.casefold()
        return installed == preferred or installed.startswith(preferred + "-")
