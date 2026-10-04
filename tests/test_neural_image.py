import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PyQt6.QtGui import QImage

from igris_os.bootstrap import build_igris
from igris_os.domain import Mission
from igris_os.multimedia.neural_image import NeuralImageRenderer
from igris_os.application.mission_router import MissionRouter, neural_image_action
from igris_os.application.mission_queue import MissionQueue
from igris_os.ui.cinematic import format_result
from igris_os.ui.artifact_viewer import checked_image


class NeuralImageTests(unittest.TestCase):
    def test_preview_rejects_external_changed_and_missing_files(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            result = NeuralImageRenderer(root).render(count=1, width=960, height=540)
            artifact = {**result, 'media_type': 'image/png'}
            path, image = checked_image(artifact, root)
            self.assertFalse(image.isNull())
            with self.assertRaises(ValueError):
                checked_image(artifact, root / 'other_runtime')
            original = path.read_bytes()
            path.write_bytes(original + b'modified')
            with self.assertRaisesRegex(ValueError, 'ha cambiado'):
                checked_image(artifact, root)
            path.unlink()
            with self.assertRaises(OSError):
                checked_image(artifact, root)

    def test_actual_request_routes_to_two_spheres_not_chat(self):
        request = ('ok igris , te puedo pedir que me hagas una imagen visual de una esfera '
                   'de pensamiento neuronal parecido a la que sale en la pelicula iron-man '
                   'de jarvis? en la que sale utron tambien con otra esfera similar')
        action = MissionRouter(use_llm_director=False).route(request)
        self.assertEqual(action.capability, 'image.neural_sphere')
        self.assertEqual(action.payload['count'], 2)
        self.assertTrue(action.requires_confirmation)

    def test_advice_and_unrelated_images_do_not_use_sphere_renderer(self):
        for request in ('Como puedo crear una esfera neuronal?', 'crea una imagen de un gato',
                        'explicame una esfera de pensamiento neuronal'):
            with self.subTest(request=request):
                self.assertIsNone(neural_image_action(request))

    def test_real_png_is_visible_verified_and_inside_workspace(self):
        with TemporaryDirectory() as directory:
            workspace = Path(directory)
            result = NeuralImageRenderer(workspace).render(count=2, width=960, height=540)
            path = Path(result['output'])
            self.assertTrue(path.is_relative_to(workspace))
            image = QImage(str(path))
            self.assertEqual((image.width(), image.height()), (960, 540))
            self.assertGreater(result['visible_sample_fraction'], 0.03)
            self.assertEqual(result['sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertTrue(json.loads(Path(result['report']).read_text())['verified'])
            self.assertIn('no IA generativa', result['method'])

    def test_invalid_limits_do_not_create_outputs(self):
        with TemporaryDirectory() as directory:
            renderer = NeuralImageRenderer(directory)
            for arguments in ({'count': 3}, {'width': 99999}, {'count': True}, {'width': '1920'}):
                with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                    renderer.render(**arguments)
            self.assertFalse((Path(directory) / 'output').exists())

    def test_single_sphere_at_full_resolution_is_not_rejected_by_empty_margins(self):
        with TemporaryDirectory() as directory:
            result = NeuralImageRenderer(directory).render(count=1, width=1920, height=1080)
            self.assertTrue(result['verified'])
            self.assertEqual(result['spheres'], 1)
            self.assertGreater(result['visible_sample_fraction'], 0.03)

    def test_kernel_requires_approval_and_records_real_artifact(self):
        with TemporaryDirectory() as directory:
            kernel = build_igris(Path(directory))
            mission = Mission('Crea una imagen de dos esferas neuronales')
            capability = 'image.neural_sphere'
            payload = {'count': 2, 'width': 960, 'height': 540}
            invalid = kernel.execute(mission, capability, {'count': 2, 'command': 'anything'})
            self.assertEqual(invalid.code, 'CONTRACT_INVALID')
            denied = kernel.execute(mission, capability, payload)
            self.assertEqual(denied.code, 'CONFIRMATION_REQUIRED')
            approval = kernel.issue_approval(mission.objective, capability)
            result = kernel.execute(mission, capability, payload, approval=approval)
            self.assertTrue(result.ok, result.message)
            self.assertTrue(Path(result.data['output']).is_file())
            self.assertTrue(result.data['verified'])
            events = [json.loads(line) for line in kernel.audit.path.read_text(encoding='utf-8').splitlines()]
            self.assertEqual(events[-1]['payload_output']['artifact']['output'], result.data['output'])

    def test_real_result_survives_queue_reload_and_has_clear_delivery(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            kernel = build_igris(root)
            queue = MissionQueue(root / 'queue.json')
            objective = 'Crea una imagen de una esfera neuronal'
            action = neural_image_action(objective)
            action.payload.update(width=960, height=540)
            approval = kernel.issue_approval(objective, action.capability)
            payload = {**action.payload, '__approval': approval}
            queued = queue.enqueue(objective, action.kind, action.capability, payload)
            queue.next()
            result = kernel.execute(Mission(objective, id=queued.id), action.capability, payload, approval=approval)
            self.assertTrue(result.ok, result.message)
            queue.finish(queued.id, result.ok, result.message, result.data)
            recovered = MissionQueue(queue.path).recent()[0]
            self.assertEqual(recovered.state, 'completed')
            self.assertTrue(Path(recovered.result['artifact']['output']).is_file())
            self.assertEqual(recovered.result['artifact']['sha256'], result.data['sha256'])
            display = format_result(recovered.result)
            self.assertIn(result.data['output'], display)
            self.assertIn('no IA generativa', display)
            self.assertIn('Verificado', display)


if __name__ == '__main__':
    unittest.main()