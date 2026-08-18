# -*- coding: utf-8 -*-
"""Orquestacion de especialistas externos de codificacion.

Claude Code (agente con herramientas) y el modelo local Ollama (genera-y-
escribe) comparten el mismo contrato y verificacion. ``ResilientSpecialist``
encadena ambos con degradacion controlada.
"""

from .claude_specialist import DelegatedSpecialist, clean_env
from .contract import (DEFAULT_ALLOWED_TOOLS, DelegatedResult, DelegatedTask)
from .ollama_specialist import OllamaSpecialist
from .resilient import ResilientSpecialist, build_resilient_specialist

__all__ = [
    "DEFAULT_ALLOWED_TOOLS",
    "DelegatedResult",
    "DelegatedSpecialist",
    "DelegatedTask",
    "OllamaSpecialist",
    "ResilientSpecialist",
    "build_resilient_specialist",
    "clean_env",
]
