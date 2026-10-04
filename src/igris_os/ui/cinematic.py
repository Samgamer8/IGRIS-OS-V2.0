import math
import os
import time
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
from igris_os.application.assistant import is_conversational_input
from igris_os.application.intent_classifier import is_capability_query as classify_capability_query
from igris_os.core.igrisd import IgrisDaemon
from igris_os.ai.daemon_process import AIProcessRunner
from igris_os.application.conversation_daemon import _ProcessAIClient
from igris_os.bootstrap import build_igris
from igris_os.application.director import ContractualPlan
from igris_os.domain import Mission, MissionBranch
from igris_os.memory import MemoryStore
from igris_os.ai.server import ensure_ollama_server
from igris_os.retrieval import RepositoryContextStore
from igris_os.ui.galaxia import GalaxiaWidget
from igris_os.voice import WindowsVoice
from igris_os.ui.resilience import resilient_slot


def is_capability_query(objective: str) -> bool:
    """Consulta el clasificador central; la GUI no mantiene reglas propias."""
    return classify_capability_query(objective)


def asset_path(name):
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[3]))
    path = base / "assets" / name
    return path if path.is_file() else None


def runtime_root():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "runtime"
    return Path(__file__).resolve().parents[3] / "runtime"


def format_result(data):
    artifact = data.get('artifact')
    if isinstance(artifact, dict) and artifact.get('media_type') == 'image/png':
        state = 'Verificado' if artifact.get('verified') is True else 'Pendiente de verificacion'
        return ('\n[RESULTADO] ' + str(artifact.get('output', '')) +
                '\n[IMAGEN] ' + str(artifact.get('width', '?')) + ' x ' + str(artifact.get('height', '?')) +
                ' px; ' + str(artifact.get('spheres', '?')) + ' esfera(s)' +
                '\n[METODO] ' + str(artifact.get('method', '')) +
                '\n[COMPROBACION] ' + state + ': ' + str(artifact.get('verification_scope', '')) +
                '\n[EVIDENCIA] ' + str(artifact.get('report', '')))
    if data.get('work_status'):
        delivery = data.get('work_delivery', {})
        states = {'needs_input': 'Esperando tu respuesta', 'ready_for_review': 'Copia lista para revisar',
                  'delivered': 'Entregado', 'blocked': 'Bloqueado',
                  'needs_download_approval': 'Esperando autorizacion de descarga'}
        lines = ['\n[ENCARGO] ' + states.get(data['work_status'], str(data['work_status']))]
        if delivery:
            lines += [str(delivery.get('understanding', '')),
                      '[COPIA PARA REVISAR] ' + str(delivery.get('staged_root', '')),
                      '[ARCHIVOS PROGRAMADOS]\n' + '\n'.join(delivery.get('changed_files', [])),
                      '[DIFERENCIAS] ' + str(delivery.get('diff', '')),
                      '[EVIDENCIA] ' + str(delivery.get('report', ''))]
            if delivery.get('manual_checks'):
                lines.append('[PENDIENTE DE TU REVISION]\n' + '\n'.join(delivery['manual_checks']))
        else:
            if data.get('project'):
                label = '[PROYECTO]' if data['work_status'] == 'delivered' else '[COPIA DE TRABAJO]'
                lines.append(label + ' ' + str(data['project']))
            if data.get('questions'):
                lines.append('\n'.join(data['questions']))
            if data.get('report'):
                lines.append('[EVIDENCIA] ' + str(data['report']))
            if data.get('backup'):
                lines.append('[RESPALDO] ' + str(data['backup']))
        contract = data.get('delivery_contract', {})
        if contract.get('destination'):
            lines.append('[DESTINO SOLICITADO] ' + str(contract['destination']))
        if contract.get('executable_name'):
            lines.append('[EJECUTABLE SOLICITADO] ' + str(contract['executable_name']))
        if data.get('executable') or delivery.get('executable'):
            lines.append('[EJECUTABLE COMPROBADO] ' + str(data.get('executable') or delivery['executable']))
        if data.get('model_calls') is not None:
            lines.append('[LLAMADAS A ESPECIALISTAS] ' + str(data['model_calls']))
        budget = data.get('budget', {})
        if budget:
            lines.append('[LIMITES] ' + str(budget.get('calls_used', 0)) + '/' +
                         str(budget.get('max_calls', '?')) + ' llamadas; ' +
                         str(budget.get('elapsed_seconds', 0)) + '/' +
                         str(budget.get('max_seconds', '?')) + ' segundos')
        if data.get('last_failure', {}).get('message') and data['work_status'] == 'blocked':
            failure = data['last_failure']
            lines.append('[ULTIMO FALLO REGISTRADO] ' + str(failure.get('tool', '')) + ': ' +
                         str(failure['message'])[-1200:])
        if data.get('diagnostic_report'):
            lines.append('[DIAGNOSTICO DEL ENCARGO] ' + str(data['diagnostic_report']))
        return '\n'.join(lines)
    if data.get("host_report"):
        import json
        return "\n[EQUIPO LOCAL]\n" + json.dumps(data["host_report"], ensure_ascii=False, indent=2)
    if data.get("template_search"):
        result = data["template_search"]
        found = result["directories"] + result["archives"]
        return ("\n[GODOT] " + (result["godot_version"] or "no localizado") +
                "\n[CARPETAS REVISADAS]\n" + "\n".join(result["searched"]) +
                "\n[PLANTILLAS]\n" + ("\n".join(
                    item["path"] + " · " + item["version"] +
                    (" · compatible" if item["compatible"] else " · version no compatible")
                    for item in found) if found else "No encontradas") +
                ("\n" + "\n".join(result["diagnostics"]) if result["diagnostics"] else ""))
    if data.get("diagnostics") and not data.get("project"):
        details = "\n".join("• " + str(item)[:1800]
                            for item in data["diagnostics"][-4:])
        report = data.get("diagnostic_report", "")
        return ("\n[DIAGNOSTICO]\n" + details + ("\nInforme: " + str(report) if report else "") +
                ("\n[AVANCE GUARDADO]\n" + str(data["partial_project"]) if data.get("partial_project") else "") +
                ("\n[PROGRESO]\n" + str(data["checkpoint"]) if data.get("checkpoint") else ""))
    if data.get("staged_project") and not data.get("project"):
        return ("\n[STAGING VERIFICADO]\n" + str(data["staged_project"]) +
                "\nEsperando autorización de entrega.")
    if data.get("questions"):
        return "\n[DATOS NECESARIOS]\n" + "\n".join(
            "• " + str(question) for question in data["questions"])
    if data.get("project_plan"):
        plan = data["project_plan"]
        phases = "\n".join(
            "• " + str(item.get("name", "")) + ": " +
            str(item.get("outcome", "")) + "\n  Puerta: " +
            str(item.get("gate", ""))
            for item in plan.get("phases", ()))
        return ("\n[PLAN DE PROYECTO] " + str(plan.get("project", "")) +
                "\n[FASES]\n" + phases +
                "\n[RIESGOS]\n" + "\n".join(
                    "• " + str(item) for item in plan.get("risks", ())) +
                "\n[DEPENDENCIAS]\n" + "\n".join(
                    "• " + str(item) for item in plan.get("dependencies", ())))
    if data.get("sales_plan"):
        plan = data["sales_plan"]
        actions = "\n".join("• " + str(item) for item in plan.get("actions", ()))
        assumptions = "\n".join(
            "• " + str(item) for item in plan.get("assumptions", ()))
        return ("\n[PLAN COMERCIAL] " + str(plan.get("product", "")) +
                "\nCliente: " + str(plan.get("audience", "")) +
                "\nCanal: " + str(plan.get("channel", "")) +
                "\nMargen por venta: " + str(plan.get("contribution_margin", 0)) +
                "\nPunto de equilibrio: " + str(plan.get("break_even_sales", 0)) +
                " ventas\n[ACCIONES]\n" + actions +
                "\n[SUPUESTOS]\n" + assumptions)
    if data.get("capabilities"):
        return "\n[FUNCIONES REGISTRADAS · DISPONIBILIDAD NO COMPROBADA]\n" + "\n".join(
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
    if data.get("updated_existing"):
        files = "\n".join(
            "• " + str(item) for item in data.get("changed_files", ()))
        return ("\n[REPOSITORIO ORIGINAL ACTUALIZADO Y VERIFICADO]" +
                ("\n" + files if files else "") +
                "\n[ORIGINAL] " + str(data.get("project", "")) +
                "\n[RESPALDO] " + str(data.get("backup", "")) +
                ("\n[EVIDENCIA] " + str(data["report"]) if data.get("report") else ""))
    if data.get("repository_changes"):
        changes = data["repository_changes"]
        files = "\n".join("• " + str(item)
                          for item in changes.get("changed_files", ()))
        return ("\n[CAMBIOS PROPUESTOS EN COPIA AISLADA]\n" + files +
                "\n[DIFF] " + str(changes.get("report", "")) +
                ("\n[RESPALDO] " + str(data.get("backup", "")) if data.get("updated_existing") else "\n[ORIGINAL] Sin modificar"))
    if data.get("facts") and ("risks" in data or "required_tests" in data):
        facts = "\n".join("• " + str(item) for item in data.get("facts", ()))
        risks = "\n".join("• " + str(item) for item in data.get("risks", ()))
        doubts = "\n".join("• " + str(item) for item in data.get("doubts", ()))
        tests = "\n".join("• " + str(item) for item in data.get("required_tests", ()))
        return ("\n[DIAGNOSTICO TECNICO]\n[HECHOS]\n" + facts +
                ("\n[RIESGOS]\n" + risks if risks else "") +
                ("\n[DUDAS]\n" + doubts if doubts else "") +
                "\n[PRUEBAS NECESARIAS]\n" + tests +
                "\n[PROPUESTA]\n" + "\n".join(
                    "• " + str(item) for item in data.get("proposal", ())))
    if data.get("affected_files") and "changes" in data:
        return ("\n[PROPUESTA DE CAMBIOS]\nArchivos: " +
                ", ".join(str(item) for item in data["affected_files"]) +
                "\n[RIESGOS]\n" + "\n".join(
                    "• " + str(item) for item in data.get("risks", ())) +
                "\n[CAMBIOS]\n" + "\n".join(
                    "• " + str(item) for item in data.get("changes", ())) +
                "\n[PRUEBAS]\n" + "\n".join(
                    "• " + str(item) for item in data.get("tests", ())) +
                "\n[CONFIRMACION REQUERIDA] " +
                str(data.get("requires_confirmation", True)))
    if data.get("project"):
        project = Path(str(data["project"]))
        files = ()
        if project.is_dir():
            files = tuple(sorted(
                str(item.relative_to(project)).replace("\\", "/")
                for item in project.rglob("*") if item.is_file()
            ))
        verification = "verificacion no confirmada"
        verification_file = project / "VERIFICATION.json"
        if verification_file.is_file():
            verification = "VERIFICATION.json presente"
        return ("\n[PROYECTO ENTREGADO]\n[UBICACION] " + str(project) +
                "\n[ARCHIVOS]\n" + "\n".join(
                    "• " + item for item in files) +
                "\n[ESTADO] " + verification +
                "\n[ORIGINAL] Sin modificar")
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
    if os.name == "nt":
        os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
    from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
    from PyQt6.QtGui import (
        QBrush, QColor, QConicalGradient, QFont, QIcon, QLinearGradient,
        QPainter, QPen, QPixmap, QRadialGradient,
    )
    from PyQt6.QtWidgets import (
        QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
        QFileDialog, QFormLayout, QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
        QMainWindow, QMessageBox, QPushButton, QTextEdit, QVBoxLayout, QWidget,
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
            p.setFont(QFont("Segoe UI", max(9, int(d / 4.2)), QFont.Weight.Bold))
            p.setPen(QColor("#f7f7fa"))
            p.drawText(QRectF(x, y - 2, d, d), Qt.AlignmentFlag.AlignCenter,
                       f"{self.value}{self.unit}")

            # Título bajo el dial.
            p.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
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
            self.relayout()
            super().resizeEvent(event)

        def relayout(self):
            sx, sy = self.width() / self.BASE_W, self.height() / self.BASE_H
            for widget, x, y, w, h in self.items:
                widget.setGeometry(round(x * sx), round(y * sy),
                                   round(w * sx), round(h * sy))

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
            _edition = os.environ.get("IGRIS_EDITION", "").strip()
            self.setWindowTitle("IGRIS OS — Centro de Control" +
                               (f" [{_edition}]" if _edition else ""))
            self.resize(1440, 810)
            self.setMinimumSize(1100, 619)
            icon = asset_path("igris_icon_v2.ico")
            if icon:
                self.setWindowIcon(QIcon(str(icon)))
            self.runtime = runtime_root()
            self.active_job = None
            self._programming_focus = None
            self._last_submitted_objective = ''
            self._deciding_task_switch = False
            self.voice_enabled = True
            self.voice_inputs = queue.Queue()
            self.replies = queue.Queue()
            self.progress_events = queue.Queue()
            self.backend_events = queue.Queue()
            self.plan_events = queue.Queue()
            self.intent_events = queue.Queue()
            self.command_count = 0
            self.attachments = []
            self._artifact_catalog = {}
            self._artifact_previews = []
            self.assistant = None
            self.director = None
            self.cognitive = None
            self.cognitive_state = None
            self.kernel = None
            self.context_store = None
            self.memory = None
            self.mission_queue = None
            self.voice_engine = None
            from igris_os.ui.settings_store import load_settings
            self.settings = load_settings(self.runtime)
            self._last_backends: list = []
            self._last_models: tuple = ()
            self._last_backend = ""
            self._last_model = ""
            self._samadmin_requests = {}
            self._last_samadmin_poll = 0.0
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
            self.backend_timer = QTimer(self)
            self.backend_timer.timeout.connect(self._refresh_backend)
            self.backend_timer.start(5000)
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
            header.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            header.setStyleSheet("color:#ffd98a;background:transparent;")
            self.canvas.place(header, 1104, 58, 220, 20)

            self.clock = QLabel("", self.canvas)
            self.clock.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            self.clock.setStyleSheet("color:#d7dae2;background:transparent;")
            self.clock.setAlignment(Qt.AlignmentFlag.AlignRight |
                                    Qt.AlignmentFlag.AlignVCenter)
            self.canvas.place(self.clock, 1330, 58, 212, 20)

            from PyQt6.QtWidgets import QTextBrowser
            from PyQt6.QtGui import QTextOption
            from igris_os.ui.artifact_viewer import open_artifact
            self.chat = QTextBrowser(self.canvas)
            self.chat.setOpenLinks(False)
            self.chat.setOpenExternalLinks(False)
            self.chat.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
            self.chat.anchorClicked.connect(lambda url: open_artifact(self, url))
            self.chat.setReadOnly(True)
            self.chat.setFont(QFont("Segoe UI", 11))
            self.chat.setStyleSheet(
                "QTextEdit{background:rgba(4,5,10,180);color:#e8e8ec;"
                "border:1px solid rgba(209,17,36,150);border-radius:15px;"
                "padding:18px;} QScrollBar:vertical{width:8px;background:transparent;}"
                "QScrollBar::handle:vertical{background:#65101e;border-radius:4px;}")
            self.chat.setPlainText(
                "[IGRIS] Interfaz abierta.\nLa disponibilidad de la IA se muestra en la barra de estado.\n\n"
                "[SISTEMA] Escribe una orden. Shift+Enter crea otra linea.")
            self.canvas.place(self.chat, 1110, 120, 435, 610)

            self.prompt = PromptEdit(self.canvas)
            self.prompt.setFont(QFont("Segoe UI", 13))
            self.prompt.setPlaceholderText("Escribe una orden...")
            self.prompt.setStyleSheet(
                "QTextEdit{background:#11131a;color:#f2f2f5;"
                "border:2px solid #a7152d;border-radius:17px;padding:16px;}"
                "QTextEdit:focus{border-color:#ff3b5c;background:#131722;}")
            self.canvas.place(self.prompt, 1100, 770, 390, 72)

            send = QPushButton("›", self.canvas)
            send.setFont(QFont("Segoe UI", 26, QFont.Weight.Bold))
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
            self.status.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            self.status.setStyleSheet("color:#55dc76;background:transparent;")
            self.canvas.place(self.status, 48, 847, 230, 30)

            self.backend_label = QLabel("IA: detectando...", self.canvas)
            self.backend_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            self.backend_label.setStyleSheet(
                "color:#ffd98a;background:transparent;")
            self.canvas.place(self.backend_label, 286, 847, 660, 30)

            menu_style = (
                "QPushButton{background:rgba(7,8,13,235);color:#e9e9ef;"
                "text-align:left;padding-left:28px;border:1px solid rgba(120,25,42,150);"
                "border-radius:11px;font-size:14px;font-weight:700;}"
                "QPushButton:hover{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
                "stop:0 #8d142b,stop:0.75 #3c0b16,stop:1 #13070c);color:white;"
                "border:1px solid #ff4965;}"
                "QPushButton:pressed{background:#bc1e3b;}")
            menu = (
                ("⚙  PROPIEDADES", 152, self.show_properties),
                ("◈  PROYECTOS", 234, self.show_projects),
                ("▣  ACADEMIA", 318, self.show_academy),
                ("✚  DIAGNÓSTICO", 402, self.show_integrity),
            )
            for title, y, callback in menu:
                button = QPushButton(title, self.canvas)
                button.setCursor(Qt.CursorShape.PointingHandCursor)
                button.setStyleSheet(menu_style)
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
            self.settings_btn = QPushButton("⚙", self.canvas)
            self.settings_btn.setToolTip(
                "Configuracion: endpoint IA, voz y apariencia")
            self.settings_btn.clicked.connect(self.open_settings)
            for index, button in enumerate(
                    (self.voice, self.mic, self.attach, self.clear,
                     self.settings_btn)):
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
                ("ACTIVIDAD", 0, "#d11124", "%"),
                ("MEMORIA", 0, "#d89a45", "%"),
                ("PROCESADO", 0, "#e03038", "%"),
                ("RAZONAR", 0, "#39d06b", "%"),
                ("VOZ", 0, "#b9b9c2", "%"),
                ("COMANDOS", 0, "#666975", ""),
            )
            self.dials = []
            for index, (title, value, color, unit) in enumerate(labels):
                dial = Dial(title, value, color, unit, self.canvas)
                self.canvas.place(dial, 326 + index * 119, 728, 98, 105)
                self.dials.append(dial)

            self.plan_label = QLabel("", self.canvas)
            self.plan_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            self.plan_label.setStyleSheet(
                "color:#ffd98a;background:rgba(0,0,0,120);"
                "border-radius:7px;padding:5px;")
            self.plan_label.setWordWrap(True)
            self.canvas.place(self.plan_label, 320, 92, 250, 72)
            self.plan_label.hide()
            self.update_metrics()

            from igris_os.ui.panel_presentation import prepare_presentation, apply_presentation
            prepare_presentation(self, {'background': bg, 'frame': chat_frame, 'header': header,
                                       'send': send, 'stats': stat_frame, 'galaxy_button': galaxy_button}, art)
            apply_presentation(self, self.settings.get('panel_mode', 'modern'))

        def update_metrics(self):
            if not _HAS_PSUTIL:
                return
            try:
                cpu = round(psutil.cpu_percent(interval=None))
                memory = round(psutil.virtual_memory().percent)
            except (OSError, psutil.Error):
                return
            activity = round(max(cpu, getattr(self.galaxy, "ia_activity", 0) * 100))
            reasoning = 85 if self.active_job is not None else round(
                getattr(self.galaxy, "ia_activity", 0) * 100)
            self.dials[0].set_value(activity)
            self.dials[1].set_value(memory)
            self.dials[2].set_value(cpu)
            self.dials[3].set_value(reasoning)
            self.dials[4].set_value(100 if self.voice_enabled else 0)

        def _refresh_backend(self):
            runner = getattr(self, "ai_runner", None)
            if (runner is None or getattr(runner, "busy", False)
                    or getattr(self, "_backend_fetching", False)):
                return
            self._backend_fetching = True

            def _fetch():
                try:
                    backends = runner.backends().get("backends", [])
                    models = runner.models().get("models", ())
                except Exception:
                    backends, models = [], ()
                finally:
                    self._backend_fetching = False
                self.backend_events.put((backends, models))
            threading.Thread(target=_fetch, daemon=True).start()

        def _update_backend_label(self, backends=None, models=None,
                                  last_backend="", last_model=""):
            if backends is not None:
                self._last_backends = backends
            if models is not None:
                self._last_models = tuple(models)
            if last_backend:
                self._last_backend = last_backend
            if last_model:
                self._last_model = last_model
            from igris_os.ui.backend_status import (
                build_status_line, build_status_tooltip)
            endpoint = str(self.settings.get("openai_endpoint", ""))
            self.backend_label.setText("IA ▸ " + build_status_line(
                getattr(self, "_last_backends", []),
                getattr(self, "_last_models", ()),
                getattr(self, "_last_backend", ""),
                getattr(self, "_last_model", ""),
                endpoint))
            self.backend_label.setToolTip(build_status_tooltip(
                getattr(self, "_last_backends", []), endpoint))

        @resilient_slot
        def submit(self):
            self._submission_stage = "read_prompt"
            objective = self.prompt.toPlainText().strip()
            if not objective:
                return
            if not self._confirm_task_switch(objective):
                return
            self._last_submitted_objective = objective
            self._submission_stage = "ui_prelude"
            self.prompt.clear()
            self.command_count += 1
            self.dials[5].set_value(min(100, self.command_count))
            self.chat.append(f"\n[USUARIO] {objective}")
            self._submission_stage = "memory"
            if self.memory is not None:
                try:
                    self.memory.remember(
                        "chat", {"role": "user", "text": objective}, verified=True)
                except Exception:
                    pass
            self._submission_stage = "programming_followup"
            from igris_os.application.intent_classifier import classify_intent
            decision = classify_intent(objective)
            from igris_os.application.mission_router import neural_image_action
            neural = neural_image_action(objective)
            if neural is not None:
                if self.kernel is None or self.mission_queue is None:
                    self.finish_message('Servicios inicializando; la imagen aun no se ha creado.', False)
                    return
                plan = ContractualPlan(mission_id='neural-image', objective=objective,
                                       branch=MissionBranch.IMAGE, deliverables=('PNG neuronal verificado',))
                self._on_plan_ready(plan, objective, routed_action=neural)
                return
            if decision.subtype == 'media_creation' and set(decision.normalized.split()) & {
                    'imagen', 'imagenes', 'fotografia', 'ilustracion', 'dibujo'}:
                if self.kernel is None or self.kernel.registry.get('image.generate') is None:
                    self.finish_message(
                        'Esta instalacion no tiene un motor de generacion de imagenes registrado. '
                        'No he generado ni guardado ninguna imagen. El encargo anterior no se ha reanudado.', False)
                    return
            from igris_os.application.programming_followup import programming_followup
            try:
                answer = programming_followup(
                    objective, self.mission_queue, getattr(self, 'runtime', None),
                    active_job_id=self._programming_focus)
            except Exception as exc:
                # La compatibilidad con misiones antiguas nunca puede bloquear
                # la ruta cognitiva principal. El detalle queda auditado.
                try:
                    from igris_os.ui.resilience import log_nonfatal_ui_exception
                    log_nonfatal_ui_exception(self, "programming_followup", exc)
                except Exception:
                    pass
                answer = None
            if answer is not None:
                self._programming_focus = answer.job.id
                self.chat.append('[IGRIS] ' + answer.message)
                if not answer.ready:
                    return
                if self.kernel is None:
                    self.finish_message('Servicios inicializando; tu respuesta sigue pendiente de procesar.', False)
                    return
                if answer.mode == 'dialog':
                    self._handle_programming_result(answer.job, dict(answer.job.result))
                    return
                # Una respuesta a una pregunta de intake pertenece a la MISMA
                # mision. El token del kernel es de un solo uso y la primera
                # fase de intake puede haberlo consumido; renueva un token
                # ligado al mismo objetivo/capacidad ya autorizado, sin abrir
                # una segunda mision ni ampliar permisos.
                from igris_os.application.programming_followup import refresh_continuation_approval
                resumed_payload = refresh_continuation_approval(
                    answer.job, answer.payload, self.kernel.issue_approval)
                try:
                    resumed = self.mission_queue.continue_in_place(answer.job.id, resumed_payload)
                except (KeyError, OSError, ValueError) as exc:
                    self.finish_message('No se pudo continuar el encargo: ' + str(exc), False)
                    return
                self.chat.append('[COLA] Misión ' + resumed.id[:8] + ' reanudada · mismo encargo')
                if self._uses_samadmin() and resumed.payload.get('__approval'):
                    request_id = resumed.payload['__approval']
                    try:
                        self.mission_queue.await_supervision(resumed.id, request_id)
                    except (KeyError, OSError, ValueError) as exc:
                        self.finish_message('No se pudo autorizar la continuacion: ' + str(exc), False)
                        return
                    self._samadmin_requests[request_id] = resumed.id
                    self.chat.append('[SAMADMIN] Continuación ' + request_id[:12] + ' pendiente para la misma misión.')
                    return
                self.dispatch_next()
                return
            # Entradas estructurales que no deben llegar al LLM. Un checksum
            # aislado sirve para verificar un archivo, no es una orden; y una
            # ruta aislada solo puede completar una mision que la estuviera
            # esperando. Esto evita respuestas inventadas tipo "ORDEN DEL
            # USUARIO: C:\\..." cuando se ha perdido el estado.
            from igris_os.application.assistant import standalone_sha256
            checksum = standalone_sha256(objective)
            if checksum:
                self.chat.append('[IGRIS] Ese texto es un SHA-256, no una orden. '
                                 'Usalo para comprobar la integridad del ZIP; no necesito que me lo envies para continuar un proyecto.')
                return
            if (self.assistant is not None and
                    self.assistant._is_conversation(objective.casefold())):
                self._submit_conversation(objective)
                return
            # Ruta principal: el núcleo cognitivo recibe también rutas aisladas
            # para poder resolverlas contra una aclaración pendiente. No deben
            # rechazarse antes de consultar el estado conversacional.
            if self.cognitive is not None:
                self._submission_stage = "cognitive_dispatch"
                self._submit_cognitive(objective)
                return

            # Sólo en modo fallback (sin Cognitive Core) una ruta aislada que no
            # pertenezca a una misión pendiente se rechaza como insuficiente.
            from igris_os.application.programming_followup import is_standalone_local_path
            if is_standalone_local_path(objective):
                self.chat.append('[IGRIS] He recibido una ruta local, pero no hay una mision de programacion '
                                 'esperando una ruta. Indica primero que proyecto quieres continuar o que debo hacer con esa carpeta.')
                return

            from igris_os.application.game_resume import is_resume_request
            from igris_os.application.programming_intent import programming_action
            from igris_os.application.mission_router import godot_templates_action
            from igris_os.application.host_routing import host_action
            if (not is_resume_request(objective) and
                    not (godot_templates_action(objective) or host_action(objective))):
                work = programming_action(objective, getattr(self, 'attachments', ()),
                    self.mission_queue.recent(1000) if self.mission_queue else (), self.runtime)
                if work:
                    if self.kernel is None:
                        self.finish_message('Servicios inicializando; el encargo aun no se ha iniciado.', False)
                        return
                    from igris_os.application.mission_queue import QueuedMission
                    job = QueuedMission('work', objective, 'capability', work.capability, work.payload)
                    plan = ContractualPlan(mission_id='work', objective=objective,
                        branch=MissionBranch.PROGRAMMING, deliverables=(objective,))
                    self._on_plan_ready(plan, objective, retry_job=job)
                    return
            from igris_os.application.mission_followup import mission_followup
            followup = mission_followup(objective, self.mission_queue)
            if followup is not None:
                self.chat.append("[IGRIS] " + followup.message)
                if followup.intent == "notify":
                    if not hasattr(self, "_notify_jobs"):
                        self._notify_jobs = set()
                    self._notify_jobs.add(followup.job.id)
                elif followup.intent == "retry":
                    original = followup.job
                    plan = ContractualPlan(mission_id="retry", objective=original.objective,
                                           branch=MissionBranch.GENERAL, deliverables=(original.objective,))
                    self._on_plan_ready(plan, original.objective, retry_job=original)
                elif followup.intent == "resume":
                    if self.kernel is None:
                        self.chat.append("[IGRIS] Servicios inicializando; la reanudacion no se ha enviado al chat.")
                        return
                    try:
                        from igris_os.application.game_resume import resolve_game_resume
                        from igris_os.application.mission_queue import QueuedMission
                        original, payload = resolve_game_resume(objective, followup.job, self.runtime)
                        resume_job = QueuedMission("resume", original, "capability", "games.godot.resume", payload)
                        plan = ContractualPlan(mission_id="resume", objective=original,
                                               branch=MissionBranch.GAMES, deliverables=(original,))
                        self._on_plan_ready(plan, original, retry_job=resume_job)
                    except (OSError, ValueError) as exc:
                        self.chat.append("[IGRIS] " + str(exc))
                return
            if self._is_self_diagnostic(objective):
                if self.kernel is None:
                    self.finish_message("Servicios aun inicializando.", False)
                else:
                    self._submit_self_diagnostic(objective)
                return
            if self._is_capability_query(objective):
                if self.kernel is None:
                    self.finish_message("Servicios aun inicializando.", False)
                else:
                    self._submit_capability_query(objective)
                return
            from igris_os.application.mission_router import is_creation_request, godot_templates_action
            from igris_os.application.host_routing import host_action
            if godot_templates_action(objective) or host_action(objective):
                if self.kernel is None:
                    self.finish_message("Servicios aun inicializando.", False)
                    return
                plan = ContractualPlan(mission_id="local-tools", objective=objective,
                                       branch=MissionBranch.GAMES, deliverables=(objective,))
                self._on_plan_ready(plan, objective)
                return
            if is_creation_request(objective):
                if self.assistant is None or self.director is None:
                    self.finish_message(
                        "Servicios aún inicializando, intenta de nuevo en unos segundos.",
                        False)
                    return
                self.status.setText("● Estado: Interpretando encargo de creación")
                self.galaxy.set_busy(True)
                threading.Thread(
                    target=self._plan_in_background, args=(objective,),
                    daemon=True).start()
                return
            if self.assistant is not None and self.assistant._is_conversation(
                    objective.casefold()):
                self._submit_conversation(objective)
                return
            if self.director is None or self.kernel is None:
                self.finish_message("Servicios aún inicializando, intenta de nuevo en unos segundos.", False)
                return
            if self._is_self_diagnostic(objective):
                self._submit_self_diagnostic(objective)
                return
            self.plan_label.setText("MISIÓN: Planificando...")
            self.plan_label.show()
            self.status.setText("● Estado: Planificando")
            self.status.setStyleSheet("color:#ffbe55;background:transparent;")
            self.galaxy.set_busy(True)
            threading.Thread(
                target=self._plan_in_background, args=(objective,),
                daemon=True).start()

        def _submit_cognitive(self, objective: str):
            """Interpreta significado/contexto fuera del hilo Qt y enruta después."""
            self.status.setText("● Estado: Comprendiendo intención")
            self.status.setStyleSheet("color:#ffbe55;background:transparent;")
            self.galaxy.set_busy(True)
            context = self.memory_context()
            attachments = tuple(getattr(self, "attachments", ()))

            def _interpret():
                try:
                    frame = self.cognitive.interpret(objective, context)
                    from igris_os.cognitive import (
                        route_frame, IgrisDecisionGraph, DecisionStatus)
                    from igris_os.application.mission_router import RoutedAction
                    action = route_frame(frame, objective, attachments)
                    decision = IgrisDecisionGraph().evaluate(objective, frame, action)
                    if decision.status == DecisionStatus.BLOCKED and action.kind == "capability":
                        self.intent_events.put((
                            objective, None, None,
                            "El contrato cognitivo o la politica bloquearon la accion antes de ejecutarla."))
                        return
                    if action.kind == "capability" and decision.compiled_payload:
                        action = RoutedAction(
                            action.kind, action.capability, decision.compiled_payload,
                            action.requires_confirmation)
                    self.intent_events.put((objective, frame, action, ""))
                except Exception as exc:
                    self.intent_events.put((objective, None, None, str(exc)))

            threading.Thread(target=_interpret, daemon=True).start()

        def _handle_cognitive_result(self, objective, frame, action, error=""):
            if error or frame is None or action is None:
                self.finish_message(
                    "No se pudo interpretar el encargo de forma segura: " +
                    (error or "resultado cognitivo vacío"), False)
                return
            capability = action.capability if action.kind == "capability" else ""
            try:
                self.cognitive_state.record(objective, frame, capability)
            except Exception:
                pass
            if action.kind == "clarify":
                self.chat.append("[IGRIS] " + str(action.payload.get(
                    "question") or "Necesito una aclaración para continuar."))
                self.galaxy.set_busy(False)
                self.status.setText("● Estado: Esperando aclaración")
                return
            if action.kind == "cancel":
                self.finish_message(str(action.payload.get("message") or "Operación cancelada."), True)
                return
            if action.kind == "chat":
                self._submit_conversation(objective)
                return
            branch = MissionBranch.GENERAL
            if frame.domain == "programming":
                branch = MissionBranch.PROGRAMMING
            elif frame.domain == "games":
                branch = MissionBranch.GAMES
            plan = ContractualPlan(
                mission_id="cognitive", objective=objective, branch=branch,
                deliverables=(frame.goal,))
            self._on_plan_ready(plan, objective, routed_action=action)

        def _submit_conversation(self, objective: str):
            """Envia charla breve sin pasar por el planificador de misiones."""
            self.status.setText("● Estado: Conversando")
            self.status.setStyleSheet("color:#55dc76;background:transparent;")
            self.galaxy.set_busy(True)
            from igris_os.ui.response_preferences import preference_context
            profile_context = preference_context(self.settings)

            def _respond():
                try:
                    context = self.memory_context() + self.semantic_context(objective) + profile_context
                    result = self.igrisd.chat(objective, tuple(context))
                    from igris_os.application.assistant import AssistantReply
                    reply = AssistantReply(
                        ok=result.get("ok", False), text=result.get("text", ""),
                        model=result.get("model", ""), tokens=result.get("tokens", 0),
                        backend=result.get("backend", ""),
                        reasoning=result.get("reasoning", ""))
                except Exception as exc:
                    from igris_os.application.assistant import AssistantReply
                    reply = AssistantReply(False, str(exc))
                self.replies.put((None, reply))

            threading.Thread(target=_respond, daemon=True).start()

        @staticmethod
        def _is_self_diagnostic(objective: str) -> bool:
            text = objective.casefold()
            return any(phrase in text for phrase in (
                "autodiagnostico", "autodiagnóstico", "diagnostico de igris",
                "diagnóstico de igris", "estado del sistema", "health check",
            ))

        def _submit_self_diagnostic(self, objective: str):
            self.status.setText("● Estado: Autodiagnóstico")
            self.status.setStyleSheet("color:#55dc76;background:transparent;")
            self.galaxy.set_busy(True)

            def _check():
                try:
                    result = self.kernel.execute(
                        Mission(objective), "system.health", {})
                    from igris_os.application.assistant import AssistantReply
                    reply = AssistantReply(
                        ok=result.ok, text=result.message,
                        model="local", tokens=0)
                except Exception as exc:
                    from igris_os.application.assistant import AssistantReply
                    reply = AssistantReply(False, str(exc), model="local")
                self.replies.put((None, reply))

            threading.Thread(target=_check, daemon=True).start()

        @staticmethod
        def _is_capability_query(objective: str) -> bool:
            return is_capability_query(objective)

        def _submit_capability_query(self, objective: str):
            self.status.setText("● Estado: Consultando capacidades")
            self.status.setStyleSheet("color:#55dc76;background:transparent;")
            self.galaxy.set_busy(True)

            def _check():
                try:
                    result = self.kernel.execute(
                        Mission(objective), "system.capabilities", {})
                    from igris_os.application.assistant import AssistantReply
                    reply = AssistantReply(
                        ok=result.ok,
                        text=result.message,
                        model="local", tokens=0, data=result.data)
                except Exception as exc:
                    from igris_os.application.assistant import AssistantReply
                    reply = AssistantReply(False, str(exc), model="local")
                self.replies.put((None, reply))

            threading.Thread(target=_check, daemon=True).start()

        def _is_greeting(self, text: str) -> bool:
            return is_conversational_input(text)

        def _plan_in_background(self, objective: str):
            try:
                from igris_os.application.mission_router import is_game_creation_request
                if is_game_creation_request(objective):
                    plan = ContractualPlan(mission_id="game-intake", objective=objective,
                                           branch=MissionBranch.GAMES, deliverables=(objective,))
                else:
                    plan = self.director.plan(Mission(objective))
            except Exception:
                plan = ContractualPlan(
                    mission_id="fallback",
                    objective=objective,
                    branch=MissionBranch.GENERAL,
                    deliverables=(objective,))
            # No se puede crear un QTimer sin receptor desde este hilo: el
            # callback quedaría asociado a un hilo sin event loop y la misión
            # desaparecería. ``tick`` consume esta cola en el hilo Qt.
            self.plan_events.put((plan, objective))

        def _on_plan_ready(self, plan, objective: str, retry_job=None, continuation=False, routed_action=None):
            preview = plan.deliverables[:3] if plan.deliverables else (plan.objective,)
            self.plan_label.setText(
                "MISIÓN: " + plan.branch.value.upper() + "\n" +
                " → ".join(preview))
            self.status.setText("● Estado: Procesando")
            self.status.setStyleSheet("color:#ffbe55;background:transparent;")
            try:
                if routed_action is not None:
                    action = routed_action
                elif retry_job is not None:
                    from igris_os.application.mission_router import RoutedAction
                    action = RoutedAction("capability", retry_job.capability,
                                          {k: v for k, v in retry_job.payload.items()
                                           if not k.startswith("__")}, True)
                else:
                    action = self._route_with_plan(plan, objective)
                if action.kind == "capability":
                    payload = dict(action.payload or {})
                    if retry_job is None and action.capability in {"games.godot.scaffold", "project.stage"}:
                        brief = self._collect_creation_brief(
                            objective, payload,
                            kind=("juego" if action.capability ==
                                  "games.godot.scaffold" else "aplicación"))
                        if brief is None:
                            self.finish_message("Creación cancelada.", False)
                            return
                        payload.update(brief)
                    if action.capability == "sales.plan":
                        sales = self._collect_sales_brief()
                        if sales is None:
                            self.finish_message("Plan comercial cancelado.", False)
                            return
                        payload["answers"] = sales
                    answer = QMessageBox.StandardButton.Yes
                    if action.requires_confirmation and not continuation:
                        prompt = (
                            "Se buscara el paquete oficial de plantillas para tu version exacta de Godot. "
                            "Si hace falta, se descargara en esta carpeta y se comprobara su hash. "
                            "La descarga puede ocupar cientos de MB. ¿Continuar?"
                            if action.capability == "games.godot.templates.install" else
                            "IGRIS creara y verificara archivos en un workspace aislado. "
                            "Despues entregara la copia en la carpeta elegida. ¿Continuar?")
                        if action.capability.startswith("host."):
                            from igris_os.application.host_routing import host_confirmation
                            prompt = host_confirmation(action.capability, payload)
                        elif action.capability == 'image.neural_sphere':
                            prompt = ('IGRIS dibujara ' + str(payload['count']) +
                                      ' esfera(s) neuronal(es) y comprobara un PNG en una mision aislada. '
                                      'Es dibujo programatico local, no una imagen generada por un modelo de IA. '
                                      'No descargara modelos ni modificara otros proyectos. ¿Crear la imagen?')
                        elif action.capability == 'programming.mission':
                            prompt = ('Encargo: ' + objective + '\n\nProyecto: ' +
                                str(payload.get('root') or 'nuevo o pendiente de identificar') +
                                '\n\nIGRIS analizara, programara y ejecutara pruebas en una copia. '
                                'Te preguntara solo las decisiones que falten y presentara los cambios '
                                'antes de entregar. ¿Iniciar el trabajo?')
                        elif action.capability == "repository.develop":
                            prompt = (
                                "IGRIS analizará el repositorio y programará primero en una "
                                "copia aislada. Ejecutará sus pruebas y conservará intacto el "
                                "original. Solo si verifica los cambios pedirá una segunda "
                                "autorización para aplicarlos con respaldo y rollback. ¿Continuar?")
                        elif retry_job is not None:
                            prompt = "Reintentar este encargo con sus opciones originales:\n" + objective + "\n¿Continuar?"
                            if action.capability == "games.godot.resume":
                                prompt = ("Reanudar este proyecto:\n" + str(payload["resume_project"]) +
                                          "\nEncargo: " + objective +
                                          "\nSe verificaran los archivos existentes y se trabajara en una copia. "
                                          "La entrega conservara una copia de los archivos que sustituya. ¿Continuar?")
                        answer = QMessageBox.question(
                            self, "Confirmar misión", prompt)
                    if answer != QMessageBox.StandardButton.Yes:
                        self.finish_message("Operación cancelada.", False)
                        return
                    payload["__approval"] = self.kernel.issue_approval(
                        objective, action.capability)
                    job = self.mission_queue.enqueue(
                        objective, "capability", action.capability, payload)
                    if self._uses_samadmin():
                        request_id = payload["__approval"]
                        self.mission_queue.await_supervision(job.id, request_id)
                        self._samadmin_requests[request_id] = job.id
                        self.chat.append(
                            "[SAMADMIN] Solicitud " + request_id[:12] +
                            " pendiente para " + action.capability + ".")
                        self.status.setText("● Estado: Esperando Samadmin")
                        self.status.setStyleSheet("color:#ffbe55;background:transparent;")
                        return
                else:
                    job = self.mission_queue.enqueue(objective, "chat")
                pending = self.mission_queue.summary()["pending"]
                self.chat.append(f"[COLA] Misión {job.id[:8]} registrada · pendientes: {pending}")
            except Exception as exc:
                self.finish_message(f"Error interno: {exc}", False)
                return
            self.dispatch_next()

        def _uses_samadmin(self) -> bool:
            try:
                from igris_os.samadmin import SamadminApprovalAuthority
                return isinstance(self.kernel.approval, SamadminApprovalAuthority)
            except Exception:
                return False

        def _poll_samadmin(self) -> None:
            if not self._samadmin_requests or not self._uses_samadmin():
                return
            now = time.monotonic()
            if now - self._last_samadmin_poll < 1.0:
                return
            self._last_samadmin_poll = now
            authority = self.kernel.approval
            for request_id, job_id in tuple(self._samadmin_requests.items()):
                try:
                    status = authority.client.status(request_id).get("status", "")
                    if status == "approved":
                        self.mission_queue.release_supervision(job_id)
                        self.chat.append("[SAMADMIN] Solicitud " + request_id[:12] + " aprobada.")
                        del self._samadmin_requests[request_id]
                    elif status in {"rejected", "consumed"}:
                        self.mission_queue.finish(
                            job_id, False, "Samadmin " + status + " la solicitud")
                        self.chat.append("[SAMADMIN] Solicitud " + request_id[:12] + " " + status + ".")
                        del self._samadmin_requests[request_id]
                except (ConnectionError, OSError, ValueError):
                    continue

        def _queue_project_delivery(self, staged_job, data: dict) -> None:
            if not bool(data.get("verified")):
                self.chat.append(
                    "[SEGURIDAD] El staging no tiene evidencia verificable; no se entregará.")
                return
            staged = str(data.get("staged_project", "")).strip()
            answers = staged_job.payload.get("answers", {})
            if not staged or not isinstance(answers, dict):
                return
            answer = QMessageBox.question(
                self, "Autorizar entrega verificada",
                "El proyecto superó el staging. IGRIS copiará esta ruta:\n\n"
                + staged +
                "\n\nLa copia no sobrescribirá destinos existentes. ¿Autorizar una vez?")
            if answer != QMessageBox.StandardButton.Yes:
                self.chat.append(
                    "[SEGURIDAD] Entrega cancelada; el staging se conserva para revisión.")
                return
            payload = {
                "objective": staged_job.objective,
                "answers": dict(answers),
                "staged_project": staged,
            }
            payload["__approval"] = self.kernel.issue_approval(
                staged_job.objective, "project.deliver")
            delivery = self.mission_queue.enqueue(
                staged_job.objective, "capability", "project.deliver", payload)
            if self._uses_samadmin():
                request_id = payload["__approval"]
                self.mission_queue.await_supervision(delivery.id, request_id)
                self._samadmin_requests[request_id] = delivery.id
                self.chat.append(
                    "[SAMADMIN] Entrega " + request_id[:12] +
                    " pendiente para el staging verificado.")
            else:
                self.chat.append("[COLA] Entrega " + delivery.id[:8] + " registrada.")

        def _queue_repository_apply(self, staged_job, data: dict) -> None:
            changes = data.get("repository_changes")
            if not bool(data.get("verified")) or not isinstance(changes, dict):
                self.chat.append(
                    "[SEGURIDAD] Los cambios no tienen evidencia verificable; "
                    "el original permanece intacto.")
                return
            required = ("staged_root", "staging_manifest", "changed_files")
            if any(not changes.get(key) for key in required):
                self.chat.append(
                    "[SEGURIDAD] Falta evidencia del staging; el original permanece intacto.")
                return
            original = str(staged_job.payload.get("root", "")).strip()
            if not original:
                return
            answer = QMessageBox.question(
                self, "Aplicar cambios verificados",
                "Las pruebas de la copia aislada han terminado correctamente.\n\n"
                "Repositorio original:\n" + original +
                "\n\nIGRIS comprobará que el original no cambió, creará un respaldo "
                "y aplicará solo los archivos verificados. Si ocurre un fallo, "
                "hará rollback. ¿Autorizar una vez?")
            if answer != QMessageBox.StandardButton.Yes:
                self.chat.append(
                    "[SEGURIDAD] Aplicación cancelada; la copia verificada se conserva.")
                return
            payload = {
                "source_root": original,
                "staged_root": str(changes["staged_root"]),
                "staging_manifest": str(changes["staging_manifest"]),
                "changed_files": list(changes["changed_files"]),
            }
            payload["__approval"] = self.kernel.issue_approval(
                staged_job.objective, "repository.apply_verified")
            delivery = self.mission_queue.enqueue(
                staged_job.objective, "capability",
                "repository.apply_verified", payload)
            if self._uses_samadmin():
                request_id = payload["__approval"]
                self.mission_queue.await_supervision(delivery.id, request_id)
                self._samadmin_requests[request_id] = delivery.id
                self.chat.append(
                    "[SAMADMIN] Aplicación " + request_id[:12] +
                    " pendiente para el repositorio original.")
            else:
                self.chat.append(
                    "[COLA] Aplicación verificada " + delivery.id[:8] +
                    " registrada.")

        def _collect_creation_brief(self, objective: str, payload: dict,
                                    *, kind: str):
            """Recoge las decisiones de entrega antes de generar archivos."""
            from igris_os.application.mission_router import _project_name

            dialog = QDialog(self)
            is_game = kind == "juego"
            dialog.setWindowTitle("Configurar proyecto de " + kind)
            layout = QVBoxLayout(dialog)
            layout.addWidget(QLabel(
                "Indica solo las decisiones que afectan a la entrega."))
            form = QFormLayout()
            name = QLineEdit(str(payload.get("name") or _project_name(objective)))
            delivery = QComboBox()
            if is_game:
                delivery.addItem("Código fuente Godot", "source")
                delivery.addItem("Código fuente y ejecutable Windows", "source_and_exe")
                delivery.setCurrentIndex(1)
            else:
                delivery.addItem("Intentar código Python; entregar solo si verifica", "source")
            acceptance = QLineEdit(
                "El proyecto inicia; tablero 3D animado; reglas de ajedrez funcionales"
                if is_game else
                "La aplicación inicia; función principal operativa; pruebas aprobadas")
            acceptance.setPlaceholderText("Ejemplo: crear tareas; listar tareas; pruebas pasan")
            candidates = (
                Path(os.environ.get("OneDrive", "")) / "Escritorio",
                Path(os.environ.get("OneDrive", "")) / "Desktop",
                Path.home() / "Desktop", Path.home() / "Documents")
            suggested = next((item for item in candidates if item.is_dir()), Path.home())
            destination = QLineEdit(str(suggested))
            browse = QPushButton("Examinar...")
            destination_row = QHBoxLayout()
            destination_row.addWidget(destination)
            destination_row.addWidget(browse)
            shortcut = QCheckBox("Crear acceso directo si se entrega un ejecutable")
            shortcut.setVisible(is_game)
            form.addRow("Nombre:", name)
            form.addRow("Entrega:", delivery)
            form.addRow("Carpeta:", destination_row)
            form.addRow("Debe comprobarse:", acceptance)
            form.addRow("", shortcut)
            layout.addLayout(form)
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok |
                QDialogButtonBox.StandardButton.Cancel)
            layout.addWidget(buttons)

            def choose_destination():
                selected = QFileDialog.getExistingDirectory(
                    dialog, "Selecciona la carpeta de entrega", destination.text())
                if selected:
                    destination.setText(selected)

            browse.clicked.connect(choose_destination)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return None
            root = Path(destination.text()).expanduser()
            if (not name.text().strip() or not root.is_dir() or
                    not acceptance.text().strip()):
                QMessageBox.warning(
                    self, "Configuración incompleta",
                    "Indica nombre, carpeta de entrega y criterios comprobables.")
                return None
            if not is_game:
                return {
                    "answers": {
                        "name": name.text().strip(),
                        "technology": "python",
                        "delivery": str(delivery.currentData()),
                        "destination": str(root.resolve()),
                        "acceptance": acceptance.text().strip(),
                    },
                }
            return {
                "objective": objective,
                "name": name.text().strip(),
                "delivery_type": str(delivery.currentData()),
                "delivery_root": str(root.resolve()),
                "generate_full_code": True,
                "acceptance": acceptance.text().strip(),
                "brief": {
                    "objective": objective,
                    "acceptance": acceptance.text().strip(),
                    "delivery_type": str(delivery.currentData()),
                    "shortcut_requested": is_game and shortcut.isChecked(),
                },
            }

        def _collect_sales_brief(self):
            dialog = QDialog(self)
            dialog.setWindowTitle("Configurar plan comercial")
            layout = QVBoxLayout(dialog)
            layout.addWidget(QLabel(
                "Los cálculos se basan solo en los datos que indiques."))
            form = QFormLayout()
            fields = {}
            labels = (
                ("product", "Producto o servicio:"),
                ("audience", "Cliente objetivo:"),
                ("channel", "Canal inicial:"),
                ("price", "Precio por venta:"),
                ("variable_cost", "Coste variable por venta:"),
                ("fixed_cost", "Costes fijos mensuales:"),
                ("acquisition_budget", "Presupuesto inicial de captación:"),
            )
            for key, label in labels:
                field = QLineEdit("0" if key == "acquisition_budget" else "")
                fields[key] = field
                form.addRow(label, field)
            layout.addLayout(form)
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok |
                QDialogButtonBox.StandardButton.Cancel)
            layout.addWidget(buttons)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return None
            values = {key: field.text().strip() for key, field in fields.items()}
            required = ("product", "audience", "channel", "price",
                        "variable_cost", "fixed_cost")
            if any(not values[key] for key in required):
                QMessageBox.warning(
                    self, "Datos incompletos",
                    "Indica producto, cliente, canal, precio y costes.")
                return None
            return values

        def _route_with_plan(self, plan, objective: str):
            from igris_os.application.mission_router import godot_templates_action
            templates = godot_templates_action(objective)
            if templates:
                return templates
            from igris_os.application.host_routing import host_action
            local = host_action(objective)
            if local:
                return local
            from igris_os.application.programming_intent import programming_action
            work = programming_action(objective, getattr(self, 'attachments', ()))
            if work:
                return work
            from igris_os.application.mission_router import (
                RoutedAction, _programming_language, _dimensions,
                is_game_creation_request, is_programming_creation_request,
                is_sales_request, _project_name, _game_genre,
                repository_action)
            from pathlib import Path as _P
            low = objective.casefold()
            if classify_capability_query(objective):
                return RoutedAction("capability", "system.capabilities",
                                    {"objective": objective})
            if any(phrase in low for phrase in (
                    "herramientas disponibles", "herramientas tienes",
                    "programas instalados")):
                return RoutedAction("capability", "system.tools")
            repository = repository_action(objective, self.attachments)
            if repository:
                return repository
            if is_sales_request(objective):
                return RoutedAction("capability", "sales.plan",
                                    {"objective": objective})
            source = str(_P(self.attachments[0]).resolve()) if self.attachments else ""
            if source and _P(source).is_dir() and any(phrase in low for phrase in (
                    "audita", "auditoria", "autodiagnostico del proyecto",
                    "autodiagnóstico del proyecto", "preflight", "diagnostico tecnico",
                    "diagnóstico técnico")):
                return RoutedAction("capability", "programming.assess",
                                    {"root": source, "objective": objective})
            if source and _P(source).is_dir() and any(phrase in low for phrase in (
                    "propone cambios", "propón cambios", "proponer cambios",
                    "plan de cambios", "que cambiarias", "qué cambiarías")):
                return RoutedAction("capability", "programming.propose",
                                    {"root": source, "objective": objective})
            if any(phrase in low for phrase in (
                    "coordina especialistas", "revisión cruzada",
                    "revision cruzada", "equipo de especialistas")):
                return RoutedAction("capability", "mission.coordinate",
                                    {"objective": objective}, True)
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
            if is_game_creation_request(objective):
                return RoutedAction("capability", "games.godot.scaffold",
                                    {"objective": objective, "name": _project_name(objective),
                                     "genre": _game_genre(low)}, True)
            if (is_programming_creation_request(objective) and
                    _programming_language(low) == "python"):
                return RoutedAction("capability", "project.lead",
                                    {"objective": objective}, True)
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

        def _confirm_task_switch(self, objective):
            from igris_os.application.mission_followup import task_switch_question
            question = task_switch_question(objective, self.mission_queue)
            if question is None:
                return True
            job = question.job
            box = QMessageBox(self)
            box.setWindowTitle('Cambiar de encargo')
            box.setTextFormat(Qt.TextFormat.PlainText)
            box.setText(question.message)
            start_new = box.addButton('Dejar pendiente y empezar nuevo', QMessageBox.ButtonRole.ActionRole)
            keep = box.addButton('Continuar pendiente', QMessageBox.ButtonRole.ActionRole)
            back = box.addButton('Volver', QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(back)
            box.setEscapeButton(back)
            if job.state == 'running':
                start_new.setEnabled(False)
                start_new.setToolTip('No se puede pausar el proceso activo sin un punto seguro')
            self._deciding_task_switch = True
            try:
                box.exec()
            finally:
                self._deciding_task_switch = False
            chosen = box.clickedButton()
            if chosen is start_new:
                try:
                    self.mission_queue.defer(job.id)
                except (OSError, ValueError, KeyError) as exc:
                    self.chat.append('[IGRIS] No se ha cambiado de encargo: ' + str(exc))
                    return False
                self._programming_focus = None
                self.chat.append('[IGRIS] Encargo ' + job.id[:8] +
                                 ' dejado pendiente; sus archivos y estado se conservan. Ahora atiendo la nueva peticion.')
                return True
            if chosen is keep:
                self._programming_focus = job.id if job.capability == 'programming.mission' else None
                self._last_submitted_objective = job.objective
                self.prompt.clear()
                self.chat.append('[IGRIS] Mantengo el encargo ' + job.id[:8] + ': ' + job.objective)
                if job.state in {'awaiting_review', 'awaiting_downloads'} and job.capability == 'programming.mission':
                    self._handle_programming_result(job, dict(job.result))
                elif job.result.get('questions'):
                    self.chat.append('[IGRIS] ' + '\n'.join(job.result['questions']))
                elif job.state == 'failed' and job.capability == 'programming.mission':
                    self.prompt.setPlainText('reanuda ' + job.id)
                    QTimer.singleShot(0, self.submit)
                elif job.state == 'pending':
                    self.dispatch_next()
                else:
                    self.chat.append('[IGRIS] Estado: ' + job.state + '. ' + job.message)
            return False

        def dispatch_next(self):
            try:
                if self._deciding_task_switch or self.active_job is not None or self.mission_queue is None:
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
                        Mission(job.objective, id=job.id), job.capability, job.payload,
                        approval=job.payload.get("__approval"),
                        on_progress=report_progress)
                    self.remember_repository_context(reply, job)
                else:
                    context = self.memory_context() + self.semantic_context(job.objective)
                    if hasattr(self, 'igrisd') and self.igrisd is not None:
                        result = self.igrisd.chat(job.objective, tuple(context) if context else ())
                        from igris_os.application.assistant import AssistantReply
                        reply = AssistantReply(
                            ok=result.get("ok", False),
                            text=result.get("text", ""),
                            model=result.get("model", ""),
                            tokens=result.get("tokens", 0),
                            backend=result.get("backend", ""),
                            reasoning=result.get("reasoning", ""))
                    else:
                        reply = self.assistant.respond(job.objective, context)
            except Exception as exc:
                from igris_os.application.assistant import AssistantReply
                reply = AssistantReply(
                    ok=False, text=f"Error ejecutando misión: {exc}")
            self.replies.put((job.id, reply))

        @resilient_slot
        def tick(self):
            self._poll_samadmin()
            voice_events = getattr(self.voice_engine, 'events', None)
            if voice_events is not None:
                try:
                    self.chat.append('[VOZ] ' + voice_events.get_nowait())
                except queue.Empty:
                    pass
            try:
                backends, models = self.backend_events.get_nowait()
            except queue.Empty:
                backends = models = None
            if backends is not None:
                self._update_backend_label(backends, models)
            if getattr(self, "clock", None) is not None:
                now = datetime.now().strftime("%H:%M:%S")
                if self.clock.text() != now:
                    self.clock.setText(now)
            try:
                objective, frame, action, error = self.intent_events.get_nowait()
            except queue.Empty:
                pass
            else:
                self._handle_cognitive_result(objective, frame, action, error)
            try:
                plan, objective = self.plan_events.get_nowait()
            except queue.Empty:
                pass
            else:
                self._on_plan_ready(plan, objective)
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
            backend = getattr(reply, "backend", "")
            self._update_backend_label(
                last_backend=backend, last_model=model)
            reasoning = getattr(reply, "reasoning", "") or ""
            from igris_os.ui.chat_format import chat_reply_html
            self.chat.append(chat_reply_html(
                text, reasoning=reasoning, model=model,
                backend=backend, ok=ok))
            data = getattr(reply, "data", {})
            matched_job = (self.active_job if job_id is not None and
                           self.active_job is not None and self.active_job.id == job_id else None)
            try:
                if self.voice_enabled:
                    def _speak():
                        spoken = False
                        if self.voice_engine is not None:
                            spoken = self.voice_engine.speak(text)
                        if (not spoken and hasattr(self, 'igrisd')
                                and self.igrisd is not None
                                and getattr(self.voice_engine, 'allow_fallback', True)):
                            self.igrisd.speak(text)
                    threading.Thread(target=_speak, daemon=True).start()
                if hasattr(self, 'igrisd') and self.igrisd is not None:
                    self.igrisd.remember(
                        "chat", {"role": "igris", "text": text,
                                 "ok": bool(getattr(reply, "ok", False))}, verified=True)
                elif self.memory is not None:
                    self.memory.remember(
                        "chat", {"role": "igris", "text": text,
                                 "ok": bool(getattr(reply, "ok", False))}, verified=True)
                if data and matched_job is not None:
                    technical = self.technical_summary(
                        self.active_job.objective, self.active_job.capability,
                        dict(data))
                    if technical:
                        if hasattr(self, 'igrisd') and self.igrisd is not None:
                            self.igrisd.remember("technical", technical, verified=ok)
                        elif self.memory is not None:
                            self.memory.remember("technical", technical, verified=ok)
                if data:
                    rendered = self.render_result(dict(data))
                    if rendered:
                        self.chat.append(rendered)
                    artifact = data.get('artifact')
                    if ok and isinstance(artifact, dict) and artifact.get('media_type') == 'image/png':
                        from igris_os.ui.artifact_viewer import append_artifact
                        append_artifact(self, artifact)
                if (data and matched_job is not None and
                        matched_job.capability == 'programming.mission'):
                    self._handle_programming_result(matched_job, dict(data))
                if (ok and data and matched_job is not None and
                        matched_job.capability == "project.stage"):
                    self._queue_project_delivery(matched_job, dict(data))
                if (ok and data and matched_job is not None and
                        matched_job.capability == "repository.develop"):
                    self._queue_repository_apply(matched_job, dict(data))
            except Exception as exc:
                self.chat.append('[IGRIS] No se pudo completar la presentacion del resultado: ' + str(exc))
            finally:
                if job_id is not None and self.mission_queue is not None:
                    try:
                        self.mission_queue.finish(job_id, ok, text, result=dict(data or {}))
                    except (KeyError, OSError, ValueError) as exc:
                        self.chat.append("[COLA] No se pudo guardar el resultado: " + str(exc))
                if job_id in getattr(self, "_notify_jobs", set()):
                    self._notify_jobs.discard(job_id)
                    self.chat.append("[AVISO] Mision " + job_id[:8] +
                                     (" finalizada: " if ok else " fallida: ") + text)
                    QApplication.alert(self, 0)
                if matched_job is not None:
                    self.active_job = None
                    self.finish_message("", ok)
                elif self.active_job is None:
                    self.finish_message("", ok)
                self.dispatch_next()

        def render_result(self, data):
            return format_result(data)

        def _handle_programming_result(self, job, data):
            if job.objective == self._last_submitted_objective and job.state != 'deferred':
                self._programming_focus = job.id
            """Una o dos respuestas de producto; la aprobacion final ve evidencia."""
            from igris_os.application.mission_queue import QueuedMission
            status = data.get('work_status')
            payload = {k: v for k, v in job.payload.items() if not k.startswith('__')}
            if status == 'needs_input':
                self.chat.append('[IGRIS] Responde aqui en el chat para continuar este encargo. '
                                 'Conservo las preguntas y los archivos de la mision ' + job.id[:8] + '.')
                return
            elif status == 'needs_download_approval':
                requested = data.get('requested_tools', {})
                detail = ', '.join(requested.get('packages', [])) or requested.get('tool', 'dependencias')
                if QMessageBox.question(self, 'Preparar herramientas',
                        'Este encargo necesita: ' + detail +
                        '\nIGRIS descargara herramientas portables oficiales o dependencias de '
                        'los registros de paquetes dentro de su carpeta de trabajo. ¿Autorizar para este encargo?'
                        ) != QMessageBox.StandardButton.Yes:
                    return
                payload['allow_downloads'] = True
            elif status == 'ready_for_review':
                delivery = data.get('work_delivery', {})
                manual = delivery.get('manual_checks', [])
                question = (str(delivery.get('understanding', job.objective)) +
                    '\n\nCopia para probar:\n' + str(delivery.get('staged_root', '')) +
                    '\n\nArchivos cambiados:\n' + '\n'.join(delivery.get('changed_files', [])) +
                    '\n\nDiferencias: ' + str(delivery.get('diff', '')) +
                    '\nInforme: ' + str(delivery.get('report', '')) +
                    ('\nEjecutable comprobado: ' + str(delivery['executable']) if delivery.get('executable') else '') +
                    ('\nDestino solicitado: ' + str(delivery['destination']) if delivery.get('destination') else '') +
                    ('\n\nRevisa en el proyecto:\n' + '\n'.join(manual) if manual else '') +
                    '\n\nLas comprobaciones automaticas pasaron. ¿Aceptas el resultado para entregarlo? '
                    'Pulsa No para indicar una correccion o Cancelar para revisarlo mas tarde.')
                decision = QMessageBox.question(self, 'Revisar resultado programado', question,
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)
                if decision == QMessageBox.StandardButton.Cancel:
                    self.chat.append('[IGRIS] Copia conservada para revision. Su informe permite entregarla despues.')
                    return
                if decision == QMessageBox.StandardButton.No:
                    correction, accepted = QInputDialog.getMultiLineText(self,
                        'Corregir el resultado', '¿Que debo cambiar para que cumpla tu encargo?')
                    if not accepted or not correction.strip():
                        return
                    payload['clarifications'] = list(payload.get('clarifications', [])) + [
                        {'question': 'Correccion del usuario al resultado anterior', 'answer': correction.strip()}]
                else:
                    target = str(delivery.get('destination') or payload.get('destination', ''))
                    if not payload.get('root') and not target:
                        parent = QFileDialog.getExistingDirectory(self, 'Carpeta donde entregar el proyecto')
                        if not parent:
                            return
                        name, accepted = QInputDialog.getText(self, 'Nombre de la carpeta', 'Nombre del proyecto:')
                        if not accepted or not name.strip() or any(c in name for c in '/\\:') or name in {'.', '..'}:
                            return
                        target = str(Path(parent) / name.strip())
                    payload = {'report': delivery['report'], 'destination': target, 'user_accepted': True,
                               'continuation_of': job.id}
                    token = self.kernel.issue_approval(job.objective, 'programming.deliver')
                    payload['__approval'] = token
                    queued = self.mission_queue.enqueue(job.objective, 'capability', 'programming.deliver', payload)
                    if self._uses_samadmin():
                        self.mission_queue.await_supervision(queued.id, token)
                        self._samadmin_requests[token] = queued.id
                    self.chat.append('[COLA] Entrega programada ' + queued.id[:8])
                    return
            else:
                return
            # Answers continue the same objective; never replace it with a short reply.
            if data.get('report'):
                payload['resume_report'] = data['report']
            payload['continuation_of'] = job.id
            followup = QueuedMission('work', job.objective, 'capability', 'programming.mission', payload)
            plan = ContractualPlan(mission_id='work', objective=job.objective,
                branch=MissionBranch.PROGRAMMING, deliverables=(job.objective,))
            self._on_plan_ready(plan, job.objective, retry_job=followup, continuation=True)

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
            if data.get("updated_existing"):
                summary.update(
                    kind="repository_applied", path=str(data.get("project", "")),
                    backup=str(data.get("backup", "")),
                    report=str(data.get("report", "")),
                    files=list(data.get("changed_files", ())))
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
            if ok:
                try:
                    self.cognitive_state.clear_active()
                except Exception:
                    pass
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

        def open_settings(self):
            from igris_os.ui.settings_dialog import SettingsDialog
            from igris_os.ui.settings_store import (
                apply_ai_settings, load_settings, save_settings)
            settings = load_settings(self.runtime)
            dialog = SettingsDialog(settings, self)
            if dialog.exec() != dialog.DialogCode.Accepted:
                return
            save_settings(self.runtime, settings)
            from igris_os.ui.panel_presentation import apply_presentation
            previous_endpoint = self.settings.get('openai_endpoint')
            self.settings = settings
            apply_presentation(self, settings.get('panel_mode', 'modern'))
            endpoint = apply_ai_settings(settings)
            # El subproceso AI arranco con la config anterior: se reinicia
            # para que la nueva deteccion multi-backend surta efecto.
            runner = getattr(self, "ai_runner", None)
            if runner is not None and runner.is_alive() and previous_endpoint != settings.get('openai_endpoint'):
                try:
                    runner.stop()
                    runner.start()
                except Exception:
                    pass
            self.chat.append(
                "\n[SISTEMA] Configuracion guardada. Endpoint IA: " + endpoint)
            self._refresh_backend()

        def response_preferences_changed(self):
            from igris_os.ui.response_preferences import output_limit
            from igris_os.ui.settings_store import save_settings
            self.settings['conversation_agent'] = self.agent_choice.currentData()
            self.settings['resource_mode'] = self.resource_choice.currentData()
            save_settings(self.runtime, self.settings)
            runner = getattr(self, 'ai_runner', None)
            if runner is not None:
                runner.output_token_limit = output_limit(self.settings)

        def _init_services(self):
            try:
                from igris_os.ui.settings_store import (
                    apply_ai_settings, load_settings)
                self.settings = load_settings(self.runtime)
                apply_ai_settings(self.settings)
                self.ai_runner = AIProcessRunner()
                self.ai_runner.start()
                from igris_os.ui.response_preferences import output_limit
                self.ai_runner.output_token_limit = output_limit(self.settings)
                self.igrisd = IgrisDaemon(ai_runner=self.ai_runner)
                process_client = _ProcessAIClient(self.ai_runner)
                self.assistant = AssistantService(client=process_client)
                self.director = self.assistant.director
                from igris_os.cognitive import CognitiveStateStore, SemanticInterpreter
                self.cognitive_state = CognitiveStateStore(
                    self.runtime / "cognitive" / "state.json")
                self.cognitive = SemanticInterpreter(process_client, self.cognitive_state)
                self.kernel = build_igris(self.runtime)
                self.galaxy.set_capabilities(self.kernel.registry.specs())
                self.context_store = RepositoryContextStore(self.runtime)
                self.memory = MemoryStore(self.runtime / "memory" / "chat.db")
                self.mission_queue = MissionQueue(self.runtime / "missions_queue.json")
                from igris_os.ui.artifact_viewer import restore_last_artifact
                restore_last_artifact(self)
                from igris_os.voice.identity import IdentityVoice
                reference = asset_path("igris_voice_identity.wav")
                if reference:
                    self.voice_engine = IdentityVoice(reference, self.runtime / 'voice')
                else:
                    self.voice_engine = WindowsVoice()
                    self.chat.append('[VOZ] Falta igris_voice_identity.wav; se utiliza la voz de Windows.')
                self._refresh_backend()
            except Exception as exc:
                self.chat.append(f"\n[SISTEMA] Error inicializando servicios: {exc}")
            self.dispatch_next()

        def show_properties(self):
            from igris_os.ui.control_center import PropertiesDialog
            PropertiesDialog(self.runtime, self).exec()

        def show_projects(self):
            from igris_os.ui.control_center import ProjectsDialog
            ProjectsDialog(self).exec()

        def show_military(self):
            self.show_properties()

        def show_laboratory(self):
            self.show_projects()

        def closeEvent(self, event):
            if self.voice_engine is not None:
                self.voice_engine.close()
            from igris_os.ai.server import stop_owned_server
            stop_owned_server()
            super().closeEvent(event)

        def toggle_voice(self):
            self.voice_enabled = not self.voice_enabled
            self.dials[4].set_value(100 if self.voice_enabled else 0)
            state = "activada" if self.voice_enabled else "desactivada"
            self.chat.append("\n[VOZ] Voz local " + state + ".")
            if self.voice_engine is None:
                return
            if self.voice_enabled and not getattr(self.voice_engine, 'allow_fallback', True):
                self.chat.append('[VOZ] Sintesis local con igris_voice_identity.wav. '
                                 'La primera frase necesita cargar el modelo.')
                self.voice_engine.speak('IGRIS preparado. Estoy usando mi voz de referencia.')
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
            from igris_os.ui.control_center import AcademyDialog
            AcademyDialog(self.runtime, self).exec()

        def show_integrity(self):
            from igris_os.ui.control_center import IntegrityDialog
            IntegrityDialog(self).exec()

        def reset_view(self):
            cancelled = self.mission_queue.cancel_pending() if self.mission_queue else 0
            self.chat.clear()
            self._artifact_catalog.clear()
            self.attachments.clear()
            self.attachment_label.clear()
            self.plan_label.hide()
            self.prompt.clear()
            self.chat.append(
                "[SISTEMA] Vista reiniciada. Memoria y auditoría conservadas. "
                f"Misiones pendientes canceladas: {cancelled}.")

        def show_memory(self):
            self.show_integrity()

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
            """Devuelve memoria reciente sin permitir que datos antiguos rompan la UI."""
            if self.memory is None:
                return ()
            context = []
            try:
                rows = list(reversed(self.memory.recent("chat", limit=8)))
            except Exception:
                rows = []
            for row in rows:
                try:
                    item = row.get("content", {}) if isinstance(row, dict) else {}
                    if not isinstance(item, dict):
                        continue
                    role = str(item.get("role", "?"))[:40]
                    text = str(item.get("text", ""))[:1000]
                    if text:
                        context.append(role + ": " + text)
                except Exception:
                    continue
            try:
                technical = list(reversed(self.memory.recent("technical", limit=3)))
            except Exception:
                technical = []
            for row in technical:
                try:
                    item = row.get("content", {}) if isinstance(row, dict) else {}
                    if not isinstance(item, dict):
                        continue
                    context.append(
                        "evidencia técnica: " + str(item.get("objective", ""))[:300] +
                        " | " + str(item.get("capability", ""))[:160])
                except Exception:
                    continue
            return tuple(context)

        def semantic_context(self, objective):
            if self.context_store is None:
                return ()
            try:
                rows = self.context_store.retrieve(objective, limit=4)
            except Exception:
                return ()
            result = []
            for item in rows or ():
                if not isinstance(item, dict):
                    continue
                try:
                    result.append(
                        "archivo relevante: " + str(item.get("path", "")) +
                        " — " + str(item.get("excerpt", ""))[:250])
                except Exception:
                    continue
            return tuple(result)

        def pick_files(self):
            paths, _ = QFileDialog.getOpenFileNames(
                self, "Adjuntar archivos a IGRIS")
            self.add_files(paths)

        def add_files(self, paths):
            for path in paths:
                if path and path not in self.attachments:
                    self.attachments.append(path)
            if paths:
                self.attachment_label.setText(' · '.join(Path(path).name for path in self.attachments))
                self.attachment_label.setToolTip('\n'.join(self.attachments))
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
