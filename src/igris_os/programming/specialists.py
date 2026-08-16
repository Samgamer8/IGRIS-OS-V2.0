from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence

from igris_os.ai import ModelReply, OllamaClient


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

    def __init__(self, client: OllamaClient | None = None) -> None:
        self.client = client or OllamaClient()

    def available_models(self) -> Sequence[str]:
        try:
            return self.client.models()
        except Exception:
            return ()

    def execute(self, role: SpecialistRole, prompt: str) -> SpecialistOutput:
        profile = self.ROLES[role]
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
