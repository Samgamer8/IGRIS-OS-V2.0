from pathlib import Path
import unittest

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QColor, QImage, QPainter

from igris_os.ui.neural_layers import NeuralLayers


class NeuralLayersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.renderer = NeuralLayers(Path(__file__).resolve().parents[1] / 'assets/igris_neural_layers.jpg')

    def test_real_reference_has_six_cached_transparent_layers(self):
        self.assertEqual(len(self.renderer.images), 6)
        for image in self.renderer.images:
            self.assertEqual((image.width(), image.height()), (512, 512))
            self.assertEqual(image.pixelColor(0, 0).alpha(), 0)

    def test_layers_move_without_any_activity_points_and_stay_inside(self):
        frames = []
        for seconds in (0, 3, 19):
            image = QImage(640, 520, QImage.Format.Format_ARGB32)
            image.fill(QColor('#060910'))
            painter = QPainter(image)
            self.renderer.draw(painter, QRectF(0, 0, 640, 520), seconds)
            painter.end()
            frames.append(image.constBits().asstring(image.sizeInBytes()))
            for pos_x in range(image.width()):
                self.assertEqual(image.pixelColor(pos_x, 0), QColor('#060910'))
                self.assertEqual(image.pixelColor(pos_x, image.height() - 1), QColor('#060910'))
        changed = sum(abs(first - second) > 8 for first, second in zip(frames[0], frames[1]))
        self.assertGreater(changed, 640 * 520 * 0.01)
        for index in range(6):
            self.assertGreater(abs(self.renderer.pose(index, 3)['angle'] - self.renderer.pose(index, 0)['angle']), 2)


if __name__ == '__main__':
    unittest.main()