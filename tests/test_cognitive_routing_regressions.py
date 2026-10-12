import tempfile
import unittest
from pathlib import Path

from igris_os.application.intent_classifier import classify_intent
from igris_os.application.delivery_request import requested_delivery
from igris_os.application.mission_router import _existing_directory_sources
from igris_os.cognitive.interpreter import SemanticInterpreter
from igris_os.cognitive.models import IntentFrame
from igris_os.cognitive.router import route_frame


class _EmptyState:
    def context(self):
        return {"active_domain": "", "pending_domain": "", "active_target": ""}


class CognitiveRoutingRegressionTests(unittest.TestCase):
    def setUp(self):
        self.interpreter = SemanticInterpreter(None, _EmptyState())

    def test_build_and_verify_is_not_reduced_to_test_only(self):
        decision = classify_intent(
            "Crea un prototipo jugable de ajedrez y verifica el resultado")
        self.assertEqual((decision.kind, decision.subtype), ("programming", "create"))

    def test_fallback_executes_clear_request_without_semantic_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "Chess Master, original"
            destination = root / "IGRIS Chess Modern"
            source.mkdir()
            destination.mkdir()
            objective = (
                f"Crea un prototipo jugable basado en el juego de origen `{source}`. "
                f"Guárdalo en la carpeta de destino `{destination}` y verifica el resultado. "
                "Mantén las siluetas de las piezas y no modifiques el original."
            )
            frame = self.interpreter._fallback(objective, ["modelo no disponible"])
            action = route_frame(frame, objective)

            self.assertFalse(frame.needs_clarification)
            self.assertEqual(action.capability, "programming.mission")
            self.assertEqual(Path(action.payload["root"]), destination.resolve())
            self.assertEqual(action.payload["resource_roots"], [str(source.resolve())])
            self.assertEqual(action.payload["destination"], str(destination))

    def test_path_complete_order_overrides_chatbot_request_for_more_details(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "Chess Master, original"
            destination = root / "IGRIS Chess Modern"
            source.mkdir()
            destination.mkdir()
            objective = (
                f"Realiza un prototipo de ajedrez basado en el origen `{source}` "
                f"y guárdalo en el destino `{destination}`."
            )
            mislabelled = IntentFrame(
                domain="programming", intent="audit_project", mode="inspect",
                goal="¿Qué estilo gráfico prefieres?", needs_clarification=True,
                clarification_question="Indica las rutas.", confidence=1.0,
            )
            frame = self.interpreter._guard(mislabelled, objective)
            action = route_frame(frame, objective)

            self.assertFalse(frame.needs_clarification)
            self.assertEqual(action.kind, "capability")
            self.assertEqual(action.capability, "programming.mission")
            self.assertEqual(Path(action.payload["root"]), destination.resolve())
            self.assertEqual(action.payload["resource_roots"], [str(source.resolve())])

    def test_plain_paths_from_the_actual_prompt_keep_source_and_destination_roles(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "Chess Master, original"
            destination = root / "IGRIS Chess Modern"
            source.mkdir()
            destination.mkdir()
            objective = (
                f"La carpeta original que debes mantener intacta es:\n{source}\n\n"
                f"Crea el prototipo en esta carpeta:\n{destination}\n\n"
                "Moderniza Chess Master 3D de 1997 y verifica el prototipo."
            )

            self.assertEqual(
                _existing_directory_sources(objective),
                [str(source.resolve()), str(destination.resolve())],
            )
            self.assertEqual(requested_delivery(objective)["destination"], str(destination))
            frame = self.interpreter._fallback(objective, ["modelo no disponible"])
            action = route_frame(frame, objective)
            self.assertEqual(action.capability, "programming.mission")
            self.assertEqual(Path(action.payload["root"]), destination.resolve())
            self.assertEqual(action.payload["resource_roots"], [str(source.resolve())])

    def test_unresolved_command_is_clarified_instead_of_sent_to_chat(self):
        frame = self.interpreter._fallback("Crea algo", ["modelo no disponible"])
        self.assertTrue(frame.needs_clarification)
        self.assertEqual(route_frame(frame, "Crea algo").kind, "clarify")

    def test_actual_conversation_stays_in_chat(self):
        frame = IntentFrame(
            domain="conversation", intent="chat", mode="explain",
            goal="¿Qué tal, IGRIS?", confidence=0.99,
        )
        self.assertEqual(route_frame(frame, frame.goal).kind, "chat")


if __name__ == "__main__":
    unittest.main()
