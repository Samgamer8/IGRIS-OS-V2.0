import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import os
from unittest.mock import patch

from igris_os.ui.settings_store import load_settings, save_settings


class PanelModeTests(unittest.TestCase):
    def test_panel_choice_roundtrips_without_changing_engine_configuration(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            settings = load_settings(root)
            settings.update(panel_mode='original', preferred_backend='openai', exclusive_backend=True)
            save_settings(root, settings)
            restored = load_settings(root)
            self.assertEqual(restored['panel_mode'], 'original')
            self.assertEqual(restored['preferred_backend'], 'openai')
            self.assertTrue(restored['exclusive_backend'])
            restored['panel_mode'] = 'modern'
            save_settings(root, restored)
            self.assertEqual(load_settings(root)['panel_mode'], 'modern')

    def test_invalid_choice_falls_back_to_modern(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'settings.json').write_text(json.dumps({'panel_mode': 'unsupported'}), encoding='utf-8')
            self.assertEqual(load_settings(root)['panel_mode'], 'modern')

    def test_native_switch_preserves_content_and_controls(self):
        with patch.dict(os.environ, {'QT_QPA_PLATFORM': 'offscreen', 'IGRIS_TEST_GUI': '1'}):
            from PyQt6.QtCore import QTimer
            from PyQt6.QtWidgets import QApplication, QMessageBox
            from igris_os.application.mission_queue import MissionQueue
            from igris_os.ui.cinematic import run_cinematic_panel
            from igris_os.ui.panel_presentation import apply_presentation

            schedule = QTimer.singleShot
            failures = []

            def verify():
                try:
                    window = next(widget for widget in QApplication.topLevelWidgets()
                                  if hasattr(widget, '_panel_mode'))
                    message = 'Primera linea\nSegunda linea\n' + 'texto' * 140
                    window.prompt.setPlainText(message)
                    window.chat.setPlainText('Conversacion que debe conservarse')
                    window.add_files(['archivo.txt'])
                    self.assertEqual(window.attachment_label.text(), 'archivo.txt')
                    for mode in ('modern', 'original', 'modern'):
                        apply_presentation(window, mode)
                        QApplication.processEvents()
                        self.assertEqual(window.prompt.toPlainText(), message)
                        self.assertEqual(window.chat.toPlainText().splitlines()[0],
                                         'Conversacion que debe conservarse')
                        self.assertEqual(window.galaxy._orbit_motion, mode == 'original')
                        self.assertEqual(window.prompt.horizontalScrollBar().maximum(), 0)
                        if mode == 'original':
                            self.assertEqual(window.canvas.items, window._original_items)
                    with patch('igris_os.ui.settings_store.save_settings') as save:
                        window.agent_choice.setCurrentIndex(window.agent_choice.findData('reviewer'))
                        window.resource_choice.setCurrentIndex(window.resource_choice.findData('light'))
                        self.assertEqual(window.settings['conversation_agent'], 'reviewer')
                        self.assertEqual(window.settings['resource_mode'], 'light')
                        save.assert_called()
                    with TemporaryDirectory() as directory:
                        window.mission_queue = MissionQueue(Path(directory) / 'queue.json')
                        job = window.mission_queue.enqueue('Crea el ajedrez 3D', 'capability', 'programming.mission')
                        window.mission_queue.finish(job.id, False, 'Faltan recursos',
                            {'work_status': 'needs_input', 'questions': ['Que carpeta de piezas uso?']})
                        request = 'ok igris te puedo pedir que me hagas una imagen de una esfera neuronal'

                        def choose(label):
                            def execute(dialog):
                                self.assertTrue(window._deciding_task_switch)
                                self.assertEqual(job.state, 'awaiting_input')
                                dialog._test_choice = next(button for button in dialog.buttons() if button.text() == label)
                                return 0
                            return execute

                        with patch.object(QMessageBox, 'exec', choose('Volver')), \
                                patch.object(QMessageBox, 'clickedButton', lambda dialog: dialog._test_choice):
                            window.prompt.setPlainText(request)
                            self.assertFalse(window._confirm_task_switch(request))
                            self.assertEqual(window.prompt.toPlainText(), request)
                            self.assertEqual(job.state, 'awaiting_input')
                        with patch.object(QMessageBox, 'exec', choose('Continuar pendiente')), \
                                patch.object(QMessageBox, 'clickedButton', lambda dialog: dialog._test_choice):
                            self.assertFalse(window._confirm_task_switch(request))
                            self.assertEqual(window._programming_focus, job.id)
                            self.assertIn('Que carpeta de piezas uso?', window.chat.toPlainText())
                            self.assertEqual(job.state, 'awaiting_input')
                        with patch.object(QMessageBox, 'exec', choose('Dejar pendiente y empezar nuevo')), \
                                patch.object(QMessageBox, 'clickedButton', lambda dialog: dialog._test_choice), \
                                patch.object(window, '_submit_conversation') as conversation, \
                                patch.object(window, 'finish_message') as finished:
                            window.prompt.setPlainText(request)
                            window.submit()
                            self.assertEqual(job.state, 'deferred')
                            self.assertIsNone(window._programming_focus)
                            conversation.assert_not_called()
                            self.assertIn('Servicios inicializando', finished.call_args.args[0])
                        from igris_os.bootstrap import build_igris
                        window.runtime = Path(directory) / 'runtime'
                        window.kernel = build_igris(Path(directory) / 'runtime')
                        with patch.object(window, '_on_plan_ready') as planned, \
                                patch.object(window, '_submit_conversation') as conversation:
                            window.prompt.setPlainText(request)
                            window.submit()
                            self.assertEqual(planned.call_args.kwargs['routed_action'].capability, 'image.neural_sphere')
                            conversation.assert_not_called()
                            plan_call = planned.call_args
                        window.voice_enabled = False
                        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes), \
                                patch.object(window, 'dispatch_next'):
                            window._on_plan_ready(*plan_call.args, **plan_call.kwargs)
                            execution = window.mission_queue.next()
                            self.assertEqual(execution.capability, 'image.neural_sphere')
                            window.active_job = execution
                            window.run_job(execution)
                            from igris_os.cognitive import CognitiveStateStore
                            from igris_os.cognitive.models import IntentFrame
                            window.cognitive_state = CognitiveStateStore(
                                Path(directory) / 'cognitive_state.json')
                            window.cognitive_state.record(
                                request, IntentFrame(
                                    domain='files', intent='inspect_files', mode='inspect',
                                    goal='g', needs_clarification=True,
                                    clarification_question='pendiente?'))
                            window.tick()
                            self.assertEqual(execution.state, 'completed', execution.message + '\n' + str(execution.result))
                            context_after = window.cognitive_state.context()
                            self.assertEqual(context_after['pending_domain'], '',
                                              'finish_message(ok=True) debe limpiar el estado pendiente tras completar la mision')
                            self.assertEqual(context_after['active_domain'], '')
                            self.assertTrue(Path(execution.result['artifact']['output']).is_file())
                            self.assertIn(execution.result['artifact']['output'], window.chat.toPlainText())
                            self.assertIn('no IA generativa', window.chat.toPlainText())
                            self.assertIn('Ver imagen', window.chat.toPlainText())
                            self.assertEqual(len(window._artifact_catalog), 1)
                            from PyQt6.QtCore import QUrl
                            from PyQt6.QtGui import QDesktopServices
                            token = next(iter(window._artifact_catalog))
                            window.chat.anchorClicked.emit(QUrl('igris-result://preview/' + token))
                            self.assertEqual(len(window._artifact_previews), 1)
                            self.assertFalse(window._artifact_previews[0].source.isNull())
                            with patch.object(QDesktopServices, 'openUrl', return_value=True) as opened:
                                window.chat.anchorClicked.emit(QUrl('igris-result://folder/' + token))
                                self.assertEqual(Path(opened.call_args.args[0].toLocalFile()),
                                                 Path(execution.result['artifact']['output']).parent)
                                opened.reset_mock()
                                window.chat.anchorClicked.emit(QUrl('https://example.com'))
                                opened.assert_not_called()
                            window._artifact_previews[0].close()
                            from igris_os.ui.artifact_viewer import restore_last_artifact
                            window.chat.clear()
                            window._artifact_catalog.clear()
                            restore_last_artifact(window)
                            self.assertIn('ULTIMA ENTREGA CONSERVADA', window.chat.toPlainText())
                            self.assertIn('Ver imagen', window.chat.toPlainText())
                            self.assertEqual(len(window._artifact_catalog), 1)

                            # --- "Operacion cancelada" nunca debe ser silencioso ---
                            from igris_os.application.mission_router import RoutedAction
                            cancel_action = RoutedAction('cancel', payload={'message': 'Operación cancelada.'})
                            cancel_frame = IntentFrame(
                                domain='conversation', intent='chat', mode='cancel', goal='g')

                            # Caso A: no hay ninguna tarea activa/pendiente (falso positivo
                            # del interprete semantico) -> no se cancela nada en silencio,
                            # se trata como conversacion normal.
                            self.assertEqual(window.cognitive_state.context()['active_domain'], '')
                            self.assertEqual(window.cognitive_state.context()['pending_domain'], '')
                            with patch.object(window, '_submit_conversation') as conversation, \
                                    patch.object(QMessageBox, 'exec') as dialog_exec:
                                window._handle_cognitive_result('hola, que haces?', cancel_frame, cancel_action)
                                conversation.assert_called_once_with('hola, que haces?')
                                dialog_exec.assert_not_called()

                            # Caso B: hay una tarea activa -> debe preguntar, nunca cancelar solo.
                            window.cognitive_state.record(
                                'crea un proyecto de ajedrez', IntentFrame(
                                    domain='programming', intent='create_project', mode='execute',
                                    goal='crear el ajedrez 3D'))
                            self.assertEqual(window.cognitive_state.context()['active_domain'], 'programming')

                            def click(label):
                                def execute(dialog_self):
                                    button = next(b for b in dialog_self.buttons() if b.text() == label)
                                    dialog_self._test_choice = button
                                    return 0
                                return execute

                            with patch.object(QMessageBox, 'exec', click('Anular la tarea')), \
                                    patch.object(QMessageBox, 'clickedButton', lambda d: d._test_choice):
                                window._handle_cognitive_result('olvida eso', cancel_frame, cancel_action)
                                self.assertIn('Operación cancelada.', window.chat.toPlainText())
                                self.assertEqual(window.cognitive_state.context()['active_domain'], '')

                            window.chat.clear()
                            window.cognitive_state.record(
                                'crea un proyecto de ajedrez', IntentFrame(
                                    domain='programming', intent='create_project', mode='execute',
                                    goal='crear el ajedrez 3D'))
                            with patch.object(QMessageBox, 'exec', click('Pausarla (seguir después)')), \
                                    patch.object(QMessageBox, 'clickedButton', lambda d: d._test_choice):
                                window._handle_cognitive_result('cuales son tus funciones', cancel_frame, cancel_action)
                                self.assertIn('en pausa, sin cambios', window.chat.toPlainText())
                                # El contexto activo se conserva: no se pierde la tarea.
                                self.assertEqual(window.cognitive_state.context()['active_domain'], 'programming')

                            window.chat.clear()
                            with patch.object(QMessageBox, 'exec', click('Pausarla y empezar nueva')), \
                                    patch.object(QMessageBox, 'clickedButton', lambda d: d._test_choice), \
                                    patch.object(QTimer, 'singleShot', side_effect=lambda ms, cb: cb()), \
                                    patch.object(window, 'submit') as resubmit:
                                window._handle_cognitive_result('cuales son tus funciones', cancel_frame, cancel_action)
                                self.assertIn('Tarea anterior pausada', window.chat.toPlainText())
                                self.assertEqual(window.cognitive_state.context()['active_domain'], '')
                                self.assertEqual(window.prompt.toPlainText(), 'cuales son tus funciones')
                                resubmit.assert_called_once()
                except Exception as exc:
                    failures.append(exc)
                finally:
                    QApplication.instance().quit()

            def single_shot(milliseconds, callback):
                name = getattr(callback, '__name__', '')
                if name in {'_init_services', '_probe_server'}:
                    return None
                return schedule(milliseconds, verify if name == 'finish_test' else callback)

            with patch.object(QTimer, 'singleShot', side_effect=single_shot):
                self.assertEqual(run_cinematic_panel(), 0)
            if failures:
                raise failures[0]


if __name__ == '__main__':
    unittest.main()