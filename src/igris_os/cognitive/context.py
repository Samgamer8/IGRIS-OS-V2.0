"""Contexto jerarquico para IGRIS OS.

No intenta reproducir Kimi Delta Attention: KDA pertenece al modelo neuronal.
Este modulo aplica la idea equivalente a nivel de aplicacion: mantener un nucleo
pequeno y siempre visible, contexto reciente y referencias historicas limitadas.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True, slots=True)
class ContextBudget:
    max_chars: int = 24000
    hot_chars: int = 10000
    warm_chars: int = 9000
    cold_chars: int = 5000


class HybridContextBuilder:
    """Compone HOT/WARM/COLD sin inyectar transcripciones infinitas."""

    def __init__(self, budget: ContextBudget | None = None) -> None:
        self.budget = budget or ContextBudget()

    @staticmethod
    def _clip(value: str, limit: int) -> str:
        text = str(value or "")
        if len(text) <= limit:
            return text
        # Conserva principio y final: el objetivo suele estar al principio y
        # los ultimos errores/decisiones al final.
        head = max(1, limit * 2 // 3)
        tail = max(1, limit - head - 18)
        return text[:head] + "\n...[recortado]...\n" + text[-tail:]

    def build(self, *, current_message: str, active_state: Mapping[str, Any],
              recent_context: Iterable[str] = (),
              retrieved_context: Iterable[str] = ()) -> dict[str, Any]:
        hot_items = [str(x) for x in recent_context if str(x).strip()][-8:]
        hot_raw = "\n".join(hot_items)
        hot = self._clip(hot_raw, self.budget.hot_chars)

        warm = {
            "active_domain": active_state.get("active_domain", ""),
            "active_intent": active_state.get("active_intent", ""),
            "active_goal": active_state.get("active_goal", ""),
            "active_target": active_state.get("active_target", ""),
            "active_mode": active_state.get("active_mode", ""),
            "last_capability": active_state.get("last_capability", ""),
            "constraints": list(active_state.get("constraints", ()))[:12],
            "recent_decisions": list(active_state.get("recent_decisions", ())) [-6:],
        }
        # El warm state es estructurado y pequeno; el recorte se aplica solo a
        # los campos de texto que pueden crecer accidentalmente.
        for key in ("active_goal", "active_target"):
            warm[key] = self._clip(str(warm.get(key, "")), 2200)

        cold_items = [str(x) for x in retrieved_context if str(x).strip()][-12:]
        cold = self._clip("\n".join(cold_items), self.budget.cold_chars)

        payload = {
            "hot": {
                "current_message": self._clip(current_message, 5000),
                "recent_turns": hot,
            },
            "warm": warm,
            "cold": {
                "retrieved_memory": cold,
            },
        }
        # Guardia global. Si excede el presupuesto por un estado anomalo,
        # reduce primero lo frio y despues lo reciente; nunca elimina el mensaje.
        approx = len(repr(payload))
        if approx > self.budget.max_chars:
            payload["cold"]["retrieved_memory"] = ""
        approx = len(repr(payload))
        if approx > self.budget.max_chars:
            payload["hot"]["recent_turns"] = self._clip(
                payload["hot"]["recent_turns"], max(1500, self.budget.hot_chars // 2))
        return payload
