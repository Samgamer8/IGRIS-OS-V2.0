# -*- coding: utf-8 -*-
"""Cadena de especialistas delegados con degradacion controlada.

Prueba los especialistas en orden y se queda con el primero que entregue un
resultado valido. Es el mecanismo de fallback: Claude Code primero (si esta
disponible) y el modelo local Ollama despues, para que la delegacion funcione
incluso sin credito en la cuenta de Claude.
"""

from __future__ import annotations

from igris_os.delegation.claude_specialist import DelegatedSpecialist
from igris_os.delegation.contract import DelegatedResult, DelegatedTask
from igris_os.delegation.ollama_specialist import OllamaSpecialist


class ResilientSpecialist:
    """Ejecuta una tarea probando especialistas en cadena."""

    def __init__(self, specialists) -> None:
        self.specialists = tuple(specialists)

    def run(self, task: DelegatedTask) -> DelegatedResult:
        last: DelegatedResult | None = None
        for specialist in self.specialists:
            try:
                result = specialist.run(task)
            except Exception as exc:  # degradacion: un especialista no tumba el resto
                result = DelegatedResult(
                    False, "Especialista fallo: " + str(exc), returncode=-1)
            if result.ok:
                return result
            last = result
        return last or DelegatedResult(
            False, "Ningun especialista disponible", returncode=-1)


def build_resilient_specialist(
        local_model: str = "qwen2.5-coder:7b") -> ResilientSpecialist:
    """Cadena por defecto: Claude Code (si existe) -> Ollama local."""
    specialists = []
    try:
        specialists.append(DelegatedSpecialist())
    except FileNotFoundError:
        pass
    specialists.append(OllamaSpecialist(model=local_model))
    return ResilientSpecialist(specialists)
