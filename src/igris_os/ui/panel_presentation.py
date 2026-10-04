from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPixmap, QTextOption
from PyQt6.QtWidgets import QApplication, QComboBox, QLabel, QPushButton


class Portrait(QLabel):
    def __init__(self, art: Path | None, parent):
        super().__init__(parent)
        self.source = QPixmap(str(art)).copy(38, 535, 194, 269) if art else QPixmap()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet('background:transparent;')

    def resizeEvent(self, event):
        if not self.source.isNull():
            self.setPixmap(self.source.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                             Qt.TransformationMode.SmoothTransformation))
        super().resizeEvent(event)


def prepare_presentation(window, parts, art):
    window._original_items = list(window.canvas.items)
    window._original_styles = {widget: widget.styleSheet() for widget, *_ in window._original_items}
    window._original_fonts = {widget: QFont(widget.font()) for widget, *_ in window._original_items}
    window._panel_parts = parts
    window._modern_widgets = []
    mask = QLabel(window.canvas)
    mask.setStyleSheet('background:#060910;')
    window.canvas.place(mask, 0, 0, 274, 900)
    mask.lower()
    parts['background'].lower()
    logo = QLabel(window.canvas)
    if art:
        logo.setPixmap(QPixmap(str(art)).copy(0, 0, 270, 112))
        logo.setScaledContents(True)
    window.canvas.place(logo, 0, 0, 270, 112)
    portrait = Portrait(art, window.canvas)
    window.canvas.place(portrait, 42, 526, 194, 269)
    name = QLabel('IGRIS OS', window.canvas)
    name.setAlignment(Qt.AlignmentFlag.AlignCenter)
    name.setStyleSheet('color:#c0becb;background:transparent;')
    window.canvas.place(name, 42, 804, 194, 20)
    attachments = QLabel(window.canvas)
    attachments.setStyleSheet('color:#bfb0bf;background:transparent;')
    attachments.setWordWrap(True)
    window.canvas.place(attachments, 1010, 618, 550, 34)
    window.attachment_label = attachments
    copy = QPushButton('Copiar', window.canvas)
    copy.setToolTip('Copiar la conversacion actual')
    copy.clicked.connect(lambda: QApplication.clipboard().setText(window.chat.toPlainText()))
    window.canvas.place(copy, 1010, 784, 95, 30)
    profile = QComboBox(window.canvas)
    for label, value in [('Auto', 'auto'), ('Director', 'director'), ('Programador', 'programmer'),
                         ('Revisor', 'reviewer'), ('Investigador', 'researcher')]:
        profile.addItem(label, value)
    profile.setToolTip('Perfil de respuesta; no cambia permisos ni ejecuta tareas por si mismo')
    profile.setCurrentIndex(max(0, profile.findData(window.settings.get('conversation_agent', 'auto'))))
    window.canvas.place(profile, 1120, 784, 190, 30)
    window.agent_choice = profile
    resources = QComboBox(window.canvas)
    for label, value in [('Recursos: Auto', 'auto'), ('Ligero', 'light'), ('Equilibrado', 'balanced'), ('Avanzado', 'advanced')]:
        resources.addItem(label, value)
    resources.setToolTip('Limite de salida del modelo; no aumenta su inteligencia ni su memoria')
    resources.setCurrentIndex(max(0, resources.findData(window.settings.get('resource_mode', 'auto'))))
    window.canvas.place(resources, 1325, 784, 230, 30)
    window.resource_choice = resources
    profile.currentIndexChanged.connect(window.response_preferences_changed)
    resources.currentIndexChanged.connect(window.response_preferences_changed)
    for widget in (copy, profile, resources):
        widget.setStyleSheet('background:#201723;color:#e4d5df;border:1px solid #743046;'
                            'border-radius:4px;padding:3px;')
    window._modern_widgets = [mask, logo, portrait, name, attachments, copy, profile, resources]
    window._modern_items = list(window.canvas.items[len(window._original_items):])


def apply_presentation(window, mode):
    if mode not in {'modern', 'original'}:
        raise ValueError('Panel no valido')
    modern = mode == 'modern'
    for widget in window._modern_widgets:
        widget.setVisible(modern)
    for widget, style in window._original_styles.items():
        widget.setStyleSheet(style)
        widget.setFont(window._original_fonts[widget])
    window.canvas.items = list(window._original_items)
    if modern:
        parts = window._panel_parts
        placements = {
            window.galaxy: (280, 70, 688, 612), parts['frame']: (990, 48, 590, 830),
            parts['header']: (1012, 58, 270, 25), window.clock: (1395, 58, 160, 25),
            window.chat: (1010, 130, 550, 480), window.prompt: (1010, 662, 490, 110),
            parts['send']: (1510, 720, 43, 48), parts['stats']: (290, 725, 675, 128),
            parts['galaxy_button']: (835, 45, 128, 30), window.backend_label: (285, 862, 685, 24),
        }
        for index, button in enumerate((window.voice, window.mic, window.attach, window.clear, window.settings_btn)):
            placements[button] = (1344 + index * 43, 89, 35, 31)
        for index, dial in enumerate(window.dials):
            placements[dial] = (305 + index * 107, 737, 96, 103)
        window.canvas.items = [(widget, *placements.get(widget, (x, y, width, height)))
                               for widget, x, y, width, height in window._original_items]
        window.canvas.items.extend(window._modern_items)
        window.prompt.setStyleSheet('QTextEdit{background:#141521;color:#f0eaf1;border:1px solid #b34e68;'
                                   'border-radius:6px;padding:10px;} QTextEdit:focus{border-color:#e67e99;}')
        window.chat.setStyleSheet('QTextEdit{background:rgba(7,9,16,230);color:#e5e0eb;border:1px solid #542337;'
                                 'border-radius:6px;padding:14px;} QScrollBar:vertical{width:8px;}'
                                 'QScrollBar::handle:vertical{background:#743149;border-radius:3px;}')
        window.chat.setFont(QFont('Segoe UI', 11))
        window.settings_btn.setText('⚙')
        window.settings_btn.setToolTip('Ajustes de IGRIS y seleccion de panel')
    window.prompt.setLineWrapMode(window.prompt.LineWrapMode.WidgetWidth)
    window.prompt.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
    window.prompt.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    window.prompt.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
    window.galaxy.set_orbit_motion(not modern)
    window.galaxy.set_layered_presentation(modern)
    window._panel_mode = mode
    window.canvas.relayout()
    window.canvas.update()