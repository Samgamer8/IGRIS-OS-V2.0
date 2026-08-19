from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence

from igris_os.ai import ModelReply, OllamaClient
from igris_os.ai.multi_provider import MultiProviderRouter, GenerationRequest, GenerationResponse, ProviderRank


class SpecialistRole(str, Enum):
    ARCHITECT = "architect"
    PROGRAMMER = "programmer"
    REVIEWER = "reviewer"
    DEVOPS = "devops"
    SECURITY = "security"
    QA = "qa"


@dataclass(frozen=True, slots=True)
class SpecialistProfile:
    role: SpecialistRole
    model: str
    system_prompt: str
    temperature: float = 0.2
    max_tokens: int = 4096


@dataclass(frozen=True, slots=True)
class SpecialistOutput:
    role: SpecialistRole
    ok: bool
    text: str
    model: str
    tokens_used: int = 0
    error: str = ""


class SpecialistRegistry:
    ROLES: dict[SpecialistRole, SpecialistProfile] = {
        SpecialistRole.ARCHITECT: SpecialistProfile(
            role=SpecialistRole.ARCHITECT,
            model="qwen2.5-coder:7b",
            system_prompt=(
                "Eres arquitecto de software senior. Analiza requerimientos, "
                "define contratos, selecciona patrones y estructura modular. "
                "Devuelve SOLO JSON: {\"plan\":\"...\",\"modules\":[...],"
                "\"interfaces\":[...],\"risks\":[...],\"acceptance\":[...]}. "
                "Sin markdown."
            ),
            temperature=0.1,
        ),
        SpecialistRole.PROGRAMMER: SpecialistProfile(
            role=SpecialistRole.PROGRAMMER,
            model="qwen2.5-coder:7b",
            system_prompt=(
                "Eres programador senior. Implementa codigo completo, probado, "
                "con manejo de errores y type hints. Devuelve SOLO JSON: "
                '{"source":"codigo completo","tests":"tests completos",'
                '"explanation":"cambios realizados"}. Sin markdown.'
            ),
            temperature=0.2,
        ),
        SpecialistRole.REVIEWER: SpecialistProfile(
            role=SpecialistRole.REVIEWER,
            model="qwen2.5-coder:14b",
            system_prompt=(
                "Eres revisor independiente. Aplica checklist: seguridad, "
                "rendimiento, legibilidad, tests, contratos. Devuelve SOLO JSON: "
                '{"approved":true,"score":0.95,"issues":[...],"suggestions":[...]}. '
                "Sin markdown."
            ),
            temperature=0.1,
        ),
        SpecialistRole.DEVOPS: SpecialistProfile(
            role=SpecialistRole.DEVOPS,
            model="qwen2.5-coder:7b",
            system_prompt=(
                "Eres ingeniero DevOps. Genera Dockerfile, CI, scripts de "
                "despliegue y configuracion. Devuelve SOLO JSON: "
                '{"dockerfile":"...","ci":"...","scripts":{...}}. Sin markdown.'
            ),
            temperature=0.2,
        ),
        SpecialistRole.SECURITY: SpecialistProfile(
            role=SpecialistRole.SECURITY,
            model="qwen2.5-coder:14b",
            system_prompt=(
                "Eres auditor de seguridad. Revisa inyecciones, secrets, "
                "permisos, dependencias. Devuelve SOLO JSON: "
                '{"vulnerabilities":[...],"severity":"high|medium|low",'
                '"remediation":"..."}. Sin markdown.'
            ),
            temperature=0.1,
        ),
        SpecialistRole.QA: SpecialistProfile(
            role=SpecialistRole.QA,
            model="qwen2.5-coder:7b",
            system_prompt=(
                "Eres ingeniero QA. Genera plan de pruebas, casos limite, "
                "datos sinteticos y verificaciones. Devuelve SOLO JSON: "
                '{"test_plan":"...","cases":[...],"data":[...]}. Sin markdown.'
            ),
            temperature=0.2,
        ),
    }

    def __init__(self, client: OllamaClient | None = None, use_multi_provider: bool = False) -> None:
        self.client = client or OllamaClient()
        self.use_multi_provider = use_multi_provider
        self.multi_provider = MultiProviderRouter() if use_multi_provider else None

    def available_models(self) -> Sequence[str]:
        try:
            return self.client.models()
        except Exception:
            return ()

    def execute(self, role: SpecialistRole, prompt: str) -> SpecialistOutput:
        profile = self.ROLES[role]
        
        # Use multi-provider router if enabled
        if self.use_multi_provider and self.multi_provider:
            task_type_map = {
                SpecialistRole.ARCHITECT: "architecture",
                SpecialistRole.PROGRAMMER: "code",
                SpecialistRole.REVIEWER: "review",
                SpecialistRole.DEVOPS: "code",
                SpecialistRole.SECURITY: "review",
                SpecialistRole.QA: "general",
            }
            
            request = GenerationRequest(
                prompt=prompt,
                system_prompt=profile.system_prompt,
                temperature=profile.temperature,
                max_tokens=profile.max_tokens,
                budget=float(os.getenv("DEFAULT_BUDGET", "0.10")),
                task_type=task_type_map.get(role, "general")
            )
            
            response = self.multi_provider.generate(request)
            
            if response.success:
                return SpecialistOutput(
                    role, True, response.text, 
                    f"{response.provider.value}/{response.model}",
                    response.tokens_used
                )
            else:
                return SpecialistOutput(
                    role, False, "", "multi_provider", 0,
                    response.error or "Multi-provider failed"
                )
        
        # Fallback to original Ollama-only logic
        installed = self.available_models()
        model = profile.model
        if installed and model not in installed:
            family = "qwen2.5-coder" if "coder" in model else "llama"
            for candidate in installed:
                if candidate.startswith(family):
                    model = candidate
                    break
            else:
                model = installed[0]
        reply: ModelReply = self.client.generate(
            profile.system_prompt + "\n\n" + prompt, model
        )
        if not reply.ok:
            return SpecialistOutput(role, False, "", model, 0,
                                   reply.error or "Modelo no disponible")
        return SpecialistOutput(role, True, reply.text, model,
                                getattr(reply, "tokens_used", 0))
