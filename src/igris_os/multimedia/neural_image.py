import hashlib
import json
import math
from pathlib import Path
from uuid import uuid4

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QRadialGradient


class NeuralImageRenderer:
    def __init__(self, workspace):
        self.workspace = Path(workspace).resolve()

    @staticmethod
    def _point(center, radius, angle, tilt, rotation):
        horizontal = radius * math.cos(angle)
        vertical = radius * math.sin(angle) * math.cos(tilt)
        depth = radius * math.sin(angle) * math.sin(tilt)
        return QPointF(center.x() + horizontal * math.cos(rotation) - vertical * math.sin(rotation),
                       center.y() + horizontal * math.sin(rotation) + vertical * math.cos(rotation)), depth

    @staticmethod
    def _glow(painter, center, radius, color, opacity):
        gradient = QRadialGradient(center, radius)
        bright = QColor(color)
        bright.setAlpha(opacity)
        gradient.setColorAt(0, bright)
        soft = QColor(color)
        soft.setAlpha(opacity // 5)
        gradient.setColorAt(0.35, soft)
        soft.setAlpha(0)
        gradient.setColorAt(1, soft)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawEllipse(center, radius, radius)

    def render(self, *, count=2, width=1920, height=1080):
        for value in (count, width, height):
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError('Los parametros deben ser enteros')
        if count not in {1, 2} or not 640 <= width <= 2560 or not 480 <= height <= 1440:
            raise ValueError('Resolucion o numero de esferas fuera de limites')
        if width < height or width * height > 3_686_400:
            raise ValueError('Se requiere un formato horizontal acotado')
        output = self.workspace / 'output'
        if not output.resolve().is_relative_to(self.workspace):
            raise ValueError('La salida no puede salir de la mision')
        output.mkdir(parents=True, exist_ok=True)
        destination = output / ('esfera_neuronal_' + uuid4().hex[:12] + '.png')
        image = QImage(width, height, QImage.Format.Format_ARGB32)
        image.fill(QColor('#080b0f'))
        painter = QPainter(image)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            radius = min(height * 0.35, width / (count * 2.65))
            centers = [QPointF(width * (index + 0.5) / count, height * 0.5) for index in range(count)]
            for index, center in enumerate(centers):
                color = QColor('#ffc35d' if index == 0 else '#64d7df')
                self._glow(painter, center, radius * 1.35, color, 30)
                nodes = []
                painter.setBrush(Qt.BrushStyle.NoBrush)
                for ring in range(15):
                    tilt = 0.34 + ring * 0.17
                    rotation = ring * 0.63
                    ring_radius = radius * (0.88 + (ring % 4) * 0.04)
                    path = QPainterPath()
                    for step in range(181):
                        point, depth = self._point(center, ring_radius, math.tau * step / 180, tilt, rotation)
                        if step == 0:
                            path.moveTo(point)
                        else:
                            path.lineTo(point)
                    ring_color = QColor(color)
                    ring_color.setAlpha(75 + ring % 4 * 20)
                    painter.setPen(QPen(ring_color, max(0.8, width / 1920)))
                    painter.drawPath(path)
                    for position in range(6):
                        angle = math.tau * position / 6 + ring * 0.29
                        point, depth = self._point(center, ring_radius, angle, tilt, rotation)
                        nodes.append((point, depth))
                for node_index, (point, depth) in enumerate(nodes):
                    target, _ = nodes[(node_index + 17) % len(nodes)]
                    path = QPainterPath(point)
                    bend = QPointF(center.x() + (point.x() - center.x()) * 0.26,
                                   center.y() + (target.y() - center.y()) * 0.26)
                    path.quadTo(bend, target)
                    branch = QColor(color)
                    branch.setAlpha(35 if depth < 0 else 90)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.setPen(QPen(branch, max(0.7, width / 2200)))
                    painter.drawPath(path)
                    self._glow(painter, point, max(4, radius * 0.019), color, 120)
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QColor('#fff0bd' if index == 0 else '#d1ffff'))
                    node_radius = max(1.1, radius * 0.0045)
                    painter.drawEllipse(point, node_radius, node_radius)
                self._glow(painter, center, radius * 0.21, color, 160)
                self._glow(painter, center, radius * 0.045, QColor('#fff8e5'), 230)
        finally:
            painter.end()
        temporary = destination.with_suffix('.pending')
        try:
            if not image.save(str(temporary), 'PNG'):
                raise RuntimeError('No se pudo escribir el PNG')
            reloaded = QImage(str(temporary))
            if reloaded.isNull() or (reloaded.width(), reloaded.height()) != (width, height):
                raise RuntimeError('La imagen no supera la comprobacion de formato y dimensiones')
            visible = 0
            total = 0
            for center in centers:
                region_visible = 0
                region_total = 0
                for sample_y in range(60):
                    for sample_x in range(60):
                        pos_x = int(center.x() - radius * 1.15 + radius * 2.3 * sample_x / 59)
                        pos_y = int(center.y() - radius * 1.15 + radius * 2.3 * sample_y / 59)
                        color = reloaded.pixelColor(pos_x, pos_y)
                        region_total += 1
                        region_visible += int(max(color.red(), color.green(), color.blue()) > 45)
                if region_visible / region_total < 0.03:
                    raise RuntimeError('Una esfera esta vacia o carece de contenido visible')
                visible += region_visible
                total += region_total
            digest = hashlib.sha256(temporary.read_bytes()).hexdigest()
            temporary.replace(destination)
            report = destination.with_suffix('.json')
            evidence = {'verified': True, 'output': str(destination), 'sha256': digest,
                        'width': width, 'height': height, 'spheres': count,
                        'visible_sample_fraction': round(visible / total, 4),
                        'sampling_scope': 'Region de cada esfera; el margen vacio no cuenta como fallo',
                        'method': 'Dibujo programatico local con Qt; no IA generativa',
                        'verification_scope': 'Formato, dimensiones, contenido visible e integridad; no evaluacion artistica'}
            report.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
            return {**evidence, 'report': str(report)}
        except Exception:
            temporary.unlink(missing_ok=True)
            destination.unlink(missing_ok=True)
            raise