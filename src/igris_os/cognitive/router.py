"""Traduce intención semántica validada a capacidades conocidas del kernel."""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

from .models import IntentFrame


_PROGRAMMING_EXISTING = {
    "continue_project", "modify_project", "repair_project", "test_project", "audit_project",
}


def route_frame(frame: IntentFrame, objective: str, attachments: Sequence[str] = ()):
    from igris_os.application.mission_router import RoutedAction, _existing_directory_sources

    if frame.needs_clarification:
        return RoutedAction("clarify", payload={"question": frame.clarification_question})

    if frame.mode == "cancel":
        return RoutedAction("cancel", payload={"message": "Operación cancelada."})

    from igris_os.application.mission_router import neural_image_action
    neural = neural_image_action(objective)
    if neural:
        return neural

    if frame.domain == "conversation" and frame.intent in {"chat", "explain"}:
        return RoutedAction("chat")

    # Un frame contradictorio nunca debe borrar una orden operativa ni
    # transformarla en una respuesta conversacional sin ejecutar.
    if frame.intent in {"chat", "explain"}:
        return RoutedAction("clarify", payload={
            "question": (
                "La intención quedó etiquetada como conversación aunque el dominio "
                "indica una tarea. Voy a detener la ruta para evitar una respuesta "
                "que prometa trabajo sin iniciarlo. Reformula la orden concreta."
            )
        })

    if frame.domain == "conversation":
        return RoutedAction("clarify", payload={
            "question": "La intención y el dominio no coinciden. Reformula la petición para poder clasificarla con seguridad."
        })

    if frame.domain == "capability" or frame.intent == "capability_query":
        return RoutedAction("capability", "system.capabilities", {"objective": objective})

    if frame.domain == "programming":
        roots = _existing_directory_sources(objective, attachments)
        from igris_os.application.delivery_request import requested_delivery
        contract = requested_delivery(objective)
        destination = str(contract.get("destination") or "").strip()
        if not roots and str(frame.target or "").strip():
            roots = _existing_directory_sources(str(frame.target), ())

        # La fase de comprensión/inspección es estrictamente de lectura sobre
        # el proyecto. No se promociona a ProgrammingTeam hasta que el usuario
        # pida explícitamente modificar/reparar/continuar.
        if frame.intent == "audit_project" and frame.mode == "inspect":
            if not roots:
                return RoutedAction("clarify", payload={
                    "question": "Necesito la ruta exacta de la carpeta del proyecto para revisarlo sin modificarlo."
                })
            return RoutedAction("capability", "repository.analyze", {
                "root": roots[0], "query": frame.goal or objective,
            }, True)

        payload = {
            "objective": objective,
            "semantic_intent": frame.intent,
            "semantic_goal": frame.goal,
            "requires_existing": frame.intent in _PROGRAMMING_EXISTING,
        }
        if destination:
            destination_path = Path(destination).expanduser()
            destination_key = str(destination_path.resolve()).casefold()
            source_roots = [
                root for root in roots
                if str(Path(root).resolve()).casefold() != destination_key
            ]
            payload["destination"] = destination
            payload["delivery_contract"] = contract
            if destination_path.is_dir():
                # An existing, explicitly named output folder is the project
                # being built/updated. The other supplied folder is reference
                # material; never patch the original game by path order alone.
                payload["root"] = str(destination_path.resolve())
                payload["requires_existing"] = True
            else:
                # New output: start a clean project and expose the original as
                # read-only resources for inspection.
                payload["requires_existing"] = False
            if source_roots:
                payload["resource_roots"] = source_roots[:4]
        elif roots:
            payload["root"] = roots[0]
            payload["requires_existing"] = True
            if len(roots) > 1:
                payload["resource_roots"] = roots[1:5]
        return RoutedAction("capability", "programming.mission", payload, True)

    if frame.domain == "windows_admin":
        if frame.intent == "diagnose_pc":
            return RoutedAction("capability", "host.windows.diagnose", {
                "visible_console": True,
                "semantic_goal": frame.goal,
            })
        if frame.intent == "repair_windows":
            return RoutedAction("capability", "host.windows.repair", {
                "semantic_goal": frame.goal,
            }, True)
        if frame.intent == "optimize_pc":
            # La optimización empieza por evidencia real; la capacidad de
            # diagnóstico no hace cambios y deja el informe para planificar la
            # siguiente acción. Nunca se inventan comandos desde el LLM.
            return RoutedAction("capability", "host.windows.diagnose", {
                "visible_console": True,
                "optimization_requested": True,
                "semantic_goal": frame.goal,
            })

    if frame.domain == "files":
        roots = _existing_directory_sources(objective, attachments)
        if frame.intent == "inspect_files" and roots:
            return RoutedAction("capability", "repository.analyze", {
                "root": roots[0], "query": objective,
            }, True)
        if frame.intent == "open_path" and roots:
            return RoutedAction("capability", "host.open", {"path": roots[0]}, True)

    if frame.domain == "games":
        # Los juegos que requieren desarrollo entran también en el equipo de
        # programación; éste ya soporta Godot y pruebas headless.
        roots = _existing_directory_sources(objective, attachments)
        payload = {
            "objective": objective,
            "semantic_intent": frame.intent,
            "semantic_goal": frame.goal,
            "requires_existing": bool(roots) or frame.continuation,
        }
        if roots:
            payload["root"] = roots[0]
        return RoutedAction("capability", "programming.mission", payload, True)

    if frame.domain == "research":
        # IGRIS no tiene una capacidad web universal en este build. Mantenerlo
        # como conversación evita fingir que investigó sin evidencia.
        return RoutedAction("chat")

    return RoutedAction("clarify", payload={
        "question": frame.clarification_question or
                    "No tengo suficiente contexto para actuar. ¿Qué resultado concreto quieres obtener?"
    })
