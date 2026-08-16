# -*- coding: utf-8 -*-
"""Enrutado de modelos por dificultad, tarea y presupuesto.

Elige el modelo local de Ollama mas adecuado entre los realmente instalados:

- simple  -> modelo pequeno y rapido (qwen2.5-coder:1.5b / llama3.2);
- normal  -> modelo mediano (qwen2.5-coder:7b / llama3.1:8b);
- complex -> modelo grande (qwen2.5-coder:14b).

Seleccion por politica (``RoutingMode``):

- LOCAL_ONLY      -> solo modelos locales (por defecto, privacidad);
- LOCAL_PREFERRED -> local si existe, nube solo si no hay local;
- MAX_QUALITY     -> el modelo local mas capaz;
- MAX_SAVINGS     -> el modelo local mas pequeno.

Presupuesto (``Budget``): limita el numero de tokens estimados de la peticion
y prefiere el modelo mas pequeno que quepa en su ventana de contexto, para no
gastar recursos en tareas simples. Nunca inventa un modelo no instalado.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from igris_os.ai.ollama import OllamaClient


class Difficulty(str, Enum):
    SIMPLE = "simple"
    NORMAL = "normal"
    COMPLEX = "complex"


class RoutingMode(str, Enum):
    LOCAL_ONLY = "local_only"
    LOCAL_PREFERRED = "local_preferred"
    MAX_QUALITY = "max_quality"
    MAX_SAVINGS = "max_savings"


@dataclass(frozen=True, slots=True)
class Budget:
    max_tokens: int = 0  # 0 = sin limite

    def __post_init__(self) -> None:
        if self.max_tokens < 0:
            raise ValueError("max_tokens no puede ser negativo")


@dataclass(frozen=True, slots=True)
class Route:
    model: str
    difficulty: Difficulty
    reason: str = ""
    mode: RoutingMode = RoutingMode.LOCAL_ONLY
    estimated_tokens: int = 0


class ModelRouter:
    """Selecciona un modelo local disponible segun dificultad, tarea y coste."""

    CODER_TIERS: dict[Difficulty, tuple[str, ...]] = {
        Difficulty.SIMPLE: ("qwen2.5-coder:1.5b", "qwen2.5-coder:1.5b-base"),
        Difficulty.NORMAL: ("qwen2.5-coder:7b", "qwen2.5-coder:latest"),
        Difficulty.COMPLEX: ("qwen2.5-coder:14b", "qwen2.5-coder:7b"),
    }
    GENERAL_TIERS: dict[Difficulty, tuple[str, ...]] = {
        Difficulty.SIMPLE: ("llama3.1:8b", "llama3.1:latest",
                            "llama3.2:latest", "qwen2.5-coder:1.5b"),
        Difficulty.NORMAL: ("llama3.1:8b", "llama3.1:latest", "llama3:latest"),
        Difficulty.COMPLEX: ("llama3.1:8b", "llama3.2:latest"),
    }
    CONTEXT_WINDOW: dict[str, int] = {
        "qwen2.5-coder:1.5b": 32768, "qwen2.5-coder:1.5b-base": 32768,
        "qwen2.5-coder:7b": 32768, "qwen2.5-coder:latest": 32768,
        "qwen2.5-coder:14b": 32768,
        "llama3.1:8b": 131072, "llama3.1:latest": 131072,
        "llama3:latest": 8192, "llama3.2:latest": 131072,
    }

    def __init__(self, client: OllamaClient | None = None) -> None:
        self.client = client or OllamaClient()

    def route(self, difficulty: Difficulty, *, code: bool = False,
              mode: RoutingMode = RoutingMode.LOCAL_ONLY,
              budget: Budget | None = None,
              objective: str = "") -> Route:
        installed = self.client.models()
        if not installed:
            return Route("", difficulty, "Ollama sin modelos instalados", mode)
        difficulty = self._adjust(difficulty, mode)
        tiers = self.CODER_TIERS if code else self.GENERAL_TIERS
        chosen = ""
        reason = ""
        for name in tiers[difficulty]:
            if name in installed:
                chosen, reason = name, "nivel seleccionado"
                break
        if not chosen:
            family = "qwen2.5-coder" if code else "llama"
            for name in sorted(installed):
                if name.startswith(family):
                    chosen, reason = name, "nivel no disponible, familia"
                    break
        if not chosen:
            chosen, reason = sorted(installed)[0], "modelo instalado"

        estimated = self.estimate_tokens(objective, difficulty)
        if budget and budget.max_tokens > 0:
            chosen, reason = self._fit_budget(
                chosen, estimated, budget.max_tokens, installed, reason)
        return Route(chosen, difficulty, reason, mode, estimated)

    @staticmethod
    def _adjust(difficulty: Difficulty, mode: RoutingMode) -> Difficulty:
        if mode is RoutingMode.MAX_SAVINGS:
            return Difficulty.SIMPLE
        if mode is RoutingMode.MAX_QUALITY:
            return Difficulty.COMPLEX
        return difficulty

    def _fit_budget(self, chosen: str, estimated: int, max_tokens: int,
                    installed: tuple[str, ...], reason: str) -> tuple[str, str]:
        needed = estimated + max_tokens
        candidates = sorted(
            installed,
            key=lambda name: (self._size_hint(name), self._context_window(name)))
        # El mas pequeno (mas barato) que quepa en la ventana de contexto.
        for name in candidates:
            if self._context_window(name) >= needed:
                return name, (reason + ", ajustado a presupuesto"
                              if name != chosen else reason)
        # Si ninguno cabe, el de mayor ventana (mejor esfuerzo).
        return candidates[-1], reason + ", supera presupuesto (mejor esfuerzo)"

    def _context_window(self, model: str) -> int:
        return self.CONTEXT_WINDOW.get(model, 8192)

    @staticmethod
    def _size_hint(model: str) -> float:
        """Tamano aproximado en miles de millones de parametros (para ordenar
        por coste cuando la ventana de contexto es igual)."""
        import re
        match = re.search(r":(\d+(?:\.\d+)?)b", model)
        return float(match.group(1)) if match else 8.0

    @staticmethod
    def estimate_tokens(objective: str, difficulty: Difficulty) -> int:
        """Estimacion burda de tokens de la peticion (entrada + salida)."""
        words = max(1, len(objective.split()))
        base = {Difficulty.SIMPLE: 128, Difficulty.NORMAL: 512,
                Difficulty.COMPLEX: 2048}[difficulty]
        return int(words * 1.4) + base

    @staticmethod
    def infer_difficulty(objective: str) -> Difficulty:
        """Heuristica simple de dificultad por longitud y senales explicitas."""
        text = objective.strip().casefold()
        words = text.split()
        complex_markers = (
            "arquitectura", "migrar", "refactorizar", "sistema", "motor",
            "complejo", "complicado", "produccion", "integracion", "seguridad",
            "optimizar", "motor de", "multijugador", "3d", "base de datos",
        )
        simple_markers = (
            "resume", "resumen", "explica", "que es", "hola", "traduce",
            "corrige este texto", "comenta", "pequeno", "sencillo", "rapido",
        )
        if any(marker in text for marker in complex_markers):
            return Difficulty.COMPLEX
        if any(marker in text for marker in simple_markers):
            return Difficulty.SIMPLE
        if len(words) <= 12:
            return Difficulty.SIMPLE
        if len(words) >= 45 or "detallado" in text:
            return Difficulty.COMPLEX
        return Difficulty.NORMAL
