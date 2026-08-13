import os
from pathlib import Path
import queue
import sys
import threading

from igris_os.application import AssistantService, MissionDirector, MissionRouter
from igris_os.bootstrap import build_igris
from igris_os.domain import Mission
from igris_os.memory import MemoryStore
from igris_os.ui.galaxia import GalaxiaWidget
from igris_os.voice import WindowsVoice


def asset_path(name):
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[3]))
    path = base / "assets" / name
    return path if path.is_file() else None


def run_cinematic_panel():
    from PyQt6.QtCore import Qt, QTimer, QRectF
    from PyQt6.QtGui import (
        QBrush, QColor, QFont, QIcon, QLinearGradient, QPainter, QPen,
        QPixmap, QRadialGradient,
    )
    from PyQt6.QtWidgets import (
        QApplication, QFileDialog, QFrame, QLabel, QMainWindow, QMessageBox,
        QPushButton, QTextEdit, QWidget,
    )

    class PromptEdit(QTextEdit):
        def keyPressEvent(self, event):
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    return super().keyPressEvent(event)
                self.parent().window().submit()
                return
            super().keyPressEvent(event)

    class Dial(QWidget):
        def __init__(self, title, value, color, unit="%", parent=None):
            super().__init__(parent)
            self.title, self.value, self.color, self.unit = (
                title, value, QColor(color), unit)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        def set_value(self, value):
            self.value = max(0, min(100, int(value)))
            self.update()

        def paintEvent(self, event):
            del event
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            d = min(self.width() - 8, self.height() - 22)
            x, y = (self.width() - d) / 2, 1
            rim = QLinearGradient(x, y, x + d, y + d)
            rim.setColorAt(0, self.color.lighter(180))
            rim.setColorAt(.5, self.color)
            rim.setColorAt(1, self.color.darker(220))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(rim))
            p.drawEllipse(QRectF(x, y, d, d))
            face = QRadialGradient(x + d / 2, y + d / 2, d / 2)
            face.setColorAt(0, QColor("#303440"))
            face.setColorAt(1, QColor("#050609"))
            p.setBrush(QBrush(face))
            p.drawEllipse(QRectF(x + 6, y + 6, d - 12, d - 12))
            track = QRectF(x + 11, y + 11, d - 22, d - 22)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor("#1c1d24"), 8))
            p.drawArc(track, 0, 360 * 16)
            p.setPen(QPen(self.color, 6))
            p.drawArc(track, 90 * 16, -int(360 * 16 * self.value / 100))
            p.setFont(QFont("Consolas", max(9, int(d / 4.5)), QFont.Weight.Bold))
            p.setPen(QColor("#f7f7fa"))
            p.drawText(QRectF(x, y, d, d), Qt.AlignmentFlag.AlignCenter,
                       f"{self.value}{self.unit}")
            p.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
            p.setPen(QColor("#c9cbd3"))
            p.drawText(QRectF(0, y + d, self.width(), 20),
                       Qt.AlignmentFlag.AlignCenter, self.title)

    class Canvas(QWidget):
        BASE_W, BASE_H = 1600, 900

        def __init__(self):
            super().__init__()
            self.items = []
            self.file_receiver = None

        def place(self, widget, x, y, w, h):
            self.items.append((widget, x, y, w, h))
            widget.setGeometry(x, y, w, h)
            return widget

        def resizeEvent(self, event):
            sx, sy = self.width() / self.BASE_W, self.height() / self.BASE_H
            for widget, x, y, w, h in self.items:
                widget.setGeometry(round(x * sx), round(y * sy),
                                   round(w * sx), round(h * sy))
            super().resizeEvent(event)

        def dragEnterEvent(self, event):
            if event.mimeData().hasUrls():
                event.acceptProposedAction()

        def dropEvent(self, event):
            if self.file_receiver:
                paths = [url.toLocalFile() for url in event.mimeData().urls()
                         if url.toLocalFile()]
                self.file_receiver(paths)
            event.acceptProposedAction()

    class Panel(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("IGRIS OS — Modo Militar")
            # Arranque cómodo en pantallas 1080p; el lienzo conserva su
            # proporción y puede ampliarse manualmente cuando se necesite.
            self.resize(1440, 810)
            self.setMinimumSize(1100, 619)
            icon = asset_path("igris_icon_v2.ico")
            if icon:
                self.setWindowIcon(QIcon(str(icon)))
            self.assistant = AssistantService()
            self.director = MissionDirector()
            self.router = MissionRouter()
            self.kernel = build_igris()
            self.memory = MemoryStore(Path("runtime") / "memory" / "chat.db")
            self.voice_engine = WindowsVoice()
            self.voice_enabled = True
            self.voice_inputs = queue.Queue()
            self.replies = queue.Queue()
            self.command_count = 0
            self.attachments = []
            self.canvas = Canvas()
            self.setCentralWidget(self.canvas)
            self.canvas.setAcceptDrops(True)
            self.canvas.file_receiver = self.add_files
            self.build_visuals(
                QFrame, QLabel, QPushButton, QTextEdit, PromptEdit, Dial,
                QFont, QPixmap, Qt)
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.tick)
            self.timer.start(100)
            self.metrics_timer = QTimer(self)
            self.metrics_timer.timeout.connect(self.update_metrics)
            self.metrics_timer.start(1500)

        def build_visuals(self, QFrame, QLabel, QPushButton, QTextEdit,
                          PromptEdit, Dial, QFont, QPixmap, Qt):
            bg = QLabel(self.canvas)
            art = asset_path("igris_window_art_only_1600.png")
            if art:
                bg.setPixmap(QPixmap(str(art)))
                bg.setScaledContents(True)
            bg.setStyleSheet("background:#030307;")
            self.canvas.place(bg, 0, 0, 1600, 900)
            bg.lower()

            self.galaxy = GalaxiaWidget(self.canvas)
            self.galaxy.setStyleSheet("background:transparent;")
            self.canvas.place(self.galaxy, 285, 65, 730, 605)

            chat_frame = QFrame(self.canvas)
            chat_frame.setStyleSheet(
                "QFrame{background:rgba(4,5,10,232);border:1px solid "
                "rgba(209,17,36,175);border-radius:18px;}")
            self.canvas.place(chat_frame, 1078, 48, 500, 830)

            self.chat = QTextEdit(self.canvas)
            self.chat.setReadOnly(True)
            self.chat.setFont(QFont("Consolas", 11))
            self.chat.setStyleSheet(
                "QTextEdit{background:rgba(4,5,10,180);color:#e8e8ec;"
                "border:1px solid rgba(209,17,36,150);border-radius:15px;"
                "padding:18px;} QScrollBar:vertical{width:8px;background:transparent;}"
                "QScrollBar::handle:vertical{background:#65101e;border-radius:4px;}")
            self.chat.setPlainText(
                "[IGRIS] IGRIS OS V2.O en linea.\nA tus ordenes.\n\n"
                "[SISTEMA] Escribe una orden. Shift+Enter crea otra linea.")
            self.canvas.place(self.chat, 1110, 120, 435, 610)

            self.prompt = PromptEdit(self.canvas)
            self.prompt.setFont(QFont("Consolas", 13))
            self.prompt.setPlaceholderText("Escribe una orden...")
            self.prompt.setStyleSheet(
                "QTextEdit{background:#11131a;color:#f2f2f5;"
                "border:2px solid #a7152d;border-radius:17px;padding:16px;}"
                "QTextEdit:focus{border-color:#ef2444;}")
            self.canvas.place(self.prompt, 1100, 770, 390, 72)

            send = QPushButton("›", self.canvas)
            send.setFont(QFont("Consolas", 26, QFont.Weight.Bold))
            send.clicked.connect(self.submit)
            send.setStyleSheet(
                "QPushButton{background:#760518;color:white;border:none;"
                "border-radius:10px;} QPushButton:hover{background:#b20d2b;}")
            self.canvas.place(send, 1500, 770, 48, 72)

            self.status = QLabel("● Estado: Operativo", self.canvas)
            self.status.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            self.status.setStyleSheet("color:#55dc76;background:transparent;")
            self.canvas.place(self.status, 48, 847, 230, 30)

            invisible = (
                "QPushButton{background:transparent;color:transparent;border:none;}"
                "QPushButton:hover{background:rgba(209,17,36,35);"
                "border:1px solid rgba(255,70,86,90);border-radius:10px;}")
            menu = (
                ("Modo Militar", 152, self.show_military),
                ("Laboratorio", 234, self.show_laboratory),
                ("Academia", 318, self.show_academy),
                ("Memoria", 402, self.show_memory),
            )
            for title, y, callback in menu:
                button = QPushButton(title, self.canvas)
                button.setStyleSheet(invisible)
                button.clicked.connect(callback)
                self.canvas.place(button, 12, y, 242, 68)

            top_style = (
                "QPushButton{background:rgba(58,15,23,220);color:#eee;"
                "border:1px solid #651522;border-radius:8px;font-weight:bold;}"
                "QPushButton:hover{background:#83162a;}")
            self.voice = QPushButton("V", self.canvas)
            self.voice.setToolTip("Activar o desactivar voz local")
            self.voice.clicked.connect(self.toggle_voice)
            self.mic = QPushButton("MIC", self.canvas)
            self.mic.setToolTip("Dictar una orden durante 8 segundos")
            self.mic.clicked.connect(self.listen_voice)
            self.attach = QPushButton("+", self.canvas)
            self.attach.setToolTip("Adjuntar archivos")
            self.attach.clicked.connect(self.pick_files)
            self.clear = QPushButton("R", self.canvas)
            self.clear.setToolTip("Limpiar chat")
            self.clear.clicked.connect(self.chat.clear)
            for index, button in enumerate(
                    (self.voice, self.mic, self.attach, self.clear)):
                button.setStyleSheet(top_style)
                self.canvas.place(button, 1328 + index * 44, 80, 36, 34)

            galaxy_button = QPushButton("▧  GALAXIA", self.canvas)
            galaxy_button.setStyleSheet(
                "QPushButton{background:rgba(10,12,22,210);color:#ffd98a;"
                "border:1px solid #2a3a5c;border-radius:9px;font-weight:bold;}")
            galaxy_button.clicked.connect(
                lambda: self.galaxy.setVisible(not self.galaxy.isVisible()))
            self.canvas.place(galaxy_button, 920, 52, 96, 32)

            stat_frame = QFrame(self.canvas)
            stat_frame.setStyleSheet(
                "QFrame{background:rgba(4,5,9,232);border:1px solid "
                "rgba(255,40,60,155);border-radius:15px;}")
            self.canvas.place(stat_frame, 312, 708, 738, 145)
            labels = (
                ("NÚCLEO", 100, "#d11124", "%"),
                ("MEMORIA", 0, "#d89a45", "%"),
                ("ENERGÍA", 100, "#e03038", "%"),
                ("SEGURIDAD", 100, "#39d06b", "%"),
                ("VOZ", 0, "#b9b9c2", ""),
                ("COMANDOS", 0, "#666975", ""),
            )
            self.dials = []
            for index, (title, value, color, unit) in enumerate(labels):
                dial = Dial(title, value, color, unit, self.canvas)
                self.canvas.place(dial, 326 + index * 119, 728, 98, 105)
                self.dials.append(dial)

            self.plan_label = QLabel("", self.canvas)
            self.plan_label.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
            self.plan_label.setStyleSheet(
                "color:#ffd98a;background:rgba(0,0,0,120);"
                "border-radius:7px;padding:5px;")
            self.plan_label.setWordWrap(True)
            self.canvas.place(self.plan_label, 320, 92, 250, 72)
            self.plan_label.hide()
            self.update_metrics()

        def update_metrics(self):
            try:
                import psutil
                cpu = round(psutil.cpu_percent(interval=None))
                memory = round(psutil.virtual_memory().percent)
            except ImportError:
                return
            self.dials[0].set_value(cpu)
            self.dials[1].set_value(memory)
            self.dials[2].set_value(max(0, 100 - cpu))
            self.dials[3].set_value(100)
            self.dials[4].set_value(100 if self.voice_enabled else 0)

        def submit(self):
            objective = self.prompt.toPlainText().strip()
            if not objective:
                return
            self.prompt.clear()
            self.command_count += 1
            self.dials[5].set_value(min(100, self.command_count))
            self.chat.append(f"\n[USUARIO] {objective}")
            self.memory.remember(
                "chat", {"role": "user", "text": objective}, verified=True)
            plan = self.director.plan(Mission(objective))
            self.plan_label.setText(
                "MISIÓN: " + plan.branch.value.upper() + "\n" +
                " → ".join(plan.steps[:3]))
            self.plan_label.show()
            self.status.setText("● Estado: Procesando")
            self.status.setStyleSheet("color:#ffbe55;background:transparent;")
            self.galaxy.set_busy(True)
            self.prompt.setEnabled(False)
            action = self.router.route(objective, self.attachments)
            if action.kind == "capability":
                answer = QMessageBox.StandardButton.Yes
                if action.requires_confirmation:
                    answer = QMessageBox.question(
                    self, "Confirmar misión",
                    "IGRIS creará archivos en un workspace aislado. ¿Continuar?")
                if answer != QMessageBox.StandardButton.Yes:
                    self.finish_message("Operación cancelada.", False)
                    return
                threading.Thread(
                    target=self.run_capability,
                    args=(objective, action.capability, action.payload),
                    daemon=True).start()
            else:
                threading.Thread(
                    target=lambda: self.replies.put(self.assistant.respond(
                        objective, self.memory_context())),
                    daemon=True).start()

        def run_capability(self, objective, capability, payload):
            self.replies.put(self.kernel.execute(
                Mission(objective), capability, payload, confirmed=True))

        def tick(self):
            try:
                heard = self.voice_inputs.get_nowait()
            except queue.Empty:
                heard = None
            if heard is not None:
                self.mic.setEnabled(True)
                if heard:
                    self.prompt.setPlainText(heard)
                    self.submit()
                else:
                    self.chat.append("\n[VOZ] No se detectó una orden.")
            try:
                reply = self.replies.get_nowait()
            except queue.Empty:
                return
            text = getattr(reply, "text", getattr(reply, "message", str(reply)))
            model = getattr(reply, "model", "")
            self.chat.append(f"\n[IGRIS{(' · ' + model) if model else ''}] {text}")
            data = getattr(reply, "data", {})
            if self.voice_enabled:
                threading.Thread(
                    target=self.voice_engine.speak, args=(text,),
                    daemon=True).start()
            self.memory.remember(
                "chat", {"role": "igris", "text": text,
                         "ok": bool(getattr(reply, "ok", False))}, verified=True)
            if data:
                rendered = self.render_result(dict(data))
                if rendered:
                    self.chat.append(rendered)
            self.finish_message("", bool(getattr(reply, "ok", False)))

        def render_result(self, data):
            capabilities = data.get("capabilities")
            if capabilities:
                lines = ["\n[CAPACIDADES ACTIVAS]"]
                lines.extend(
                    "• " + str(item.get("description", item.get("name", "")))
                    for item in capabilities)
                return "\n".join(lines)
            files = data.get("files")
            if files:
                lines = ["\n[ARCHIVOS ANALIZADOS]"]
                lines.extend(
                    f"• {item.get('name', 'archivo')} — "
                    f"{item.get('size', 0)} bytes" for item in files)
                return "\n".join(lines)
            project = data.get("project")
            if project:
                return "\n[PROYECTO ENTREGADO] " + str(project)
            output = data.get("output")
            if output:
                return "\n[ARCHIVO GENERADO] " + str(output)
            return ""

        def finish_message(self, text, ok):
            if text:
                self.chat.append("\n[SISTEMA] " + text)
            self.galaxy.set_busy(False)
            self.prompt.setEnabled(True)
            self.prompt.setFocus()
            self.status.setText("● Estado: Operativo" if ok else
                                "● Estado: Revisión necesaria")
            color = "#55dc76" if ok else "#efb74f"
            self.status.setStyleSheet(
                f"color:{color};background:transparent;")
            self.update_metrics()

        def show_military(self):
            self.plan_label.setVisible(not self.plan_label.isVisible())

        def show_laboratory(self):
            specs = self.kernel.registry.specs()
            self.chat.append(
                "\n[LABORATORIO] Capacidades activas: " +
                ", ".join(spec.name for spec in specs))

        def toggle_voice(self):
            self.voice_enabled = not self.voice_enabled
            self.dials[4].set_value(100 if self.voice_enabled else 0)
            state = "activada" if self.voice_enabled else "desactivada"
            self.chat.append("\n[VOZ] Voz local " + state + ".")
            sample = asset_path("igris_voice_identity.wav")
            if self.voice_enabled and sample:
                self.voice_engine.play_sample(sample)

        def listen_voice(self):
            self.mic.setEnabled(False)
            self.chat.append("\n[VOZ] Escuchando...")
            threading.Thread(
                target=lambda: self.voice_inputs.put(
                    self.voice_engine.listen()), daemon=True).start()

        def show_academy(self):
            self.chat.append(
                "\n[ACADEMIA] Método IGRIS: analizar, construir, probar, "
                "reparar y entregar evidencia.")

        def show_memory(self):
            rows = list(reversed(self.memory.recent("chat", limit=6)))
            if not rows:
                self.chat.append("\n[MEMORIA] Sin recuerdos verificados.")
                return
            summary = " | ".join(
                row["content"].get("role", "?") + ": " +
                row["content"].get("text", "")[:100] for row in rows)
            self.chat.append("\n[MEMORIA] " + summary)

        def memory_context(self):
            rows = list(reversed(self.memory.recent("chat", limit=8)))
            return tuple(
                row["content"].get("role", "?") + ": " +
                row["content"].get("text", "")[:1000] for row in rows)

        def pick_files(self):
            paths, _ = QFileDialog.getOpenFileNames(
                self, "Adjuntar archivos a IGRIS")
            self.add_files(paths)

        def add_files(self, paths):
            for path in paths:
                if path and path not in self.attachments:
                    self.attachments.append(path)
            if paths:
                self.chat.append(
                    "\n[ADJUNTOS] " + ", ".join(Path(p).name for p in paths))

    app = QApplication([])
    app.setStyle("Fusion")
    app.setStyleSheet("QMainWindow{background:#030307;}")
    window = Panel()
    window.show()
    if os.environ.get("IGRIS_TEST_GUI") == "1":
        def finish_test():
            screenshot = os.environ.get("IGRIS_TEST_SCREENSHOT")
            if screenshot:
                window.grab().save(screenshot)
            app.quit()
        QTimer.singleShot(900, finish_test)
    return app.exec()
