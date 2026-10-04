import math

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QImage, QPainter, QPainterPath


class NeuralLayers:
    SCALES = (2.58, 2.54, 2.35, 1.45, 2.62, 2.7)
    OPACITIES = (0.62, 0.44, 0.28, 0.72, 0.33, 0.82)
    SPEEDS = (0.035, -0.07, 0.11, -0.025, 0.06, -0.085)

    def __init__(self, reference):
        source = QImage(str(reference))
        if source.isNull():
            raise ValueError('Falta la imagen de las capas neuronales aprobadas')
        self.images = []
        tile_width = source.width() // 2
        tile_height = source.height() // 3
        for index in range(6):
            image = source.copy(index % 2 * tile_width + 4, index // 2 * tile_height + 4,
                                tile_width - 8, tile_height - 8).scaled(512, 512)
            image = image.convertToFormat(QImage.Format.Format_RGBA8888)
            pixels = bytearray(image.constBits().asstring(image.sizeInBytes()))
            for offset in range(0, len(pixels), 4):
                strength = max(pixels[offset:offset + 3]) / 255
                pixels[offset] = int(22 + strength * 25)
                pixels[offset + 1] = int(168 + strength * 52)
                pixels[offset + 2] = int(215 + strength * 40)
                pixels[offset + 3] = (0 if strength <= 0.06 else
                                      int(((strength - 0.06) / 0.94) ** 0.8 * 245))
            prepared = QImage(bytes(pixels), 512, 512, 512 * 4, QImage.Format.Format_RGBA8888).copy()
            self.images.append(prepared.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied))

    @classmethod
    def pose(cls, index, seconds, activity=0.04):
        amplitude = 0.055 if index == 3 else 0.016 if index == 5 else 0.025
        return {
            'angle': math.degrees(seconds * cls.SPEEDS[index] + index * 0.035),
            'tilt_x': math.sin(seconds * 0.28 + index * 0.7) * (0.08 if index == 3 else 0.14),
            'tilt_y': math.cos(seconds * 0.23 + index * 0.8) * 0.12,
            'depth': (index - 2.5) * 0.055 + math.sin(seconds * 0.6 + index) * 0.045,
            'scale': 1 + math.sin(seconds * 1.25 + index * 0.6) * (amplitude + activity * 0.012),
            'opacity': cls.OPACITIES[index] * (0.91 + math.sin(seconds * 1.25 - index * 0.5) * (0.08 + activity * 0.1)),
        }

    def draw(self, painter, bounds, seconds, activity=0.04):
        painter.save()
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        for index, image in enumerate(self.images):
            pose = self.pose(index, seconds, activity)
            diameter = min(bounds.width(), bounds.height()) * 0.78 * self.SCALES[index] / 2.7
            diameter *= pose['scale'] * 5 / (5 - pose['depth'])
            painter.save()
            painter.translate(bounds.center())
            painter.rotate(pose['angle'])
            painter.shear(math.sin(pose['tilt_y']) * 0.08, math.sin(pose['tilt_x']) * 0.08)
            painter.scale(math.cos(pose['tilt_y']), math.cos(pose['tilt_x']))
            painter.setOpacity(pose['opacity'])
            target = QRectF(-diameter / 2, -diameter / 2, diameter, diameter)
            clip = QPainterPath()
            clip.addEllipse(target)
            painter.setClipPath(clip)
            painter.drawImage(target, image)
            painter.restore()
        painter.restore()