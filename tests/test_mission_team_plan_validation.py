import unittest
from unittest.mock import Mock

from igris_os.programming.mission_team import ProgrammingTeam
from igris_os.application.programming_intent import is_improvement_request


class MissionPlanValidationTests(unittest.TestCase):
    def test_creation_of_a_utility_is_not_misrouted_as_an_existing_project_change(self):
        objective = ('Necesito crear un programa profesional que diagnostique el PC, analice hardware '
                     'y controladores y optimice el rendimiento con recomendaciones verificables.')

        self.assertFalse(is_improvement_request(objective))

    def test_explicit_existing_project_optimization_still_requests_a_source(self):
        objective = 'Optimiza este proyecto existente: mejora el panel y conserva sus funciones actuales.'

        self.assertTrue(is_improvement_request(objective))

    def test_new_project_asks_for_location_instead_of_repeating_generic_questions(self):
        objective = ('Necesito crear un programa profesional que diagnostique el PC, analice componentes '
                     'y aplicaciones, revise controladores y ofrezca recomendaciones verificables con panel propio.')
        plan = {'understanding': 'Diagnóstico local con panel y recomendaciones.',
                'steps': ['Inventariar hardware', 'Verificar drivers y crear panel'],
                'questions': ['¿Qué funcionalidades quieres incluir?', '¿Algún requisito adicional?']}

        questions, input_kind = ProgrammingTeam._clarification_gate(
            objective, plan, has_source=False, destination='')
        message = ProgrammingTeam._clarification_message(objective, plan)

        self.assertEqual(input_kind, 'destination')
        self.assertEqual(len(questions), 1)
        self.assertIn('ruta completa', questions[0])
        self.assertIn('He entendido:', message)
        self.assertIn('Plan provisional:', message)
        self.assertIn('inventariar hardware', message)
        self.assertIn('pruebas automatizadas', message)
        self.assertNotIn('→', message)
        self.assertIn('confirmación', message)

    def test_detailed_existing_project_drops_only_redundant_questions(self):
        objective = ('Implementa en este proyecto un panel profesional para diagnosticar componentes, '
                     'controladores y aplicaciones, con pruebas y recomendaciones basadas en fuentes verificables.')
        plan = {'questions': ['¿Qué funcionalidades quieres incluir?', '¿Qué tecnología usar?']}

        questions, input_kind = ProgrammingTeam._clarification_gate(
            objective, plan, has_source=True, destination='')

        self.assertEqual(questions, ['¿Qué tecnología usar?'])
        self.assertEqual(input_kind, '')

    def test_extra_test_agent_files_are_discarded(self):
        acceptance = {'path': 'test_acceptance_sumar.py', 'content': 'from sumar import sumar'}
        implementation = {'path': 'sumar.py', 'content': 'def sumar(a, b): return a + b'}

        selected = ProgrammingTeam._required_test_files(
            [acceptance, implementation], ['test_acceptance_sumar.py'])

        self.assertEqual(selected, [acceptance])

    def test_missing_or_duplicate_acceptance_tests_are_rejected(self):
        acceptance = {'path': 'test_acceptance_sumar.py', 'content': 'assert True'}
        with self.assertRaisesRegex(ValueError, 'no cubren'):
            ProgrammingTeam._required_test_files([], ['test_acceptance_sumar.py'])
        with self.assertRaisesRegex(ValueError, 'duplico'):
            ProgrammingTeam._required_test_files(
                [acceptance, acceptance], ['test_acceptance_sumar.py'])

    def test_machine_verifiable_test_evidence_is_automated(self):
        plan = {
            'understanding': 'Crear sumar y verificar sus pruebas.',
            'questions': [],
            'requirements': [{
                'id': 'evidence',
                'description': 'Ejecutar las pruebas y generar evidencia del resultado.',
                'validation': 'user',
                'test_path': 'test_acceptance_sumar.py',
            }],
        }

        ProgrammingTeam._validate_plan(plan)

        self.assertEqual(plan['requirements'][0]['validation'], 'automated')

    def test_chess_plan_rejects_unrelated_sum_function_requirements(self):
        objective = (
            'Crea un prototipo jugable de ajedrez 3D basado en Chess Master 3D; '
            'conserva las piezas con forma de dragón y verifica sus movimientos.'
        )
        plan = {
            'understanding': 'Modernizar el ajedrez conservando las piezas.',
            'questions': [],
            'requirements': [{
                'id': 'sum',
                'description': 'Crear la función sumar(a, b) y probar positivos, negativos y cero.',
                'validation': 'automated',
                'test_path': 'test_acceptance_sumar.py',
            }],
        }

        with self.assertRaisesRegex(ValueError, 'no corresponden al dominio solicitado'):
            ProgrammingTeam._validate_plan(plan, objective)

    def test_chess_plan_accepts_domain_relevant_requirements(self):
        objective = 'Crea un prototipo de ajedrez 3D y conserva las piezas dragón.'
        plan = {
            'understanding': 'Crear un prototipo jugable de ajedrez 3D.',
            'questions': [],
            'requirements': [{
                'id': 'pieces',
                'description': 'El tablero muestra las piezas y permite moverlas legalmente.',
                'validation': 'automated',
                'test_path': 'test_acceptance_chess.py',
            }],
        }

        ProgrammingTeam._validate_plan(plan, objective)

    def test_off_topic_plan_is_replanned_once_before_mission_waits_for_input(self):
        objective = 'Crea un prototipo jugable de ajedrez 3D.'
        invalid = {
            'understanding': 'Crear un prototipo de ajedrez.',
            'questions': [],
            'requirements': [{
                'id': 'sum',
                'description': 'Crear la función sumar(a, b).',
                'validation': 'automated',
                'test_path': 'test_acceptance_sumar.py',
            }],
        }
        corrected = {
            'understanding': 'Crear un prototipo de ajedrez jugable.',
            'questions': [],
            'requirements': [{
                'id': 'board',
                'description': 'Mostrar el tablero y permitir mover las piezas.',
                'validation': 'automated',
                'test_path': 'test_acceptance_chess.py',
            }],
        }
        team = object.__new__(ProgrammingTeam)
        team._ask = Mock(return_value=corrected)

        result = team._validate_plan_or_repair(
            invalid, objective, request='{}', context='')

        self.assertEqual(result, corrected)
        team._ask.assert_called_once()
        self.assertIn('sumar(a, b)', team._ask.call_args.args[1])

    def test_visual_requirement_still_requires_user_review(self):
        plan = {
            'understanding': 'Crear y revisar la experiencia visual.',
            'questions': [],
            'requirements': [{
                'id': 'visual',
                'description': 'Comprobar visualmente la apariencia del panel.',
                'validation': 'user',
                'test_path': 'test_acceptance_panel.py',
            }],
        }

        ProgrammingTeam._validate_plan(plan)

        self.assertEqual(plan['requirements'][0]['validation'], 'user')


if __name__ == '__main__':
    unittest.main()
