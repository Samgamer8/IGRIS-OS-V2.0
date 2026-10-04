import hashlib
import html
from pathlib import Path
from uuid import uuid4

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QImage, QPixmap, QTextDocument
from PyQt6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QMessageBox,
                             QSizePolicy, QStyle, QToolButton, QVBoxLayout)


class ImagePreview(QDialog):
    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle('Resultado - ' + Path(path).name)
        self.resize(900, 600)
        self.setMinimumSize(420, 320)
        self.source = QPixmap(str(path))
        layout = QVBoxLayout(self)
        self.image = QLabel(self)
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.image.setMinimumSize(200, 120)
        self.image.setStyleSheet('background:#080b0f;')
        layout.addWidget(self.image, 1)
        tools = QHBoxLayout()
        for title, icon, target in (
                ('Abrir imagen', QStyle.StandardPixmap.SP_FileIcon, Path(path)),
                ('Abrir carpeta', QStyle.StandardPixmap.SP_DirOpenIcon, Path(path).parent)):
            button = QToolButton(self)
            button.setIcon(self.style().standardIcon(icon))
            button.setToolTip(title)
            button.clicked.connect(lambda checked=False, target=target: QDesktopServices.openUrl(QUrl.fromLocalFile(str(target))))
            tools.addWidget(button)
        label = QLabel(str(path), self)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        tools.addWidget(label, 1)
        layout.addLayout(tools)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.image.setPixmap(self.source.scaled(self.image.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                               Qt.TransformationMode.SmoothTransformation))


def checked_image(artifact, runtime):
    path = Path(str(artifact.get('output', ''))).resolve(strict=True)
    if not path.is_relative_to(Path(runtime).resolve()) or not path.is_file():
        raise ValueError('El resultado no pertenece a la carpeta de trabajo de IGRIS')
    if artifact.get('verified') is not True or artifact.get('media_type') != 'image/png':
        raise ValueError('La imagen no tiene evidencia de verificacion')
    if path.stat().st_size > 20 * 1024 * 1024:
        raise ValueError('Imagen demasiado grande para la vista previa')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    if digest.hexdigest() != artifact.get('sha256'):
        raise ValueError('La imagen ha cambiado desde la verificacion')
    image = QImage(str(path))
    if image.isNull() or image.width() * image.height() > 16_000_000:
        raise ValueError('No se puede mostrar una imagen valida y acotada')
    return path, image


def append_artifact(window, artifact):
    path, image = checked_image(artifact, window.runtime)
    token = uuid4().hex
    window._artifact_catalog[token] = dict(artifact)
    resource = QUrl('igris-preview://' + token)
    thumbnail = image.scaled(200, 150, Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
    window.chat.document().addResource(QTextDocument.ResourceType.ImageResource, resource, thumbnail)
    window.chat.append(
        '<p><a style="color:#ffd98a" href="igris-result://preview/' + token + '"><img src="' + resource.toString() +
        '" width="' + str(thumbnail.width()) + '" height="' + str(thumbnail.height()) + '" /></a></p>'
        '<p><a style="color:#ffd98a" href="igris-result://preview/' + token + '">Ver imagen</a> | '
        '<a style="color:#ffd98a" href="igris-result://open/' + token + '">Abrir imagen</a> | '
        '<a style="color:#ffd98a" href="igris-result://folder/' + token + '">Abrir carpeta</a><br/>' +
        html.escape(path.name) + '</p>')


def restore_last_artifact(window):
    if window.mission_queue is None:
        return
    for job in reversed(window.mission_queue.recent(1000)):
        artifact = job.result.get('artifact')
        if job.state != 'completed' or not isinstance(artifact, dict) or artifact.get('media_type') != 'image/png':
            continue
        try:
            checked_image(artifact, window.runtime)
        except (ValueError, OSError):
            continue
        window.chat.append('[ULTIMA ENTREGA CONSERVADA] ' + window.render_result(job.result))
        append_artifact(window, artifact)
        return


def open_artifact(window, url):
    if url.scheme() != 'igris-result' or url.host() not in {'preview', 'open', 'folder'}:
        return
    artifact = window._artifact_catalog.get(url.path().lstrip('/'))
    if artifact is None:
        return
    try:
        path, _ = checked_image(artifact, window.runtime)
        if url.host() == 'preview':
            dialog = ImagePreview(path, window)
            window._artifact_previews.append(dialog)
            dialog.destroyed.connect(lambda: window._artifact_previews.remove(dialog)
                                     if dialog in window._artifact_previews else None)
            dialog.show()
        else:
            target = path.parent if url.host() == 'folder' else path
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(target))):
                raise RuntimeError('Windows no pudo abrir el resultado')
    except (ValueError, OSError, RuntimeError) as exc:
        QMessageBox.warning(window, 'Resultado no disponible', str(exc))