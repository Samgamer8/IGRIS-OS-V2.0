from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from pathlib import Path
from tempfile import TemporaryDirectory

from igris_os.application.programming_followup import programming_followup
from igris_os.application.mission_followup import task_switch_question
from igris_os.application.mission_queue import MissionQueue


class ProgrammingFollowupTests(unittest.TestCase):
    def test_new_image_request_asks_before_switching_and_preserves_queue(self):
        with TemporaryDirectory() as directory:
            queue = MissionQueue(Path(directory) / 'queue.json')
            job = queue.enqueue('Crea un juego de ajedrez 3D', 'capability', 'programming.mission')
            queue.finish(job.id, False, 'Falta una respuesta', {'work_status': 'needs_input', 'questions': ['Que recursos?']})
            request = ('ok igris te puedo pedir que me hagas una imagen visual de una esfera '
                       'de pensamiento neuronal como jarvis y utron')
            question = task_switch_question(request, queue)
            self.assertEqual(question.job.id, job.id)
            self.assertIn('dejarlo pendiente', question.message)
            self.assertEqual(job.state, 'awaiting_input')
            queue.defer(job.id)
            restored = MissionQueue(queue.path)
            self.assertEqual(restored.recent()[0].state, 'deferred')
            self.assertIsNone(restored.next())
            self.assertIsNone(programming_followup('si', restored, active_job_id=None))
            recovered = restored.restore_deferred(job.id)
            self.assertEqual(recovered.state, 'awaiting_input')
            self.assertEqual(recovered.result['questions'], ['Que recursos?'])

    def test_greeting_closure_and_same_project_do_not_request_a_switch(self):
        with TemporaryDirectory() as directory:
            queue = MissionQueue(Path(directory) / 'queue.json')
            queue.enqueue('Crea un juego de ajedrez 3D', 'capability', 'programming.mission')
            for text in ('hola igris', 'solo eso de momento', 'reanuda',
                         'quiero que crees la carpeta ajedrez 3D en el escritorio'):
                with self.subTest(text=text):
                    self.assertIsNone(task_switch_question(text, queue))

    def test_running_job_cannot_be_falsely_paused(self):
        with TemporaryDirectory() as directory:
            queue = MissionQueue(Path(directory) / 'queue.json')
            job = queue.enqueue('Crea el ajedrez', 'capability', 'programming.mission')
            queue.next()
            with self.assertRaises(ValueError):
                queue.defer(job.id)
            self.assertEqual(job.state, 'running')

    def test_named_resume_recovers_deferred_question_despite_a_later_project(self):
        with TemporaryDirectory() as directory:
            queue = MissionQueue(Path(directory) / 'queue.json')
            job = queue.enqueue('Crea el ajedrez 3D', 'capability', 'programming.mission')
            queue.finish(job.id, False, 'Falta una respuesta',
                         {'work_status': 'needs_input', 'questions': ['Que carpeta de piezas?']})
            queue.defer(job.id)
            later = queue.enqueue('Crea una calculadora', 'capability', 'programming.mission')
            queue.finish(later.id, True, 'Finalizada')
            answer = programming_followup('reanuda ' + job.id, queue, active_job_id=None)
            self.assertEqual(answer.job.id, job.id)
            self.assertEqual(answer.mode, 'questions')
            self.assertFalse(answer.ready)
            self.assertEqual(answer.payload, {})
            self.assertEqual(job.state, 'awaiting_input')
            self.assertIn('Que carpeta de piezas?', answer.message)

    def setUp(self):
        self.job = SimpleNamespace(
            id='67bfc7b3f27645fc912fdf91ea0b76d4',
            capability='programming.mission',
            state='failed',
            objective='Instala las extensiones necesarias en VS Code',
            payload={'objective': 'Instala las extensiones necesarias en VS Code'},
            result={'work_status': 'blocked', 'report': 'mission_progress.json'},
            message='El programador repite la misma accion sin avanzar')
        self.queue = Mock()
        self.queue.recent.return_value = [self.job]

    def test_voice_request_does_not_resume_failed_installation(self):
        text = ('necesito que busque un archivo que se llama assets que sta en esta '
                'uvicacion:assets y uses el archivo: igris_voice_identity.wav y lo '
                'utilices para sacarle el audio y crear tu propia voz')
        self.assertIsNone(programming_followup(text, self.queue))

    def test_unrelated_statement_does_not_resume_failed_mission(self):
        self.assertIsNone(programming_followup('necesito organizar mis archivos', self.queue))

    def test_conversation_closure_never_resumes_old_programming(self):
        for state in ('failed', 'awaiting_input', 'awaiting_review', 'awaiting_downloads'):
            self.job.state = state
            with self.subTest(state=state):
                self.assertIsNone(programming_followup('solo eso de momento', self.queue))

    def test_explicit_retry_keeps_original_objective_and_checkpoint(self):
        answer = programming_followup('reintenta', self.queue)
        self.assertIsNotNone(answer)
        self.assertTrue(answer.ready)
        self.assertIs(answer.job, self.job)
        self.assertEqual(answer.payload['objective'], self.job.objective)
        self.assertEqual(answer.payload['resume_report'], self.job.result['report'])

    def test_confirmation_still_continues_failed_mission(self):
        answer = programming_followup('si', self.queue)
        self.assertIsNotNone(answer)
        self.assertEqual(answer.payload['continuation_of'], self.job.id)

    def test_unfocused_confirmation_cannot_resume_historical_job(self):
        self.assertIsNone(programming_followup('si', self.queue, active_job_id=None))

    def test_pending_question_still_accepts_an_answer(self):
        self.job.state = 'awaiting_input'
        self.job.result = {'questions': ['Que nombre debe tener el proyecto?']}
        answer = programming_followup('Mi herramienta', self.queue)
        self.assertIsNotNone(answer)
        self.assertEqual(answer.payload['clarifications'][-1]['answer'], 'Mi herramienta')

    def test_destination_answer_routes_new_folder_as_delivery_target(self):
        self.job.state = 'awaiting_input'
        self.job.objective = 'Crear un optimizador de PC con panel y análisis de controladores'
        self.job.payload = {'objective': self.job.objective}
        self.job.result = {'work_status': 'needs_input', 'input_kind': 'destination',
                           'questions': ['¿Dónde creo el programa?'],
                           'report': 'C:/runtime/missions/job/output/mission_progress.json'}
        with TemporaryDirectory() as directory:
            target = Path(directory) / 'IgrisOptimizer'

            answer = programming_followup(str(target), self.queue)

        self.assertTrue(answer.ready)
        self.assertEqual(answer.payload['destination'], str(target))
        self.assertEqual(answer.payload['resume_report'], self.job.result['report'])
        self.assertEqual(answer.payload['clarifications'][-1]['answer'], str(target))

    def test_destination_answer_routes_existing_project_as_source(self):
        self.job.state = 'awaiting_input'
        self.job.objective = 'Crear un programa nuevo con panel'
        self.job.payload = {'objective': self.job.objective}
        self.job.result = {'work_status': 'needs_input', 'input_kind': 'destination',
                           'questions': ['¿Dónde creo el programa?'],
                           'report': 'C:/runtime/missions/job/output/mission_progress.json'}
        with TemporaryDirectory() as directory:
            answer = programming_followup(directory, self.queue)

        self.assertTrue(answer.ready)
        self.assertEqual(answer.payload['root'], str(Path(directory).resolve()))
        self.assertTrue(answer.payload['requires_existing'])
        self.assertNotIn('resume_report', answer.payload)

    def test_unfocused_path_reconnects_to_the_only_pending_destination_question(self):
        self.job.state = 'awaiting_input'
        self.job.objective = 'Moderniza Chess Master 3D en el destino indicado'
        self.job.payload = {'objective': self.job.objective}
        self.job.result = {'work_status': 'needs_input', 'input_kind': 'destination',
                           'questions': ['¿Dónde creo el programa?']}
        with TemporaryDirectory() as directory:
            answer = programming_followup(directory, self.queue, active_job_id=None)

        self.assertIsNotNone(answer)
        self.assertTrue(answer.ready)
        self.assertIs(answer.job, self.job)
        self.assertEqual(answer.payload['root'], str(Path(directory).resolve()))

    def test_unfocused_path_does_not_guess_between_pending_missions(self):
        first = SimpleNamespace(
            id='first0000000000000000000000000', capability='programming.mission',
            state='awaiting_input', objective='Crear un juego', payload={},
            result={'input_kind': 'destination', 'questions': ['¿Dónde?']}, message='')
        second = SimpleNamespace(
            id='second000000000000000000000000', capability='programming.mission',
            state='awaiting_input', objective='Crear una web', payload={},
            result={'input_kind': 'project_path', 'questions': ['¿Qué carpeta?']}, message='')
        self.queue.recent.return_value = [first, second]

        answer = programming_followup(r'C:\Users\samva\Desktop\Proyecto',
                                      self.queue, active_job_id=None)

        self.assertIsNotNone(answer)
        self.assertFalse(answer.ready)
        self.assertIn(first.id[:8], answer.message)
        self.assertIn(second.id[:8], answer.message)

    def test_destination_answer_preserves_other_supplied_folder_as_reference(self):
        self.job.state = 'awaiting_input'
        with TemporaryDirectory() as directory:
            source = Path(directory) / 'Chess Master, original'
            destination = Path(directory) / 'IGRIS Chess Modern'
            source.mkdir()
            destination.mkdir()
            self.job.objective = (
                f'La carpeta original que debes mantener intacta es:\n{source}\n'
                f'Crea el prototipo en esta carpeta:\n{destination}'
            )
            self.job.payload = {'objective': self.job.objective}
            self.job.result = {
                'work_status': 'needs_input', 'input_kind': 'destination',
                'questions': ['¿Dónde creo el programa?'],
                'report': 'C:/runtime/missions/job/output/mission_progress.json',
            }

            answer = programming_followup(str(destination), self.queue)

        self.assertTrue(answer.ready)
        self.assertEqual(answer.payload['root'], str(destination.resolve()))
        self.assertEqual(answer.payload['resource_roots'], [str(source.resolve())])
        self.assertEqual(answer.payload['clarifications'][-1]['answer'], str(destination))

    def test_destination_answer_rejects_missing_parent(self):
        self.job.state = 'awaiting_input'
        self.job.result = {'work_status': 'needs_input', 'input_kind': 'destination',
                           'questions': ['¿Dónde creo el programa?']}
        with TemporaryDirectory() as directory:
            target = Path(directory) / 'missing' / 'project'

            answer = programming_followup(str(target), self.queue)

        self.assertFalse(answer.ready)
        self.assertIn('directorio padre ya exista', answer.message)


if __name__ == '__main__':
    unittest.main()
