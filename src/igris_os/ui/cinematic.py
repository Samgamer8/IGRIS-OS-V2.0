import math
import os
from datetime import datetime
from pathlib import Path
import queue
import sys
import threading

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

from igris_os.application import (
    AssistantService, MissionDirector, MissionQueue,
)
from igris_os.bootstrap import build_igris
from igris_os.application.director import ContractualPlan
from igris_os.domain import Mission, MissionBranch
from igris_os.memory import MemoryStore
from igris_os.ai.server import ensure_ollama_server
from igris_os.retrieval import RepositoryContextStore
from igris_os.ui.galaxia import GalaxiaWidget
from igris_os.voice import WindowsVoice


def asset_path(name):
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[3]))
    path = base / "assets" / name
    return path if path.is_file() else None


def runtime_root():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "runtime"
    return Path(__file__).resolve().parents[3] / "runtime"


def format_result(data):
    if data.get("capabilities"):
        return "\n[CAPACIDADES ACTIVAS]\n" + "\n".join(
            "• " + str(item.get("description", item.get("name", "")))
            for item in data["capabilities"])
    if data.get("tools"):
        return "\n[HERRAMIENTAS LOCALES]\n" + "\n".join(
            f"• {item.get('name', 'herramienta')}: " +
            ("disponible" if item.get("available") else "no instalada")
            for item in data["tools"])
    if data.get("languages"):
        return "\n[LENGUAJES REGISTRADOS]\n" + "\n".join(
            "• " + str(item.get("name", "")) for item in data["languages"])
    if data.get("files"):
        return "\n[ARCHIVOS ANALIZADOS]\n" + "\n".join(
            f"• {item.get('name', 'archivo')} — {item.get('size', 0)} bytes"
            for item in data["files"])
    if data.get("repository"):
        repo = data["repository"]
        languages = ", ".join(
            f"{name}: {count}" for name, count in repo.get("languages", {}).items())
        matches = "\n".join(
            "• " + str(item.get("path", ""))
            for item in repo.get("matches", ())[:8])
        return ("\n[MAPA DEL REPOSITORIO]"
                f"\nArchivos: {repo.get('files', 0)} · "
                f"Símbolos: {repo.get('symbols', 0)} · "
                f"Pruebas: {repo.get('tests', 0)}"
                "\nLenguajes: " + languages +
                ("\n[ARCHIVOS RELEVANTES]\n" + matches if matches else "") +
                "\n[MANIFIESTO] " + str(repo.get("manifest", "")))
    if data.get("staged_repository"):
        staged = data["staged_repository"]
        return ("\n[COPIA AISLADA VERIFICADA]"
                f"\nArchivos: {staged.get('files', 0)} · "
                f"Bytes: {staged.get('total_bytes', 0)}"
                "\n[WORKSPACE] " + str(staged.get("root", "")) +
                "\n[MANIFIESTO] " + str(staged.get("manifest", "")))
    if data.get("repository_changes"):
        changes = data["repository_changes"]
        files = "\n".join("• " + str(item)
                          for item in changes.get("changed_files", ()))
        return ("\n[CAMBIOS PROPUESTOS EN COPIA AISLADA]\n" + files +
                "\n[DIFF] " + str(changes.get("report", "")) +
                "\n[ORIGINAL] Sin modificar")
    if data.get("project"):
        return "\n[PROYECTO ENTREGADO] " + str(data["project"])
    if data.get("output"):
        return "\n[ARCHIVO GENERADO] " + str(data["output"])
    if data.get("outputs"):
        lines = "\n".join("• " + str(item) for item in data["outputs"])
        report = str(data.get("report", ""))
        return "\n[PLAN MULTIMEDIA COMPLETADO]\n" + lines + (
            "\n[EVIDENCIA] " + report if report else "")
    if data.get("rolled_back"):
        return ("\n[ROLLBACK APLICADO] No se conservó ninguna salida parcial."
                "\n[EVIDENCIA] " + str(data.get("report", "")))
    if "cpu_percent" in data:
        return ("\n[ESTADO REAL] CPU: " + str(data.get("cpu_percent")) +
                "% · Memoria: " + str(data.get("memory_percent")) + "%")
    return ""


def run_cinematic_panel():
    from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
    from PyQt6.QtGui import (
        QBrush, QColor, QConicalGradient, QFont, QIcon, QLinearGradient,
        QPainter, QPen, QPixmap, QRadialGradient,
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
            d = min(self.width() - 10, self.height() - 24)
            x, y = (self.width() - d) / 2, 4
            cx, cy = x + d / 2, y + d / 2
            r, g, b = self.color.red(), self.color.green(), self.color.blue()

            # Halo de acento alrededor del dial.
            halo = QRadialGradient(cx, cy, d * 0.6)
            halo.setColorAt(0.0, QColor(r, g, b, 110))
            halo.setColorAt(0.6, QColor(r, g, b, 42))
            halo.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(halo))
            p.drawEllipse(QRectF(cx - d * 0.6, cy - d * 0.6, d * 1.2, d * 1.2))

            # Bisel exterior (metal oscuro con filo de acento).
            rim = QLinearGradient(x, y, x + d, y + d)
            rim.setColorAt(0.0, QColor("#454b5b"))
            rim.setColorAt(0.45, QColor("#181c26"))
            rim.setColorAt(1.0, QColor("#0a0c12"))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(rim))
            p.drawEllipse(QRectF(x, y, d, d))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(r, g, b, 130), 1))
            p.drawEllipse(QRectF(x, y, d, d))

            # Cara interior con profundidad.
            face = QRadialGradient(cx, cy - d * 0.14, d * 0.6)
            face.setColorAt(0.0, QColor("#313643"))
            face.setColorAt(0.7, QColor("#12141c"))
            face.setColorAt(1.0, QColor("#050609"))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(face))
            p.drawEllipse(QRectF(x + 5, y + 5, d - 10, d - 10))

            # Pista de fondo + marcas de graduación.
            track = QRectF(x + 13, y + 13, d - 26, d - 26)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor("#191c26"), 7))
            p.drawArc(track, 0, 360 * 16)
            for k in range(40):
                ang = math.radians(90 - k * 9.0)
                activa = k * 2.5 <= self.value
                r0, r1 = d / 2 - 19, d / 2 - 15
                tick = QColor(r, g, b, 210 if activa else 60)
                p.setPen(QPen(tick, 1.6 if activa else 1.0))
                p.drawLine(QPointF(cx + r0 * math.cos(ang), cy - r0 * math.sin(ang)),
                           QPointF(cx + r1 * math.cos(ang), cy - r1 * math.sin(ang)))

            # Arco de progreso con barrido cónico.
            if self.value > 0:
                span = -int(360 * 16 * self.value / 100)
                sweep = QConicalGradient(cx, cy, 90)
                sweep.setColorAt(0.0, self.color.lighter(150))
                sweep.setColorAt(0.55, self.color)
                sweep.setColorAt(1.0, self.color.darker(150))
                pen = QPen(QBrush(sweep), 6)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(pen)
                p.drawArc(track, 90 * 16, span)

            # Valor centrado.
            p.setFont(QFont("Consolas", max(9, int(d / 4.2)), QFont.Weight.Bold))
            p.setPen(QColor("#f7f7fa"))
            p.drawText(QRectF(x, y - 2, d, d), Qt.AlignmentFlag.AlignCenter,
                       f"{self.value}{self.unit}")

            # Título bajo el dial.
            p.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
            p.setPen(QColor("#aeb2bf"))
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
            self.resize(1440, 810)
            self.setMinimumSize(1100, 619)
            icon = asset_path("igris_icon_v2.ico")
            if icon:
                self.setWindowIcon(QIcon(str(icon)))
            self.runtime = runtime_root()
            self.active_job = None
            self.voice_enabled = True
            self.voice_inputs = queue.Queue()
            self.replies = queue.Queue()
            self.progress_events = queue.Queue()
            self.command_count = 0
            self.attachments = []
            self.assistant = None
            self.director = None
            self.kernel = None
            self.context_store = None
            self.memory = None
            self.mission_queue = None
            self.voice_engine = None
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
            QTimer.singleShot(0, self._init_services)
            QTimer.singleShot(100, self._probe_server)

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
                "QFrame{background:rgba(4,5,10,242);border:1px solid "
                "rgba(209,17,36,205);border-radius:18px;}")
            self.canvas.place(chat_frame, 1078, 48, 500, 830)

            header = QLabel("COMUNICACIÓN", self.canvas)
            header.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            header.setStyleSheet("color:#ffd98a;background:transparent;")
            self.canvas.place(header, 1104, 58, 220, 20)

            self.clock = QLabel("", self.canvas)
            self.clock.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            self.clock.setStyleSheet("color:#d7dae2;background:transparent;")
            self.clock.setAlignment(Qt.AlignmentFlag.AlignRight |
                                    Qt.AlignmentFlag.AlignVCenter)
            self.canvas.place(self.clock, 1330, 58, 212, 20)

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
                "QTextEdit:focus{border-color:#ff3b5c;background:#131722;}")
            self.canvas.place(self.prompt, 1100, 770, 390, 72)

            send = QPushButton("›", self.canvas)
            send.setFont(QFont("Consolas", 26, QFont.Weight.Bold))
            send.setCursor(Qt.CursorShape.PointingHandCursor)
            send.clicked.connect(self.submit)
            send.setStyleSheet(
                "QPushButton{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,"
                "stop:0 #a1122b, stop:1 #57040f);color:white;"
                "border:1px solid #ef2444;border-radius:10px;}"
                "QPushButton:hover{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,"
                "stop:0 #d4203c, stop:1 #7c0a1d);border-color:#ff5b74;}")
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
                "QPushButton:hover{background:#8a1830;border-color:#c2243d;}")
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
            self.clear.setToolTip("Reiniciar vista y quitar adjuntos")
            self.clear.clicked.connect(self.reset_view)
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
                "QFrame{background:rgba(4,5,9,244);border:1px solid "
                "rgba(255,72,92,195);border-radius:15px;}")
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
            if not _HAS_PSUTIL:
                return
            try:
                cpu = round(psutil.cpu_percent(interval=None))
                memory = round(psutil.virtual_memory().percent)
            except (OSError, psutil.Error):
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
            if self.memory is not None:
                try:
                    self.memory.remember(
                        "chat", {"role": "user", "text": objective}, verified=True)
                except Exception:
                    pass
            if self._is_greeting(objective):
                self.finish_message("Aqui estoy. Que necesitas?", True)
                return
            if self.director is None or self.kernel is None:
                self.finish_message("Servicios aún inicializando, intenta de nuevo en unos segundos.", False)
                return
            self.plan_label.setText("MISIÓN: Planificando...")
            self.plan_label.show()
            self.status.setText("● Estado: Planificando")
            self.status.setStyleSheet("color:#ffbe55;background:transparent;")
            self.galaxy.set_busy(True)
            threading.Thread(
                target=self._plan_in_background, args=(objective,),
                daemon=True).start()

        _GREETINGS = frozenset({
            "hola", "hey", "hi", "buenas", "que tal", "como estas",
            "buenos dias", "buenas tardes", "buenas noches", "buen dia",
            "holis", "holi", "saludos", "que onda", "que hubo",
        })

        def _is_greeting(self, text: str) -> bool:
            clean = text.strip().lower().strip("¿?!. ")
            return clean in self._GREETINGS

        def _plan_in_background(self, objective: str):
            try:
                plan = self.director.plan(Mission(objective))
            except Exception:
                plan = ContractualPlan(
                    mission_id="fallback",
                    objective=objective,
                    branch=MissionBranch.GENERAL,
                    deliverables=(objective,))
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._on_plan_ready(plan, objective))

        def _on_plan_ready(self, plan, objective: str):
            preview = plan.deliverables[:3] if plan.deliverables else (plan.objective,)
            self.plan_label.setText(
                "MISIÓN: " + plan.branch.value.upper() + "\n" +
                " → ".join(preview))
            self.status.setText("● Estado: Procesando")
            self.status.setStyleSheet("color:#ffbe55;background:transparent;")
            try:
                action = self._route_with_plan(plan, objective)
                if action.kind == "capability":
                    answer = QMessageBox.StandardButton.Yes
                    if action.requires_confirmation:
                        answer = QMessageBox.question(
                            self, "Confirmar misión",
                            "IGRIS creará archivos en un workspace aislado. ¿Continuar?")
                    if answer != QMessageBox.StandardButton.Yes:
                        self.finish_message("Operación cancelada.", False)
                        return
                    payload = dict(action.payload or {})
                    payload["__approval"] = self.kernel.issue_approval(
                        objective, action.capability)
                    job = self.mission_queue.enqueue(
                        objective, "capability", action.capability, payload)
                else:
                    job = self.mission_queue.enqueue(objective, "chat")
                pending = self.mission_queue.summary()["pending"]
                self.chat.append(f"[COLA] Misión {job.id[:8]} registrada · pendientes: {pending}")
            except Exception as exc:
                self.finish_message(f"Error interno: {exc}", False)
                return
            self.dispatch_next()

        def _route_with_plan(self, plan, objective: str):
            from igris_os.application.mission_router import (
                RoutedAction, _programming_language, _dimensions,
                _project_name, _game_genre)
            from pathlib import Path as _P
            low = objective.casefold()
            if any(phrase in low for phrase in (
                    "tus funciones", "tus capacidades", "qué puedes hacer",
                    "que puedes hacer", "capacidades tienes")):
                return RoutedAction("capability", "system.capabilities")
            if any(phrase in low for phrase in (
                    "herramientas disponibles", "herramientas tienes",
                    "programas instalados")):
                return RoutedAction("capability", "system.tools")
            source = str(_P(self.attachments[0]).resolve()) if self.attachments else ""
            if any(phrase in low for phrase in (
                    "coordina especialistas", "revisión cruzada",
                    "revision cruzada", "equipo de especialistas")):
                return RoutedAction("capability", "mission.coordinate",
                                    {"objective": objective}, True)
            if source and _P(source).is_dir() and any(word in low for word in (
                    "modifica", "arregla", "implementa", "corrige", "programa")):
                return RoutedAction("capability", "repository.develop",
                                    {"root": source, "objective": objective}, True)
            if source and _P(source).is_dir() and any(phrase in low for phrase in (
                    "copia aislada", "prepara este proyecto",
                    "trabaja en este proyecto", "prepara el repositorio")):
                return RoutedAction("capability", "repository.stage",
                                    {"root": source}, True)
            if source and _P(source).is_dir() and any(word in low for word in (
                    "repositorio", "proyecto", "código", "codigo", "carpeta")):
                return RoutedAction("capability", "repository.analyze",
                                    {"root": source, "query": objective}, True)
            if source and any(word in low for word in (
                    "redimensiona", "resize", "escala")):
                w, h = _dimensions(low)
                return RoutedAction("capability", "image.resize",
                                    {"source": source, "output": "imagen_redimensionada.png",
                                     "width": w, "height": h}, True)
            if source and any(word in low for word in (
                    "extrae audio", "extraer audio", "a mp3")):
                return RoutedAction("capability", "multimedia.extract_audio",
                                    {"source": source, "output": "audio_extraido.mp3"}, True)
            if source and any(word in low for word in (
                    "miniatura", "fotograma", "thumbnail")):
                return RoutedAction("capability", "multimedia.thumbnail",
                                    {"source": source, "output": "miniatura.png"}, True)
            if source and any(word in low for word in (
                    "convierte", "transcodifica", "a mp4")):
                return RoutedAction("capability", "multimedia.transcode",
                                    {"source": source, "output": "video_convertido.mp4"}, True)
            if source and any(phrase in low for phrase in (
                    "edita este video", "procesa este video", "prepara este video",
                    "edita el video", "procesa el video")):
                return RoutedAction("capability", "multimedia.pipeline",
                                    {"source": source, "operations": [
                                        {"kind": "thumbnail", "output": "preview.png", "second": 0},
                                        {"kind": "transcode", "output": "video_final.mp4"},
                                    ]}, True)
            if source and any(word in low for word in (
                    "verifica", "valida", "comprueba", "revisa visualmente")):
                return RoutedAction("capability", "multimedia.verify",
                                    {"source": source})
            if self.attachments and any(word in low for word in (
                    "analiza", "revisa", "inspecciona", "resume", "archivos")):
                return RoutedAction("capability", "files.inspect",
                                    {"sources": [str(_P(a).resolve()) for a in self.attachments]})
            if plan.branch is MissionBranch.PROGRAMMING and "python" in low:
                return RoutedAction("capability", "programming.python.develop",
                                    {"objective": objective}, True)
            if plan.branch is MissionBranch.PROGRAMMING:
                language = _programming_language(low)
                return RoutedAction("capability", "programming.autonomous.develop",
                                    {"objective": objective, "language": language}, True)
            if plan.branch is MissionBranch.GAMES and any(
                    word in low for word in ("exporta", "compila", "ejecutable",
                                             "exe", "build", "empaqueta")):
                return RoutedAction("capability", "games.godot.export", {}, True)
            if plan.branch is MissionBranch.GAMES and any(
                    word in low for word in ("crea", "construye", "genera")):
                return RoutedAction("capability", "games.godot.scaffold",
                                    {"name": _project_name(objective),
                                     "genre": _game_genre(low)}, True)
            if plan.branch is MissionBranch.GAMES and any(
                    word in low for word in ("prueba", "ejecuta", "corre",
                                             "playtest", "comprueba el juego",
                                             "verifica el juego")):
                return RoutedAction("capability", "games.godot.playtest", {}, True)
            if any(phrase in low for phrase in (
                    "di algo", "di ", "pronuncia", "recita", "lee en voz alta",
                    "habla ahora", "repite esto", "reproduce este texto",
                    "reproduce el texto")):
                return RoutedAction("capability", "voice.set",
                                    {"objective": objective, "text": objective}, False)
            return RoutedAction("chat")

        def dispatch_next(self):
            try:
                if self.active_job is not None or self.mission_queue is None:
                    return
                job = self.mission_queue.next()
                if job is None:
                    return
                self.active_job = job
                self.status.setText("● Estado: Ejecutando " + job.id[:8])
                self.galaxy.set_busy(True)
                threading.Thread(target=self.run_job, args=(job,), daemon=True).start()
            except Exception:
                pass

        def run_job(self, job):
            def report_progress(percent, message):
                try:
                    self.mission_queue.update_progress(
                        job.id, percent, message)
                except (KeyError, ValueError):
                    pass
                self.progress_events.put((job.id, percent, message))
            try:
                if job.kind == "capability":
                    reply = self.kernel.execute(
                        Mission(job.objective), job.capability, job.payload,
                        approval=job.payload.get("__approval"),
                        on_progress=report_progress)
                    self.remember_repository_context(reply, job)
                else:
                    context = self.memory_context() + self.semantic_context(job.objective)
                    reply = self.assistant.respond(job.objective, context)
            except Exception as exc:
                from igris_os.application.assistant import AssistantReply
                reply = AssistantReply(
                    text=f"Error ejecutando misión: {exc}",
                    ok=False, model="", data={})
            self.replies.put((job.id, reply))

        def tick(self):
            if getattr(self, "clock", None) is not None:
                now = datetime.now().strftime("%H:%M:%S")
                if self.clock.text() != now:
                    self.clock.setText(now)
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
                job_id, reply = self.replies.get_nowait()
            except queue.Empty:
                try:
                    job_id, percent, message = self.progress_events.get_nowait()
                    self.status.setText(
                        f"● Estado: Ejecutando {job_id[:8]} · {percent}% {message}")
                    self.dispatch_next()
                except queue.Empty:
                    self.dispatch_next()
                return
            text = getattr(reply, "text", getattr(reply, "message", str(reply)))
            ok = bool(getattr(reply, "ok", False))
            model = getattr(reply, "model", "")
            self.chat.append(f"\n[IGRIS{(' · ' + model) if model else ''}] {text}")
            data = getattr(reply, "data", {})
            try:
                if self.voice_enabled and self.voice_engine is not None:
                    threading.Thread(
                        target=self.voice_engine.speak, args=(text,),
                        daemon=True).start()
                if self.memory is not None:
                    self.memory.remember(
                        "chat", {"role": "igris", "text": text,
                                 "ok": bool(getattr(reply, "ok", False))}, verified=True)
                if data and self.active_job is not None and self.memory is not None:
                    technical = self.technical_summary(
                        self.active_job.objective, self.active_job.capability,
                        dict(data))
                    if technical:
                        self.memory.remember(
                            "technical", technical, verified=ok)
                if data:
                    rendered = self.render_result(dict(data))
                    if rendered:
                        self.chat.append(rendered)
                if self.mission_queue is not None:
                    self.mission_queue.finish(job_id, ok, text)
            except Exception:
                pass
            finally:
                self.active_job = None
                self.finish_message("", ok)
                self.dispatch_next()

        def render_result(self, data):
            return format_result(data)

        @staticmethod
        def technical_summary(objective, capability, data):
            summary = {"objective": objective[:500],
                       "capability": capability or "chat"}
            if data.get("repository"):
                repo = data["repository"]
                summary.update(kind="repository", files=repo.get("files", 0),
                               symbols=repo.get("symbols", 0),
                               tests=repo.get("tests", 0),
                               manifest=repo.get("manifest", ""))
                return summary
            if data.get("staged_repository"):
                staged = data["staged_repository"]
                summary.update(kind="staged_repository",
                               path=staged.get("root", ""),
                               files=staged.get("files", 0),
                               manifest=staged.get("manifest", ""))
                return summary
            if data.get("repository_changes"):
                changes = data["repository_changes"]
                summary.update(kind="repository_changes",
                               path=changes.get("staged_root", ""),
                               report=changes.get("report", ""),
                               files=list(changes.get("changed_files", ())))
                return summary
            if data.get("project"):
                summary.update(kind="project", path=str(data["project"]),
                               language=str(data.get("language", "python")))
                return summary
            if data.get("outputs") or data.get("output"):
                summary.update(kind="artifact",
                               outputs=list(data.get("outputs", ())) or
                               [str(data.get("output"))])
                return summary
            return None

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

        def _probe_server(self):
            def _do():
                self.ai_server_running = ensure_ollama_server(auto=True)
            threading.Thread(target=_do, daemon=True).start()

        def _init_services(self):
            try:
                self.assistant = AssistantService()
                self.director = MissionDirector()
                self.kernel = build_igris(self.runtime)
                self.context_store = RepositoryContextStore(self.runtime)
                self.memory = MemoryStore(self.runtime / "memory" / "chat.db")
                self.mission_queue = MissionQueue(self.runtime / "missions_queue.json")
                self.voice_engine = WindowsVoice()
            except Exception as exc:
                self.chat.append(f"\n[SISTEMA] Error inicializando servicios: {exc}")
            self.dispatch_next()

        def show_military(self):
            self.plan_label.setVisible(not self.plan_label.isVisible())

        def show_laboratory(self):
            events = self.kernel.audit.recent(8)
            if not events:
                self.chat.append("\n[LABORATORIO] Aún no hay misiones ejecutadas.")
                return
            lines = ["\n[LABORATORIO · MISIONES RECIENTES]"]
            for event in events:
                state = "OK" if event.get("ok") else event.get("code", "ERROR")
                lines.append(f"• {event.get('capability', 'desconocida')} — {state}")
            self.chat.append("\n".join(lines))

        def toggle_voice(self):
            self.voice_enabled = not self.voice_enabled
            self.dials[4].set_value(100 if self.voice_enabled else 0)
            state = "activada" if self.voice_enabled else "desactivada"
            self.chat.append("\n[VOZ] Voz local " + state + ".")
            if self.voice_engine is None:
                return
            sample = asset_path("igris_voice_identity.wav")
            if self.voice_enabled and sample:
                threading.Thread(
                    target=self.voice_engine.play_sample,
                    args=(sample,), daemon=True).start()

        def listen_voice(self):
            if self.voice_engine is None:
                return
            self.mic.setEnabled(False)
            self.chat.append("\n[VOZ] Escuchando...")
            threading.Thread(
                target=lambda: self.voice_inputs.put(
                    self.voice_engine.listen()), daemon=True).start()

        def show_academy(self):
            self.chat.append(
                "\n[ACADEMIA] Método IGRIS: analizar, construir, probar, "
                "reparar y entregar evidencia.")

        def reset_view(self):
            cancelled = self.mission_queue.cancel_pending() if self.mission_queue else 0
            self.chat.clear()
            self.attachments.clear()
            self.plan_label.hide()
            self.prompt.clear()
            self.chat.append(
                "[SISTEMA] Vista reiniciada. Memoria y auditoría conservadas. "
                f"Misiones pendientes canceladas: {cancelled}.")

        def show_memory(self):
            if self.memory is None:
                self.chat.append("\n[MEMORIA] Memoria aún no disponible.")
                return
            try:
                rows = list(reversed(self.memory.recent("chat", limit=6)))
                if not rows:
                    self.chat.append("\n[MEMORIA] Sin recuerdos verificados.")
                    return
                summary = " | ".join(
                    row["content"].get("role", "?") + ": " +
                    row["content"].get("text", "")[:100] for row in rows)
                self.chat.append("\n[MEMORIA] " + summary)
                technical_count = self.memory.count("technical")
                if technical_count:
                    latest = self.memory.recent("technical", limit=1)[0]["content"]
                    self.chat.append(
                        f"\n[MEMORIA TÉCNICA] {technical_count} evidencias · última: "
                        + latest.get("objective", "")[:120])
            except Exception:
                self.chat.append("\n[MEMORIA] Error leyendo memoria.")

        def remember_repository_context(self, reply, job):
            if self.context_store is None:
                return
            data = getattr(reply, "data", {})
            repository = data.get("repository") or {}
            if getattr(reply, "ok", False) and repository.get("records"):
                root = Path(job.payload.get("root", ""))
                if root.is_dir():
                    self.context_store.remember(root, repository["records"])

        def memory_context(self):
            if self.memory is None:
                return ()
            rows = list(reversed(self.memory.recent("chat", limit=8)))
            context = [
                row["content"].get("role", "?") + ": " +
                row["content"].get("text", "")[:1000] for row in rows]
            for row in reversed(self.memory.recent("technical", limit=3)):
                item = row["content"]
                context.append(
                    "evidencia técnica: " + item.get("objective", "")[:300] +
                    " | " + item.get("capability", ""))
            return tuple(context)

        def semantic_context(self, objective):
            if self.context_store is None:
                return ()
            return tuple(
                "archivo relevante: " + str(item["path"]) +
                " — " + str(item["excerpt"])[:250]
                for item in self.context_store.retrieve(objective, limit=4))

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
