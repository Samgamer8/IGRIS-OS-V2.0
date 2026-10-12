from __future__ import annotations

import json
import os
from pathlib import Path
import threading
import uuid

from PyQt6.QtCore import QThread, QTimer, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
    QPushButton, QVBoxLayout,
)

from igris_os.evolution.dual_debate import DEBATE_PROMPT, run_repository_debate


DEFAULT_REPOSITORIES = (
    "https://github.com/danielmeppiel/awesome-ai-native",
    "https://github.com/Yuan-ManX/ai-game-devtools",
    "https://github.com/simoninithomas/awesome-ai-tools-for-game-dev",
)


class SharedDebateView(QPlainTextEdit):
    """Live, read-only transcript embedded in each IGRIS control panel."""
    new_session = pyqtSignal()

    def __init__(self, runtime: Path, parent=None):
        super().__init__(parent)
        self.shared_root = shared_debate_root(runtime)
        self.active_path = self.shared_root / "active.json"
        self.current_log: Path | None = None
        self._run_id = ""
        self._offset = 0
        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setPlaceholderText(
            "La conversación de ambas IGRIS aparecerá aquí al iniciar el estudio.")
        self.monitor = QTimer(self)
        self.monitor.timeout.connect(self.refresh_shared_log)
        self.monitor.start(600)
        self.refresh_shared_log()

    def refresh_shared_log(self):
        try:
            active = json.loads(self.active_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        run_id = str(active.get("run_id", ""))
        raw_log = str(active.get("log", ""))
        if raw_log:
            candidate = Path(raw_log)
            try:
                if candidate.resolve().parent != self.shared_root.resolve():
                    return
            except OSError:
                return
            log_path = candidate
        else:
            log_path = None
        if run_id and run_id != self._run_id:
            self._run_id = run_id
            self.current_log = log_path
            self._offset = 0
            self.clear()
            self.appendPlainText(
                f"=== DEBATE COMPARTIDO · sesión {run_id} ===\n"
                "Los mensajes de IGRIS OS e IGRIS OS híbrido se muestran en orden.")
            self.new_session.emit()
        if not self.current_log or not self.current_log.is_file():
            return
        try:
            with self.current_log.open("r", encoding="utf-8") as handle:
                handle.seek(self._offset)
                lines = handle.readlines()
                self._offset = handle.tell()
        except OSError:
            return
        for line in lines:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            self._render_event(event)

    def _render_event(self, event: dict):
        kind = event.get("type")
        if kind == "status":
            state = str(event.get("state", ""))
            if state in {"reading_index", "independent_read", "debating", "finalizing", "complete", "blocked", "stopped"}:
                label = f"\n[ESTADO · {state}] {event.get('text', '')}"
                if event.get("progress"):
                    label += " · " + str(event["progress"])
                self.appendPlainText(label)
        elif kind == "sources":
            self.appendPlainText("\n=== FUENTES LEÍDAS ===")
            for source in event.get("manifest", []):
                self.appendPlainText(
                    f"{source['source']} · {source['repository']} · rama {source['branch']} · "
                    f"{source['commit'][:12]} · {source['characters_read']} caracteres · "
                    f"{len(source['files_read'])} archivos")
        elif kind == "reading_note":
            self.appendPlainText(
                f"\n=== LECTURA INDIVIDUAL · {event.get('persona')} · "
                f"bloque {event.get('progress')} ===\n{event.get('text', '')}\n"
                f"[IDs citados: {', '.join(event.get('citations', [])) or 'ninguno'}; "
                f"IDs inválidos: {', '.join(event.get('invalid_citations', [])) or 'ninguno'}]")
        elif kind == "turn":
            self.appendPlainText(
                f"\n=== TURNO {event.get('index')} · {event.get('persona')} ===\n"
                f"{event.get('text', '')}\n[IDs existentes: "
                f"{', '.join(event.get('citations', [])) or 'ninguno'}; inválidos: "
                f"{', '.join(event.get('invalid_citations', [])) or 'ninguno'}]")
        elif kind == "plan":
            self.appendPlainText(
                f"\n=== PLAN DE {event.get('persona')} ===\n{event.get('text', '')}\n"
                f"[IDs citados: {', '.join(event.get('citations', [])) or 'ninguno'}]")


def shared_debate_root(runtime: Path) -> Path:
    """Return the same user-level transcript directory from both installations."""
    one_drive = os.environ.get("OneDrive")
    candidates = []
    if one_drive:
        candidates.extend([Path(one_drive) / "Escritorio", Path(one_drive) / "Desktop"])
    candidates.extend([
        Path.home() / "OneDrive" / "Escritorio",
        Path.home() / "OneDrive" / "Desktop",
        Path.home() / "Escritorio",
        Path.home() / "Desktop",
    ])
    for desktop in candidates:
        if desktop.is_dir():
            return desktop / "IGRIS OS - Debate compartido"
    return Path(runtime) / "shared_debates"


def _acquire_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(b"\0")
        handle.flush()
    handle.seek(0)
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle


def _release_lock(handle) -> None:
    if handle is None:
        return
    try:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass
    handle.close()


class DebateWorker(QThread):
    finished_run = pyqtSignal(str)

    def __init__(self, client, model, urls, prompt, log_path,
                 stop_path, pause_path, active_path, run_id, lock_handle):
        super().__init__()
        self.client = client
        self.model = model
        self.urls = urls
        self.prompt = prompt
        self.log_path = log_path
        self.stop_path = stop_path
        self.pause_path = pause_path
        self.active_path = active_path
        self.run_id = run_id
        self.lock_handle = lock_handle

    def _stop_requested(self) -> bool:
        return self.stop_path.exists()

    def _paused(self) -> bool:
        return self.pause_path.exists()

    def _on_event(self, event: dict) -> None:
        if event.get("type") == "status":
            self._write_active(event.get("state", "running"), event.get("text", ""))

    def _write_active(self, state: str, text: str = "") -> None:
        payload = {"run_id": self.run_id, "log": str(self.log_path),
                   "state": state, "text": text}
        temporary = self.active_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        temporary.replace(self.active_path)

    def run(self) -> None:
        try:
            result = run_repository_debate(
                self.client, self.urls, log_path=self.log_path, model=self.model,
                max_turns=None, prompt=self.prompt,
                should_stop=self._stop_requested, is_paused=self._paused,
                on_event=self._on_event)
            state = str(result.get("state", "complete"))
        except Exception as exc:
            state = "blocked"
            from igris_os.evolution.dual_debate import _event
            _event(self.log_path, {"type": "status", "state": state,
                                   "text": f"No se pudo completar el debate: {exc}"}, self._on_event)
        finally:
            self.pause_path.unlink(missing_ok=True)
            self.stop_path.unlink(missing_ok=True)
            self._write_active(state if "state" in locals() else "blocked")
            _release_lock(self.lock_handle)
            self.finished_run.emit(state if "state" in locals() else "blocked")


class DebateDialog(QDialog):
    def __init__(self, client, model: str, runtime: Path, parent=None):
        super().__init__(parent)
        self.client = client
        self.model = model
        self.shared_root = shared_debate_root(runtime)
        self.active_path = self.shared_root / "active.json"
        self.lock_path = self.shared_root / "active.lock"
        self.current_log: Path | None = None
        self._offset = 0
        self._run_id = ""
        self.worker: DebateWorker | None = None
        self._closing = False

        self.setWindowTitle("IGRIS · Estudio y debate compartido")
        self.resize(720, 430)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMinimizeButtonHint)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Controles de la sesión. La transcripción en vivo aparece en la pestaña «Debate compartido» "
            "de ambos paneles. Minimiza esta ventana para observarla."))
        layout.addWidget(QLabel("Repositorios (uno por línea; solo se leen documentos Markdown):"))
        self.repositories = QPlainTextEdit("\n".join(DEFAULT_REPOSITORIES))
        self.repositories.setMaximumHeight(90)
        layout.addWidget(self.repositories)
        layout.addWidget(QLabel("Objetivo del debate:"))
        self.prompt_edit = QPlainTextEdit(DEBATE_PROMPT)
        self.prompt_edit.setMaximumHeight(115)
        layout.addWidget(self.prompt_edit)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Turnos sin límite · tú decides cuándo detener"))
        self.start_button = QPushButton("Comenzar estudio y debate")
        self.start_button.clicked.connect(self.start_debate)
        controls.addWidget(self.start_button)
        self.pause_button = QPushButton("Pausar")
        self.pause_button.clicked.connect(self.toggle_pause)
        self.pause_button.setEnabled(False)
        controls.addWidget(self.pause_button)
        self.stop_button = QPushButton("Detener")
        self.stop_button.clicked.connect(self.request_stop)
        self.stop_button.setEnabled(False)
        controls.addWidget(self.stop_button)
        layout.addLayout(controls)

        self.status = QLabel("Preparado. La verificación de citas comprueba IDs y rutas; no demuestra por sí sola la verdad de una afirmación.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.transcript = QPlainTextEdit()
        self.transcript.setReadOnly(True)
        self.transcript.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.path_label = QLabel(f"Registro compartido: {self.shared_root}")
        self.path_label.setWordWrap(True)
        layout.addWidget(self.path_label)

        self.monitor = QTimer(self)
        self.monitor.timeout.connect(self.refresh_shared_log)
        self.monitor.start(700)
        self.refresh_shared_log()

    def start_debate(self):
        urls = [line.strip() for line in self.repositories.toPlainText().splitlines()
                if line.strip()]
        if not urls:
            QMessageBox.warning(self, "Falta una fuente", "Añade al menos un repositorio público de GitHub.")
            return
        lock = _acquire_lock(self.lock_path)
        if lock is None:
            QMessageBox.information(self, "Debate en curso",
                                    "La otra instalación ya tiene un debate compartido en ejecución. Aquí puedes observarlo.")
            self.refresh_shared_log()
            return
        self.shared_root.mkdir(parents=True, exist_ok=True)
        self._run_id = uuid.uuid4().hex[:12]
        self.current_log = self.shared_root / f"debate_{self._run_id}.jsonl"
        self._offset = 0
        self.transcript.clear()
        self._write_active("starting", "Preparando lectura independiente.")
        stop_path = self.shared_root / f"{self._run_id}.stop"
        pause_path = self.shared_root / f"{self._run_id}.pause"
        self.worker = DebateWorker(
            self.client, self.model, urls, self.prompt_edit.toPlainText().strip(),
            self.current_log, stop_path, pause_path,
            self.active_path, self._run_id, lock)
        self.worker.finished_run.connect(self._worker_finished)
        self.start_button.setEnabled(False)
        self.pause_button.setEnabled(True)
        self.stop_button.setEnabled(True)
        self.worker.start()
        self.showMinimized()

    def _write_active(self, state: str, text: str = ""):
        self.shared_root.mkdir(parents=True, exist_ok=True)
        payload = {"run_id": self._run_id, "log": str(self.current_log or ""),
                   "state": state, "text": text}
        temporary = self.active_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        temporary.replace(self.active_path)

    def toggle_pause(self):
        if not self._run_id:
            return
        pause_path = self.shared_root / f"{self._run_id}.pause"
        if pause_path.exists():
            pause_path.unlink(missing_ok=True)
            self.pause_button.setText("Pausar")
            self.status.setText("Reanudado; continuará después de terminar la respuesta actual.")
            self._write_active("running", "Debate reanudado.")
        else:
            pause_path.touch()
            self.pause_button.setText("Reanudar")
            self.status.setText("Pausa solicitada; se aplicará entre llamadas al modelo.")
            self._write_active("paused", "Pausa solicitada; se aplicará entre llamadas al modelo.")

    def request_stop(self):
        if self._run_id:
            (self.shared_root / f"{self._run_id}.stop").touch()
            self.status.setText("Detención solicitada; se aplicará cuando termine la llamada al modelo en curso.")
            self._write_active("stopping", self.status.text())

    def _worker_finished(self, state: str):
        self.start_button.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.pause_button.setText("Pausar")
        self.status.setText(f"Estado del estudio: {state}.")
        if self._closing:
            self.accept()

    def refresh_shared_log(self):
        try:
            active = json.loads(self.active_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        run_id = str(active.get("run_id", ""))
        log_path = Path(str(active.get("log", ""))) if active.get("log") else None
        if run_id and run_id != self._run_id and self.worker is None:
            self._run_id = run_id
            self.current_log = log_path
            self._offset = 0
            self.transcript.clear()
        state = str(active.get("state", ""))
        worker_running = bool(self.worker and self.worker.isRunning())
        if not worker_running:
            active_run = state in {
                "starting", "reading_index", "independent_read", "debating",
                "turn", "paused", "stopping", "finalizing",
            }
            self.start_button.setEnabled(not active_run)
            self.pause_button.setEnabled(active_run)
            self.stop_button.setEnabled(active_run)
            if active_run:
                pause_path = self.shared_root / f"{run_id}.pause"
                self.pause_button.setText("Reanudar" if pause_path.exists() else "Pausar")
            else:
                self.pause_button.setText("Pausar")
            if state:
                self.status.setText(f"{state}: {active.get('text', '')}")
        if not self.current_log or not self.current_log.is_file():
            return
        try:
            with self.current_log.open("r", encoding="utf-8") as handle:
                handle.seek(self._offset)
                lines = handle.readlines()
                self._offset = handle.tell()
        except OSError:
            return
        for line in lines:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            self._render_event(event)

    def _render_event(self, event: dict):
        kind = event.get("type")
        if kind == "status":
            self.status.setText(str(event.get("text", event.get("state", ""))))
            if event.get("progress"):
                self.status.setText(self.status.text() + " · " + str(event["progress"]))
        elif kind == "sources":
            self.transcript.appendPlainText("=== FUENTES Y COBERTURA ===")
            for source in event.get("manifest", []):
                self.transcript.appendPlainText(
                    f"{source['source']} · {source['repository']} · rama {source['branch']} · "
                    f"{source['commit'][:12]} · {len(source['files_read'])} archivos · "
                    f"{source['characters_read']} caracteres")
                self.transcript.appendPlainText(
                    f"  Cobertura: {source.get('available_file_count', len(source['files_read']))} documentos Markdown detectados; "
                    f"{source.get('omitted_file_count', 0)} omitidos por límites o errores; "
                    f"truncados: {', '.join(source.get('truncated_files', [])) or 'ninguno'}")
                for path in source["files_read"]:
                    self.transcript.appendPlainText("  • " + path)
            self.transcript.appendPlainText("\nÍNDICE DE EVIDENCIAS (ID → repositorio/archivo/líneas):")
            for item in event.get("evidence_index", []):
                self.transcript.appendPlainText(
                    f"  [{item['id']}] {item['repository']}/{item['path']}:{item['lines']}")
        elif kind == "reading_note":
            self.transcript.appendPlainText(
                f"\n=== LECTURA INDIVIDUAL · {event.get('persona')} · "
                f"bloque {event.get('progress')} ===\n{event.get('text', '')}\n"
                f"[IDs citados: {', '.join(event.get('citations', [])) or 'ninguno'}; "
                f"IDs inválidos: {', '.join(event.get('invalid_citations', [])) or 'ninguno'}]")
        elif kind == "turn":
            self.transcript.appendPlainText(
                f"\n=== TURNO {event.get('index')} · {event.get('persona')} ===\n"
                f"{event.get('text', '')}\n[IDs existentes: "
                f"{', '.join(event.get('citations', [])) or 'ninguno'}; inválidos: "
                f"{', '.join(event.get('invalid_citations', [])) or 'ninguno'}]")
        elif kind == "plan":
            self.transcript.appendPlainText(
                f"\n=== PLAN DE {event.get('persona')} ===\n{event.get('text', '')}\n"
                f"[IDs citados: {', '.join(event.get('citations', [])) or 'ninguno'}]")
        elif kind == "sources_index":
            self.transcript.appendPlainText("Índice de evidencias guardado.")

    def closeEvent(self, event):
        if self.worker is not None and self.worker.isRunning():
            if not self._closing:
                self._closing = True
                self.request_stop()
                self.status.setText("Cerrando después de la llamada actual al modelo…")
            event.ignore()
            return
        event.accept()
