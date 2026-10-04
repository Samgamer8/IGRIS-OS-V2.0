"""IGRIS Decision Graph (IDG).

No almacena cadenas de pensamiento. Registra únicamente nodos auditables:
comprensión -> routing -> contrato -> permiso -> observación/verificación.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import time
from typing import Any

from .contracts import CompiledAction, ContractViolation, compile_action
from .models import IntentFrame


class DecisionStatus(str, Enum):
    CHAT = "chat"
    CLARIFY = "clarify"
    READY = "ready"
    REQUIRES_CONFIRMATION = "requires_confirmation"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class DecisionNode:
    kind: str
    status: str
    evidence: tuple[str, ...] = ()
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DecisionRecord:
    objective: str
    status: DecisionStatus
    frame: IntentFrame
    capability: str = ""
    compiled_payload: dict[str, Any] = field(default_factory=dict)
    nodes: tuple[DecisionNode, ...] = ()
    created_at: float = field(default_factory=time.time)

    def public_dict(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "status": self.status.value,
            "intent": self.frame.to_dict(),
            "capability": self.capability,
            "compiled_payload": dict(self.compiled_payload),
            "nodes": [asdict(node) for node in self.nodes],
            "created_at": self.created_at,
        }


class IgrisDecisionGraph:
    """Compila una interpretación semántica en una decisión auditable."""

    def evaluate(self, objective: str, frame: IntentFrame, routed_action) -> DecisionRecord:
        nodes: list[DecisionNode] = [DecisionNode(
            "understanding", "ok",
            evidence=tuple(frame.evidence[:6]),
            data={
                "domain": frame.domain,
                "intent": frame.intent,
                "mode": frame.mode,
                "goal": frame.goal,
                "confidence": frame.confidence,
            },
        )]

        if routed_action.kind == "chat":
            nodes.append(DecisionNode("routing", "chat"))
            return DecisionRecord(objective, DecisionStatus.CHAT, frame, nodes=tuple(nodes))
        if routed_action.kind == "clarify":
            nodes.append(DecisionNode("routing", "clarify", data=dict(routed_action.payload)))
            return DecisionRecord(objective, DecisionStatus.CLARIFY, frame, nodes=tuple(nodes))
        if routed_action.kind == "cancel":
            nodes.append(DecisionNode("routing", "cancel"))
            return DecisionRecord(objective, DecisionStatus.BLOCKED, frame, nodes=tuple(nodes))
        if routed_action.kind != "capability" or not routed_action.capability:
            nodes.append(DecisionNode("routing", "invalid"))
            return DecisionRecord(objective, DecisionStatus.BLOCKED, frame, nodes=tuple(nodes))

        nodes.append(DecisionNode(
            "routing", "ok", data={"capability": routed_action.capability}))
        try:
            compiled: CompiledAction = compile_action(
                routed_action.capability, routed_action.payload)
        except ContractViolation as exc:
            nodes.append(DecisionNode("contract", "rejected", evidence=(str(exc),)))
            return DecisionRecord(
                objective, DecisionStatus.BLOCKED, frame,
                capability=routed_action.capability, nodes=tuple(nodes))

        nodes.append(DecisionNode(
            "contract", "ok", data={"contract": compiled.contract}))

        # Un riesgo destructivo declarado por el intérprete nunca se convierte
        # silenciosamente en ejecución automática. El kernel aplica además su
        # propia política de CapabilitySpec.
        if frame.risk == "destructive":
            nodes.append(DecisionNode(
                "policy", "blocked", evidence=("intent_risk=destructive",)))
            status = DecisionStatus.BLOCKED
        elif routed_action.requires_confirmation or frame.risk in {"admin", "restart"}:
            nodes.append(DecisionNode("policy", "confirmation_required"))
            status = DecisionStatus.REQUIRES_CONFIRMATION
        else:
            nodes.append(DecisionNode("policy", "ready"))
            status = DecisionStatus.READY

        return DecisionRecord(
            objective=objective,
            status=status,
            frame=frame,
            capability=compiled.capability,
            compiled_payload=compiled.payload,
            nodes=tuple(nodes),
        )
