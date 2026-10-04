"""Modelos de decisión cognitiva de IGRIS OS.

No guardan razonamiento privado del modelo. Sólo decisiones auditables y
estructuradas que el kernel puede validar antes de ejecutar nada.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

DOMAINS = frozenset({
    "conversation", "capability", "programming", "windows_admin",
    "files", "games", "multimedia", "research", "unknown",
})
INTENTS = frozenset({
    "chat", "explain", "capability_query",
    "create_project", "continue_project", "modify_project", "repair_project",
    "test_project", "audit_project",
    "diagnose_pc", "repair_windows", "optimize_pc",
    "inspect_files", "search_files", "open_path",
    "game_task", "multimedia_task", "research_task", "unknown",
})
MODES = frozenset({
    "explain", "execute", "continue", "inspect", "modify", "repair", "cancel",
})
RISKS = frozenset({
    "none", "read_only", "safe_write", "admin", "restart", "destructive",
})


@dataclass(frozen=True, slots=True)
class IntentFrame:
    domain: str
    intent: str
    mode: str
    goal: str
    target: str = ""
    continuation: bool = False
    requested_tools: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    risk: str = "none"
    confidence: float = 0.0
    needs_clarification: bool = False
    clarification_question: str = ""
    source: str = "semantic"
    evidence: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], *, source: str = "semantic") -> "IntentFrame":
        if not isinstance(raw, Mapping):
            raise ValueError("La interpretación debe ser un objeto")
        domain = str(raw.get("domain", "")).strip()
        intent = str(raw.get("intent", "")).strip()
        mode = str(raw.get("mode", "")).strip()
        risk = str(raw.get("risk", "none")).strip()
        if domain not in DOMAINS:
            raise ValueError("Dominio cognitivo no permitido: " + domain)
        if intent not in INTENTS:
            raise ValueError("Intención cognitiva no permitida: " + intent)
        if mode not in MODES:
            raise ValueError("Modo cognitivo no permitido: " + mode)
        if risk not in RISKS:
            raise ValueError("Riesgo cognitivo no permitido: " + risk)

        try:
            confidence = float(raw.get("confidence", 0.0))
        except (TypeError, ValueError) as exc:
            raise ValueError("confidence debe ser numérico") from exc
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence fuera de rango")

        def strings(name: str) -> tuple[str, ...]:
            value = raw.get(name, ())
            if value is None:
                return ()
            if not isinstance(value, (list, tuple)):
                raise ValueError(name + " debe ser una lista")
            result = tuple(str(item).strip() for item in value if str(item).strip())
            if len(result) > 12:
                raise ValueError(name + " supera el límite")
            return result

        goal = str(raw.get("goal", "")).strip()
        if not goal:
            raise ValueError("Falta goal")
        question = str(raw.get("clarification_question", "") or "").strip()
        needs = bool(raw.get("needs_clarification", False))
        if needs and not question:
            question = "Necesito una aclaración breve para ejecutar el encargo correctamente."

        return cls(
            domain=domain,
            intent=intent,
            mode=mode,
            goal=goal[:1200],
            target=str(raw.get("target", "") or "").strip()[:1000],
            continuation=bool(raw.get("continuation", False)),
            requested_tools=strings("requested_tools"),
            constraints=strings("constraints"),
            risk=risk,
            confidence=confidence,
            needs_clarification=needs,
            clarification_question=question[:800],
            source=source,
            evidence=strings("evidence"),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("requested_tools", "constraints", "evidence"):
            data[key] = list(data[key])
        return data

    @property
    def operational(self) -> bool:
        return self.mode in {"execute", "continue", "inspect", "modify", "repair"}
