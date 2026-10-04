"""Ventanas funcionales del centro de control de IGRIS OS."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

import psutil
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QListWidget, QMessageBox, QPushButton, QTabWidget, QTextEdit, QVBoxLayout,
    QWidget,
)


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def projects_directory() -> Path:
    path = project_root() / "proyectos"
    path.mkdir(parents=True, exist_ok=True)
    return path


def discover_projects() -> list[dict[str, object]]:
    roots = [projects_directory(), project_root() / "runtime" / "missions"]
    found: dict[str, dict[str, object]] = {}
    candidates = list(roots[0].iterdir())
    if roots[1].is_dir():
        candidates.extend(roots[1].glob("*/projects/*"))
    for path in candidates:
        if not path.is_dir():
            continue
        progress = path / "PROGRESS.json"
        status = "Informe disponible" if (path / "VERIFICATION.json").is_file() else "Sin verificación"
        if progress.is_file():
            try:
                data = json.loads(progress.read_text(encoding="utf-8"))
                status = str(data.get("status") or data.get("state") or status)
            except (OSError, ValueError, TypeError):
                status = "Revisión necesaria"
        files = sum(1 for item in path.rglob("*") if item.is_file())
        found[str(path.resolve()).casefold()] = {
            "name": path.name, "path": path.resolve(), "status": status,
            "files": files,
            "modified": datetime.fromtimestamp(path.stat().st_mtime).strftime("%d/%m/%Y %H:%M"),
        }
    return sorted(found.values(), key=lambda item: str(item["modified"]), reverse=True)


def _academy_file(runtime: Path) -> Path:
    return runtime / "academy" / "programs.json"


def load_programs(runtime: Path) -> list[dict[str, str]]:
    path = _academy_file(runtime)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [item for item in data if isinstance(item, dict) and item.get("path")]
    except (OSError, ValueError, TypeError):
        return []


def save_programs(runtime: Path, programs: list[dict[str, str]]) -> None:
    path = _academy_file(runtime)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(programs, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def system_snapshot() -> dict[str, object]:
    root = project_root()
    result: dict[str, object] = {
        "cpu": round(psutil.cpu_percent(interval=0.2)),
        "memory": round(psutil.virtual_memory().percent),
        "disk": round(psutil.disk_usage(str(root.anchor)).percent),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "source": root,
        "defender": "No disponible",
        "signatures": "Desconocidas",
    }
    if os.name == "nt":
        command = [
            "powershell.exe", "-NoProfile", "-Command",
            "Get-MpComputerStatus | Select-Object AntivirusEnabled,RealTimeProtectionEnabled,AntivirusSignatureVersion | ConvertTo-Json -Compress",
        ]
        try:
            completed = subprocess.run(command, capture_output=True, text=True,
                                       timeout=8, creationflags=0x08000000)
            data = json.loads(completed.stdout or "{}")
            enabled = bool(data.get("AntivirusEnabled"))
            realtime = bool(data.get("RealTimeProtectionEnabled"))
            result["defender"] = "Activo" if enabled and realtime else "Revisar protección"
            result["signatures"] = str(data.get("AntivirusSignatureVersion") or "Desconocidas")
        except (OSError, subprocess.SubprocessError, ValueError, TypeError):
            pass
    return result


_DIALOG_STYLE = """
QDialog{background:#07080d;color:#ececf2;} QLabel{color:#dedee8;}
QTabWidget::pane{border:1px solid #7f1729;background:#0b0d14;}
QTabBar::tab{background:#171922;color:#ddd;padding:9px 16px;}
QTabBar::tab:selected{background:#86162b;color:white;}
QPushButton{background:#3b111b;color:#eee;border:1px solid #8e2034;
padding:8px 14px;border-radius:7px;font-weight:600;}
QPushButton:hover{background:#a51d36;border-color:#ff5a73;}
QListWidget,QTextEdit{background:#0b0d13;color:#eee;border:1px solid #651522;
border-radius:8px;padding:7px;}
"""


class PropertiesDialog(QDialog):
    def __init__(self, runtime: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Propiedades de IGRIS OS")
        self.resize(620, 420)
        self.setStyleSheet(_DIALOG_STYLE)
        layout = QVBoxLayout(self)
        tabs = QTabWidget(self)
        general = QWidget()
        form = QFormLayout(general)
        form.addRow("Producto", QLabel("IGRIS OS"))
        form.addRow("Versión", QLabel("5.0.0 RC1"))
        form.addRow("Arquitectura", QLabel(platform.machine()))
        form.addRow("Python", QLabel(platform.python_version()))
        form.addRow("Sistema", QLabel(platform.platform()))
        form.addRow("Runtime", QLabel(str(runtime)))
        form.addRow("Proyectos", QLabel(str(projects_directory())))
        tabs.addTab(general, "General")
        state = QTextEdit()
        state.setReadOnly(True)
        state.setPlainText(
            "Estado: operativo\n"
            "Interfaz: centro de control animado\n"
            "Seguridad: confirmación para acciones externas\n"
            "Registro: runtime/logs y runtime/audit")
        tabs.addTab(state, "Sistema")
        layout.addWidget(tabs)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class ProjectsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("IGRIS — Proyectos")
        self.resize(760, 520)
        self.setStyleSheet(_DIALOG_STYLE)
        self.items: list[dict[str, object]] = []
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Proyectos en ejecución y entregas verificadas"))
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._show_details)
        layout.addWidget(self.list)
        self.details = QLabel("Selecciona un proyecto.")
        self.details.setWordWrap(True)
        layout.addWidget(self.details)
        row = QHBoxLayout()
        refresh = QPushButton("Actualizar")
        refresh.clicked.connect(self.refresh)
        open_folder = QPushButton("Abrir carpeta")
        open_folder.clicked.connect(self.open_selected)
        row.addWidget(refresh)
        row.addWidget(open_folder)
        layout.addLayout(row)
        self.refresh()

    def refresh(self):
        self.items = discover_projects()
        self.list.clear()
        for item in self.items:
            self.list.addItem(f"{item['name']}   ·   {item['status']}   ·   {item['files']} archivos")
        if not self.items:
            self.list.addItem("No hay proyectos registrados todavía")

    def _show_details(self, row: int):
        if 0 <= row < len(self.items):
            item = self.items[row]
            self.details.setText(
                f"Estado: {item['status']}\nModificado: {item['modified']}\nRuta: {item['path']}")

    def open_selected(self):
        row = self.list.currentRow()
        path = self.items[row]["path"] if 0 <= row < len(self.items) else projects_directory()
        os.startfile(str(path))


class AcademyDialog(QDialog):
    def __init__(self, runtime: Path, parent=None):
        super().__init__(parent)
        self.runtime = runtime
        self.programs = load_programs(runtime)
        self.setWindowTitle("IGRIS — Academia e Integraciones")
        self.resize(760, 520)
        self.setStyleSheet(_DIALOG_STYLE)
        layout = QVBoxLayout(self)
        intro = QLabel(
            "Añade programas externos para registrarlos como material de integración o estudio. "
            "IGRIS no los ejecuta automáticamente.")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.list = QListWidget()
        layout.addWidget(self.list)
        row = QHBoxLayout()
        add = QPushButton("Añadir programa…")
        add.clicked.connect(self.add_program)
        remove = QPushButton("Quitar registro")
        remove.clicked.connect(self.remove_program)
        row.addWidget(add)
        row.addWidget(remove)
        layout.addLayout(row)
        self.refresh()

    def refresh(self):
        self.list.clear()
        for item in self.programs:
            exists = Path(item["path"]).is_file()
            self.list.addItem(f"{'●' if exists else '○'} {item['name']}\n    {item['path']}")

    def add_program(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar programa", "",
            "Programas (*.exe *.bat *.cmd *.ps1 *.py);;Todos los archivos (*)")
        if not path:
            return
        resolved = str(Path(path).resolve())
        if any(item["path"].casefold() == resolved.casefold() for item in self.programs):
            return
        self.programs.append({"name": Path(path).stem, "path": resolved,
                              "added": datetime.now().isoformat(timespec="seconds")})
        save_programs(self.runtime, self.programs)
        self.refresh()

    def remove_program(self):
        row = self.list.currentRow()
        if 0 <= row < len(self.programs):
            self.programs.pop(row)
            save_programs(self.runtime, self.programs)
            self.refresh()


class IntegrityDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("IGRIS — Diagnóstico e Integridad")
        self.resize(700, 520)
        self.setStyleSheet(_DIALOG_STYLE)
        layout = QVBoxLayout(self)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)
        row = QHBoxLayout()
        refresh = QPushButton("Actualizar diagnóstico")
        refresh.clicked.connect(self.refresh)
        scan = QPushButton("Análisis rápido con Defender")
        scan.clicked.connect(self.quick_scan)
        row.addWidget(refresh)
        row.addWidget(scan)
        layout.addLayout(row)
        self._result = None
        self._poll = QTimer(self)
        self._poll.timeout.connect(self._consume)
        self._poll.start(150)
        self.refresh()

    def refresh(self):
        self.output.setPlainText("Analizando sistema e integridad…")
        threading.Thread(target=self._collect, daemon=True).start()

    def _collect(self):
        self._result = system_snapshot()

    def _consume(self):
        if self._result is None:
            return
        data, self._result = self._result, None
        self.output.setPlainText(
            f"CPU: {data['cpu']}%\nMemoria: {data['memory']}%\nDisco: {data['disk']}%\n\n"
            f"Microsoft Defender: {data['defender']}\nFirmas: {data['signatures']}\n\n"
            f"Python: {data['python']}\nSistema: {data['platform']}\n"
            f"Código IGRIS: {data['source']}\n\n"
            "Integridad del RC: use MANIFEST.sha256 y SHA256SUMS.txt para verificar el paquete."
            + ("\n\n" + str(data["scan_message"]) if data.get("scan_message") else ""))

    def quick_scan(self):
        if os.name != "nt":
            QMessageBox.information(self, "Antivirus", "Microsoft Defender solo está disponible en Windows.")
            return
        self.output.append("\nSolicitando análisis rápido de Microsoft Defender…")
        def run():
            command = ["powershell.exe", "-NoProfile", "-Command",
                       "Start-MpScan -ScanType QuickScan"]
            try:
                completed = subprocess.run(command, capture_output=True, text=True,
                                           timeout=900, creationflags=0x08000000)
                message = "Análisis rápido finalizado." if completed.returncode == 0 else (
                    "Defender no pudo iniciar el análisis: " + (completed.stderr or "error desconocido"))
            except (OSError, subprocess.SubprocessError) as exc:
                message = "Error al iniciar Defender: " + str(exc)
            self._result = {**system_snapshot(), "scan_message": message}
        threading.Thread(target=run, daemon=True).start()
