import os
from pathlib import Path
import queue
import sys
import threading

from igris_os.application import AssistantService, MissionDirector
from igris_os.domain import Mission


STYLE = """
QWidget { background:#07080c; color:#e9e9ed; font-family:'Segoe UI'; }
#sidebar { background:#090a0e; border-right:1px solid #3b1018; }
QPushButton { text-align:left; padding:13px; border:1px solid transparent; border-radius:8px; }
QPushButton:hover { background:#241016; border-color:#7d1526; }
QTextEdit,QLineEdit { background:#0c0d13; border:1px solid #8f1429; border-radius:10px; padding:10px; }
#mission { border:1px solid #a71931; border-radius:14px; }
#title { font-size:24px; font-weight:700; color:#f1f1f1; }
#accent { color:#e31e3b; font-weight:700; }
"""


def run_panel() -> int:
    try:
        from PyQt6.QtCore import Qt, QTimer
        from PyQt6.QtGui import QIcon, QPixmap
        from PyQt6.QtWidgets import (
            QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit,
            QMainWindow, QPushButton, QTextEdit, QVBoxLayout, QWidget,
        )
    except ImportError as exc:
        raise RuntimeError("PyQt6 no esta instalado") from exc

    class Panel(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("IGRIS OS V2.O — Modo Militar")
            self.resize(1500, 900)
            self.assistant = AssistantService()
            self.replies = queue.Queue()
            bundle = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[3]))
            assets = bundle / "assets"
            icon = assets / "igris_icon_v2.png"
            if icon.exists():
                self.setWindowIcon(QIcon(str(icon)))
            root, layout = QWidget(), QHBoxLayout()
            root.setLayout(layout)
            self.setCentralWidget(root)
            side = QFrame(objectName="sidebar")
            menu = QVBoxLayout(side)
            menu.addWidget(QLabel("IGRIS OS V2.O", objectName="title"))
            for name in ("MODO MILITAR", "MISIONES", "TALLER", "ARCHIVOS",
                         "MULTIMEDIA", "VIDEOJUEGOS", "MEMORIA", "LABORATORIO"):
                menu.addWidget(QPushButton(name))
            menu.addStretch()
            avatar = assets / "igris_avatar_v2.png"
            if avatar.exists():
                portrait = QLabel()
                portrait.setPixmap(QPixmap(str(avatar)).scaled(
                    180, 250, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation))
                portrait.setAlignment(Qt.AlignmentFlag.AlignCenter)
                menu.addWidget(portrait)
            menu.addWidget(QLabel("● NUCLEO OPERATIVO", objectName="accent"))
            layout.addWidget(side, 2)
            center = QFrame(objectName="mission")
            center_box = QVBoxLayout(center)
            center_box.addWidget(QLabel("GALAXIA OPERATIVA", objectName="title"))
            background = assets / "solo_leveling_bg_v2.png"
            if background.exists():
                art = QLabel()
                art.setPixmap(QPixmap(str(background)).scaled(
                    700, 360, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation))
                art.setAlignment(Qt.AlignmentFlag.AlignCenter)
                center_box.addWidget(art)
            self.plan = QTextEdit(readOnly=True)
            self.plan.setPlainText("Sin mision activa. Las ramas y herramientas apareceran aqui.")
            center_box.addWidget(self.plan)
            layout.addWidget(center, 5)
            chat = QFrame(objectName="mission")
            chat_box = QVBoxLayout(chat)
            chat_box.addWidget(QLabel("IGRIS", objectName="title"))
            self.console = QTextEdit(readOnly=True)
            self.console.setPlainText("IGRIS OS V2.O en linea.\nA tus ordenes.")
            chat_box.addWidget(self.console)
            self.order = QLineEdit()
            self.order.setPlaceholderText("Escribe una orden...")
            self.order.returnPressed.connect(self.submit)
            chat_box.addWidget(self.order)
            layout.addWidget(chat, 4)
            self.reply_timer = QTimer(self)
            self.reply_timer.timeout.connect(self.poll_reply)
            self.reply_timer.start(100)

        def submit(self):
            objective = self.order.text().strip()
            if not objective:
                return
            plan = MissionDirector().plan(Mission(objective))
            self.console.append(f"\nUSUARIO: {objective}\nIGRIS: Mision planificada.")
            self.plan.setPlainText(
                f"RAMA: {plan.branch.value.upper()}\n\n" +
                "\n".join(f"{i}. {step}" for i, step in enumerate(plan.steps, 1)))
            self.order.clear()
            self.order.setEnabled(False)
            threading.Thread(target=self.ask_model, args=(objective,),
                             daemon=True).start()

        def ask_model(self, objective):
            self.replies.put(self.assistant.respond(objective))

        def poll_reply(self):
            try:
                reply = self.replies.get_nowait()
            except queue.Empty:
                return
            prefix = f"[{reply.model}] " if reply.model else ""
            self.console.append("\nIGRIS: " + prefix + reply.text)
            self.order.setEnabled(True)
            self.order.setFocus()

    app = QApplication([])
    app.setStyleSheet(STYLE)
    window = Panel()
    window.show()
    if os.environ.get("IGRIS_TEST_GUI") == "1":
        def finish_test():
            screenshot = os.environ.get("IGRIS_TEST_SCREENSHOT")
            if screenshot:
                window.grab().save(screenshot)
            app.quit()
        QTimer.singleShot(500, finish_test)
    return app.exec()
