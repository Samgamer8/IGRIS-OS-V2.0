"""Comprensión contextual con barreras deterministas para IGRIS OS.

El LLM interpreta significado y continuidad. El código valida la salida,
recupera órdenes operativas mal etiquetadas y el router sólo permite
capacidades registradas. Las reglas deterministas también protegen el camino
principal frente a respuestas semánticas contradictorias.
"""
from __future__ import annotations

import json
from typing import Any, Iterable

from igris_os.ai.model_selection import cognitive_model_candidates
from igris_os.utils.json_parser import StrictJSONParser
from .models import IntentFrame
from .state import CognitiveStateStore
from .context import HybridContextBuilder


INTENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "domain": {"type": "string", "enum": [
            "conversation", "capability", "programming", "windows_admin",
            "files", "games", "multimedia", "research", "unknown"]},
        "intent": {"type": "string", "enum": [
            "chat", "explain", "capability_query",
            "create_project", "continue_project", "modify_project", "repair_project",
            "test_project", "audit_project",
            "diagnose_pc", "repair_windows", "optimize_pc",
            "inspect_files", "search_files", "open_path",
            "game_task", "multimedia_task", "research_task", "unknown"]},
        "mode": {"type": "string", "enum": [
            "explain", "execute", "continue", "inspect", "modify", "repair", "cancel"]},
        "goal": {"type": "string"},
        "target": {"type": "string"},
        "continuation": {"type": "boolean"},
        "requested_tools": {"type": "array", "maxItems": 12, "items": {"type": "string"}},
        "constraints": {"type": "array", "maxItems": 12, "items": {"type": "string"}},
        "risk": {"type": "string", "enum": [
            "none", "read_only", "safe_write", "admin", "restart", "destructive"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "needs_clarification": {"type": "boolean"},
        "clarification_question": {"type": "string"},
        "evidence": {"type": "array", "maxItems": 6, "items": {"type": "string"}},
    },
    "required": [
        "domain", "intent", "mode", "goal", "target", "continuation",
        "requested_tools", "constraints", "risk", "confidence",
        "needs_clarification", "clarification_question", "evidence",
    ],
}

SYSTEM = """Eres el intérprete semántico interno de IGRIS OS.
No respondes al usuario y no ejecutas herramientas. Tu única tarea es convertir
el último mensaje y su contexto en un JSON válido del esquema indicado.

Principios:
- Comprende el significado global; NO clasifiques por una palabra aislada.
- Usa el contexto de turnos anteriores y el ESTADO ACTIVO para resolver pronombres,
  elipsis y frases como 'hazlo tú', 'continúa', 'averígualo' o 'eso no'.
- Distingue preguntar cómo se hace (explain) de pedir que IGRIS lo haga (execute).
- Distingue una pregunta de capacidad de una orden real.
- Una tarea de programación, modificación, reparación, test o auditoría pertenece
  a domain=programming aunque el usuario no diga la palabra 'programar'.
- Si el usuario quiere que IGRIS actúe sobre Windows/PC, usa windows_admin.
- No inventes rutas, proyectos, capacidades, herramientas instaladas ni resultados.
- Si el usuario introduce un proyecto/repo local existente pero aún no da una acción o ruta,
  trátalo como contexto operativo de programación: audit_project + inspect + read_only y pide
  UNA aclaración concreta. No lo degradues a conversación genérica.
- Una ruta local aislada nunca es charla. Resuélvela contra el estado pendiente/activo; si no
  existe contexto suficiente, pide qué debe hacerse con esa ruta.
- Si falta un dato imprescindible que no puede inferirse del contexto, marca
  needs_clarification=true y formula UNA pregunta concreta.
- No guardes ni devuelvas razonamiento paso a paso. evidence contiene como máximo
  frases breves sobre qué datos del mensaje/contexto justifican la decisión.
- risk describe impacto potencial, no permiso concedido.
- Si el usuario cancela o niega una acción, mode=cancel.
- Salida: SOLO JSON.
"""


class SemanticInterpreter:
    def __init__(self, client: Any, state: CognitiveStateStore):
        self.client = client
        self.state = state
        self.context_builder = HybridContextBuilder()

    def interpret(self, message: str, context: Iterable[str] = ()) -> IntentFrame:
        objective = str(message or "").strip()
        if not objective:
            return IntentFrame("conversation", "chat", "explain", "Conversación vacía",
                               confidence=1.0, source="empty")
        models = cognitive_model_candidates(self._models())
        prompt = self._prompt(objective, context)
        errors: list[str] = []
        for model in models[:2]:
            try:
                reply = self._generate(prompt, model)
                if not getattr(reply, "ok", False):
                    errors.append(model + ": " + str(getattr(reply, "error", "fallo")))
                    continue
                raw = StrictJSONParser.extract(str(getattr(reply, "text", "")))
                frame = IntentFrame.from_mapping(raw, source="semantic:" + model)
                return self._guard(frame, objective)
            except (OSError, ValueError, TypeError, KeyError) as exc:
                errors.append(model + ": " + str(exc))
        return self._fallback(objective, errors)

    def _models(self) -> tuple[str, ...]:
        try:
            models = self.client.models()
            return tuple(models or ())
        except Exception:
            try:
                return tuple(self.client.list_models() or ())
            except Exception:
                return ()

    def _generate(self, prompt: str, model: str):
        if hasattr(self.client, "generate_json"):
            return self.client.generate_json(prompt, model, INTENT_SCHEMA)
        schema = json.dumps(INTENT_SCHEMA, ensure_ascii=False, separators=(",", ":"))
        return self.client.generate(prompt + "\nJSON_SCHEMA:\n" + schema, model)

    def _prompt(self, objective: str, context: Iterable[str]) -> str:
        payload = self.context_builder.build(
            current_message=objective,
            active_state=self.state.context(),
            recent_context=context,
        )
        return SYSTEM + "\nCONTEXTO_JERARQUICO:\n" + json.dumps(payload, ensure_ascii=False)

    def _guard(self, frame: IntentFrame, objective: str) -> IntentFrame:
        """Valida coherencia y aplicación antes de convertir intención en capacidad.

        El LLM aporta comprensión contextual; las reglas deterministas impiden
        que una orden operativa termine en chat por una etiqueta contradictoria,
        corrigen consultas de capacidad y dejan las peticiones ambiguas en
        aclaración. No conceden permisos: el kernel sigue controlando la ejecución.
        """
        from igris_os.application.intent_classifier import normalize_intent, classify_intent
        from igris_os.application.programming_followup import is_standalone_local_path
        text = normalize_intent(objective)
        data = frame.to_dict()
        state_context = self.state.context()

        # Una ruta aislada nunca llega al chat. Primero intenta completar el
        # contexto operativo pendiente/activo; si no existe, solicita una sola
        # aclaración en lugar de inventar significado con un modelo conversacional.
        if is_standalone_local_path(objective):
            target = objective.strip().strip('"').strip("'")
            context_domain = str(state_context.get("pending_domain") or state_context.get("active_domain") or "")
            if context_domain == "programming":
                intent = str(state_context.get("pending_intent") or state_context.get("active_intent") or "audit_project")
                if intent not in {
                    "create_project", "continue_project", "modify_project", "repair_project",
                    "test_project", "audit_project"
                }:
                    intent = "audit_project"
                mode = str(state_context.get("pending_mode") or state_context.get("active_mode") or "inspect")
                if mode not in {"execute", "continue", "inspect", "modify", "repair"}:
                    mode = "inspect"
                return IntentFrame(
                    domain="programming", intent=intent, mode=mode,
                    goal=str(state_context.get("pending_goal") or state_context.get("active_goal") or "revisar el proyecto indicado"),
                    target=target, continuation=True,
                    constraints=tuple(state_context.get("pending_constraints") or state_context.get("constraints") or ()),
                    risk="read_only" if mode == "inspect" else "safe_write",
                    confidence=max(0.90, frame.confidence), needs_clarification=False,
                    source=frame.source + ":path_context",
                    evidence=tuple(frame.evidence) + ("standalone_local_path",),
                )
            return IntentFrame(
                domain="files", intent="inspect_files", mode="inspect",
                goal="determinar qué debe hacerse con la ruta local indicada",
                target=target, continuation=False, risk="read_only",
                confidence=0.99, needs_clarification=True,
                clarification_question="He recibido una ruta local. ¿Qué quieres que haga con esa carpeta?",
                source=frame.source + ":path_guard", evidence=("standalone_local_path",),
            )

        # El clasificador determinista es una barrera de producto: una orden
        # clara no puede degradarse a chat porque el modelo devuelva, por
        # ejemplo, programming/explain o conversation/chat.
        fallback_decision = classify_intent(
            objective, has_active_programming_context=(
                state_context.get("active_domain") == "programming" or
                state_context.get("pending_domain") == "programming"))

        if (fallback_decision.kind == "capability" and
                (frame.domain != "capability" or frame.intent != "capability_query")):
            return IntentFrame(
                domain="capability", intent="capability_query", mode="explain",
                goal=objective, risk="none",
                confidence=fallback_decision.confidence,
                source=frame.source + ":deterministic_capability_guard",
                evidence=fallback_decision.reasons,
            )

        if fallback_decision.kind == "programming":
            if fallback_decision.subtype == "context":
                return IntentFrame(
                    domain="programming", intent="audit_project", mode="inspect",
                    goal=objective,
                    target=str(state_context.get("active_target") or "").strip(),
                    continuation=False, risk="read_only",
                    confidence=fallback_decision.confidence,
                    needs_clarification=True,
                    clarification_question=(
                        "¿Qué quieres que haga con ese proyecto: analizarlo, corregirlo, "
                        "mejorarlo o continuar su desarrollo? Indica la carpeta si aún no está seleccionada."
                    ),
                    source=frame.source + ":deterministic_project_context_guard",
                    evidence=fallback_decision.reasons,
                )

            programming_mapping = {
                "create": ("create_project", "execute"),
                "continue": ("continue_project", "continue"),
                "followup": ("continue_project", "continue"),
                "modify": ("modify_project", "modify"),
                "repair": ("repair_project", "repair"),
                "test": ("test_project", "inspect"),
                "audit": ("audit_project", "inspect"),
            }
            mapped = programming_mapping.get(fallback_decision.subtype)
            if mapped is None:
                return IntentFrame(
                    domain="unknown", intent="unknown", mode="explain",
                    goal=objective, confidence=fallback_decision.confidence,
                    needs_clarification=True,
                    clarification_question=(
                        "He detectado una petición sobre un proyecto, pero no una acción concreta. "
                        "¿Qué resultado quieres que produzca?"
                    ),
                    source=frame.source + ":deterministic_programming_guard",
                    evidence=fallback_decision.reasons,
                )

            expected_intent, expected_mode = mapped
            from igris_os.application.mission_router import _existing_directory_sources
            has_resolved_path = bool(_existing_directory_sources(objective))
            can_resolve_without_question = (
                fallback_decision.subtype == "create" or has_resolved_path or
                bool(str(state_context.get("active_target") or "").strip()))
            if (frame.domain != "programming" or frame.intent != expected_intent
                    or frame.goal != objective
                    or (frame.needs_clarification and can_resolve_without_question)):
                active_target = str(state_context.get("active_target") or "").strip()
                target = active_target if fallback_decision.subtype in {"continue", "followup"} else ""
                risk = "read_only" if expected_mode == "inspect" else "safe_write"
                if frame.risk in {"admin", "restart", "destructive"}:
                    risk = frame.risk
                return IntentFrame(
                    domain="programming", intent=expected_intent,
                    mode=expected_mode, goal=objective, target=target,
                    continuation=fallback_decision.subtype in {"continue", "followup"},
                    risk=risk, confidence=fallback_decision.confidence,
                    source=frame.source + ":deterministic_programming_guard",
                    evidence=fallback_decision.reasons + ("operation_overrides_chat_label",),
                )

        if (fallback_decision.kind == "task" and
                (frame.domain == "conversation" or frame.intent in {"chat", "explain"})):
            return IntentFrame(
                domain="unknown", intent="unknown", mode="explain",
                goal=objective, confidence=fallback_decision.confidence,
                needs_clarification=True,
                clarification_question=(
                    "He detectado una orden, pero no puedo asociarla a una capacidad ejecutable con seguridad. "
                    "Concreta el resultado o el tipo de archivo que esperas."
                ),
                source=frame.source + ":unresolved_task_guard",
                evidence=fallback_decision.reasons,
            )

        if (fallback_decision.kind == "conversation" and
                frame.domain != "conversation" and frame.intent in {"chat", "explain"}):
            return IntentFrame(
                domain="conversation",
                intent=("explain" if fallback_decision.subtype == "technical_advice" else "chat"),
                mode="explain", goal=objective, confidence=fallback_decision.confidence,
                source=frame.source + ":deterministic_conversation_guard",
                evidence=fallback_decision.reasons,
            )

        # Una continuación de programación no debe perder el target activo sólo
        # porque el modelo omita repetir la ruta en el nuevo turno.
        if frame.domain == "programming" and not str(frame.target or "").strip():
            active_target = str(state_context.get("active_target") or "").strip()
            if active_target:
                data.update(target=active_target, continuation=True)
                frame = IntentFrame.from_mapping(data, source=frame.source)
                data = frame.to_dict()

        # Una intención operativa con confianza baja debe aclararse en vez de ejecutar.
        if frame.operational and frame.confidence < 0.62 and not frame.needs_clarification:
            data.update(
                needs_clarification=True,
                clarification_question="Necesito concretar qué acción quieres que ejecute antes de actuar.",
            )
            return IntentFrame.from_mapping(data, source=frame.source)
        return frame

    def _fallback(self, objective: str, errors: list[str]) -> IntentFrame:
        from igris_os.application.intent_classifier import classify_intent
        from igris_os.application.programming_followup import is_standalone_local_path
        state_context = self.state.context()

        # Una ruta aislada puede ser la respuesta exacta a una aclaración
        # pendiente. No requiere modelo ni palabras activadoras para mantener
        # la continuidad semántica del encargo.
        if (state_context.get("pending_domain") == "programming"
                and is_standalone_local_path(objective)):
            pending_intent = str(state_context.get("pending_intent") or "audit_project")
            pending_mode = str(state_context.get("pending_mode") or "inspect")
            if pending_intent not in {
                "create_project", "continue_project", "modify_project", "repair_project",
                "test_project", "audit_project"
            }:
                pending_intent = "audit_project"
            if pending_mode not in {"execute", "continue", "inspect", "modify", "repair"}:
                pending_mode = "inspect"
            return IntentFrame(
                domain="programming",
                intent=pending_intent,
                mode=pending_mode,
                goal=str(state_context.get("pending_goal") or "revisar el proyecto indicado"),
                target=objective.strip().strip('\"').strip("'"),
                continuation=True,
                constraints=tuple(state_context.get("pending_constraints") or ()),
                risk="read_only" if pending_mode == "inspect" else "safe_write",
                confidence=0.82,
                needs_clarification=False,
                source="fallback:pending_path",
                evidence=("ruta recibida como respuesta a aclaracion pendiente",),
            )

        decision = classify_intent(objective, has_active_programming_context=(
            state_context.get("active_domain") == "programming" or
            state_context.get("pending_domain") == "programming"))
        mapping = {
            ("conversation", "technical_advice"): ("conversation", "explain", "explain"),
            ("conversation", "greeting"): ("conversation", "chat", "explain"),
            ("capability", "programming"): ("capability", "capability_query", "explain"),
            ("capability", "general"): ("capability", "capability_query", "explain"),
            ("programming", "create"): ("programming", "create_project", "execute"),
            ("programming", "continue"): ("programming", "continue_project", "continue"),
            ("programming", "followup"): ("programming", "continue_project", "continue"),
            ("programming", "modify"): ("programming", "modify_project", "modify"),
            ("programming", "repair"): ("programming", "repair_project", "repair"),
            ("programming", "test"): ("programming", "test_project", "inspect"),
            ("programming", "audit"): ("programming", "audit_project", "inspect"),
            ("programming", "context"): ("programming", "audit_project", "inspect"),
        }
        domain, intent, mode = mapping.get(
            (decision.kind, decision.subtype),
            ("unknown", "unknown", "explain"),
        )
        needs = (domain == "unknown" and decision.kind != "conversation") or (
            decision.kind == "programming" and decision.subtype == "context")
        frame = IntentFrame(
            domain=domain,
            intent=intent,
            mode=mode,
            goal=objective,
            continuation=(mode == "continue"),
            # Las decisiones deterministas de alta confianza son suficientes
            # para ejecutar el fallback local; no deben convertirse en una
            # pregunta solo porque el modelo semántico no esté disponible.
            confidence=decision.confidence,
            needs_clarification=needs,
            clarification_question=(
                "¿Cuál es la ruta exacta de la carpeta del proyecto que quieres que revise?"
                if decision.kind == "programming" and decision.subtype == "context" else
                "No he podido interpretar el encargo con suficiente seguridad. ¿Qué resultado quieres que obtenga?"
                if needs else ""),
            source="fallback",
            evidence=tuple(errors[-2:]),
        )
        return self._guard(frame, objective)
