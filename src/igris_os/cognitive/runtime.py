"""Orquestador cognitivo compacto de IGRIS OS.

Une comprensión semántica, estado, routing y Decision Graph sin ejecutar el
hardware directamente. La ejecución sigue perteneciendo al kernel de capacidades.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from .decision_graph import DecisionRecord, IgrisDecisionGraph
from .interpreter import SemanticInterpreter
from .router import route_frame
from .state import CognitiveStateStore


@dataclass(frozen=True, slots=True)
class CognitiveTurn:
    frame: Any
    action: Any
    decision: DecisionRecord


class IgrisCognitiveRuntime:
    def __init__(self, client: Any, state: CognitiveStateStore):
        self.state = state
        self.interpreter = SemanticInterpreter(client, state)
        self.graph = IgrisDecisionGraph()

    def understand_and_route(
        self,
        message: str,
        context: Iterable[str] = (),
        attachments: Sequence[str] = (),
    ) -> CognitiveTurn:
        frame = self.interpreter.interpret(message, context)
        action = route_frame(frame, message, attachments)
        decision = self.graph.evaluate(message, frame, action)
        capability = decision.capability if decision.capability else ""
        self.state.record(message, frame, capability)
        return CognitiveTurn(frame=frame, action=action, decision=decision)
