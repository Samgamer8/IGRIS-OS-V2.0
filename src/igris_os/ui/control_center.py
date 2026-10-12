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


def artifact_summary(path: str) -> dict[str, object]:
    """Analiza un artefacto con ArtifactAnalyzer y devuelve una ficha legible.

    Solo lectura y con evidencia: si algo no se puede determinar, se declara en
    las limitaciones en lugar de inventarlo.
    """
    from igris_os.files import ArtifactAnalyzer
    target = Path(path)
    if not target.is_file():
        raise ValueError("La ruta no es un archivo: " + str(path))
    report = ArtifactAnalyzer().analyze(target)
    lines = [
        f"Archivo: {target.name}",
        f"Tamaño: {report.size / 1024:.1f} KB   ·   SHA256: {report.sha256[:16]}…",
        f"Tipo: {report.kind} — {report.kind_description}",
    ]
    if report.architecture:
        lines.append(f"Arquitectura: {report.architecture} {report.bitness}".rstrip())
    if report.timestamp:
        lines.append(f"Marca de tiempo: {report.timestamp}")
    if report.is_dotnet:
        lines.append("Runtime: .NET (CLR) detectado")
    if report.packer:
        lines.append(f"Empaquetado/instalador: {report.packer}")
    if report.framework:
        lines.append(f"Contenedor: {report.framework}")
    if report.sections:
        lines.append(f"Secciones: {report.sections}")
    if report.notes:
        lines.append("")
        lines.append("Evidencia:")
        lines.extend(f"  · {note}" for note in report.notes)
    if report.urls:
        lines.append("")
        lines.append(f"Endpoints/URLs ({len(report.urls)}):")
        lines.extend(f"  · {url}" for url in report.urls[:15])
    if report.notable_strings:
        lines.append("")
        lines.append("Strings de interés:")
        lines.extend(f"  · {s}" for s in report.notable_strings[:10])
    if report.zip_entries:
        lines.append("")
        lines.append(f"Contenido del paquete ({len(report.zip_entries)} entradas):")
        lines.extend(f"  · {e['name']}" for e in report.zip_entries[:25])
    lines.append("")
    lines.append("Límites del análisis:")
    lines.extend(f"  · {lim}" for lim in report.limitations)
    return {
        "path": str(target), "name": target.name, "kind": report.kind,
        "architecture": report.architecture, "bitness": report.bitness,
        "is_dotnet": report.is_dotnet, "packer": report.packer,
        "framework": report.framework, "urls": list(report.urls),
        "size": report.size, "sha256": report.sha256, "text": "\n".join(lines),
    }


def blueprint_summary(path: str) -> dict[str, object]:
    """Convierte el analisis de un archivo o carpeta en un plan propio.

    No copia ni desensambla: deriva capacidades originales a partir de hechos
    reales (URLs, framework, imports, simbolos) y devuelve un esqueleto de
    codigo con stubs que hay que completar. Pensado para software propio o
    autorizado.
    """
    from igris_os.files import ArtifactAnalyzer, BlueprintBuilder, RepositoryAnalyzer
    target = Path(path)
    builder = BlueprintBuilder()
    if target.is_dir():
        report = RepositoryAnalyzer(target.parent).analyze(target, "")
        blueprint = builder.from_project(report)
    elif target.is_file():
        report = ArtifactAnalyzer().analyze(target)
        blueprint = builder.from_artifact(report)
    else:
        raise ValueError("La ruta no existe: " + str(path))
    caps = blueprint.proposed_capabilities
    lines = [
        f"Objetivo: {blueprint.target}",
        f"Tipo de analisis: {blueprint.target_kind}",
        f"Caracteristicas detectadas: {len(blueprint.features)}",
        "",
        "Capacidades PROPIAS propuestas (inspiradas en lo observado):",
    ]
    if caps:
        lines.extend(f"  · {c['name']} — {c['description']}\n"
                     f"      evidencia: {c['motivation']}" for c in caps)
    else:
        lines.append("  (ninguna caracteristica accionable detectada)")
    lines += [
        "",
        "Como funciona: IGRIS NO copia ni desensambla el objetivo. Propone",
        "capacidades nuevas y un esqueleto (scaffold) con stubs que completas",
        "tu. Cada propuesta enlaza a la evidencia real que la motiva.",
        "",
        "Esqueleto de codigo generado (guárdalo y completa cada TODO):",
        "─" * 60,
        blueprint.scaffold,
    ]
    return {
        "path": str(target), "target_kind": blueprint.target_kind,
        "features": len(blueprint.features),
        "proposed_capabilities": [c["name"] for c in caps],
        "scaffold": blueprint.scaffold, "text": "\n".join(lines),
    }


def deep_diagnostic() -> dict[str, object]:
    """Diagnóstico completo y real del PC y de la salud de IGRIS OS."""
    import igris_os
    root = project_root()
    result: dict[str, object] = {}
    try:
        boot = psutil.boot_time()
        from datetime import datetime as _dt
        result["uptime"] = str(_dt.now() - _dt.fromtimestamp(boot)).split(".")[0]
    except (OSError, ValueError):
        result["uptime"] = "desconocido"
    vm = psutil.virtual_memory()
    result["ram_total_gb"] = round(vm.total / 1024 ** 3, 1)
    result["ram_used_gb"] = round(vm.used / 1024 ** 3, 1)
    result["ram_percent"] = vm.percent
    result["cpu_logical"] = psutil.cpu_count()
    result["cpu_percent"] = psutil.cpu_percent(interval=0.3)
    drives = []
    for part in psutil.disk_partitions():
        if "cdrom" in part.opts:
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
            drives.append({"path": part.mountpoint,
                           "total_gb": round(usage.total / 1024 ** 3, 1),
                           "free_gb": round(usage.free / 1024 ** 3, 1),
                           "percent": usage.percent})
        except OSError:
            continue
    result["drives"] = drives
    try:
        net = psutil.net_io_counters()
        result["net_sent_mb"] = round(net.bytes_sent / 1024 ** 2, 1)
        result["net_recv_mb"] = round(net.bytes_recv / 1024 ** 2, 1)
    except (OSError, AttributeError):
        result["net_sent_mb"] = result["net_recv_mb"] = 0
    procs = []
    for proc in sorted(psutil.process_iter(["name", "memory_percent"]),
                       key=lambda p: p.info.get("memory_percent") or 0,
                       reverse=True)[:8]:
        try:
            procs.append(f"{proc.info['name']} ({(proc.info.get('memory_percent') or 0):.1f}% RAM)")
        except (OSError, KeyError):
            continue
    result["top_processes"] = procs
    result["python"] = platform.python_version()
    result["platform"] = platform.platform()
    result["igris_version"] = getattr(igris_os, "__version__", "5.1.0")
    src = root / "src" / "igris_os"
    result["igris_modules"] = sum(1 for p in src.rglob("*.py")) if src.is_dir() else 0
    tests_dir = root / "tests"
    result["igris_tests"] = sum(1 for p in tests_dir.glob("test_*.py")) if tests_dir.is_dir() else 0
    result["igris_root"] = str(root)
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
        import igris_os
        version = getattr(igris_os, "__version__", "5.1.0")
        form.addRow("Producto", QLabel("IGRIS OS"))
        form.addRow("Versión", QLabel(version))
        form.addRow("Arquitectura", QLabel(platform.machine()))
        form.addRow("Python", QLabel(platform.python_version()))
        form.addRow("Sistema", QLabel(platform.platform()))
        form.addRow("Runtime", QLabel(str(runtime)))
        form.addRow("Proyectos", QLabel(str(projects_directory())))
        try:
            from igris_os.bootstrap import build_igris
            capabilities = len(build_igris(runtime).registry.specs())
            form.addRow("Capacidades", QLabel(str(capabilities)))
        except (OSError, ImportError, ValueError):
            pass
        tabs.addTab(general, "General")
        state = QTextEdit()
        state.setReadOnly(True)
        state.setPlainText(
            "Estado: operativo\n"
            "Interfaz: centro de control animado\n"
            "Seguridad: confirmación para acciones externas\n"
            "Registro: runtime/logs y runtime/audit\n"
            "Análisis de artefactos: reverse.inspect (solo lectura)\n"
            "Análisis de proyectos: reverse.project")
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
        self.list.currentRowChanged.connect(self._show_details)
        layout.addWidget(self.list)
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setPlaceholderText(
            "Selecciona un programa registrado y pulsa «Analizar» para ver su ficha "
            "técnica (tipo, arquitectura, empaquetado, endpoints). Solo lectura.")
        layout.addWidget(self.details)
        row = QHBoxLayout()
        add = QPushButton("Añadir programa…")
        add.clicked.connect(self.add_program)
        remove = QPushButton("Quitar registro")
        remove.clicked.connect(self.remove_program)
        analyze = QPushButton("Analizar (ingeniería inversa)")
        analyze.clicked.connect(self.analyze_selected)
        blueprint = QPushButton("Plan de implementación propio")
        blueprint.setToolTip(
            "Deriva capacidades originales de IGRIS a partir del análisis, con "
            "evidencia y un esqueleto de código. No copia ni desensambla.")
        blueprint.clicked.connect(self.blueprint_selected)
        row.addWidget(add)
        row.addWidget(remove)
        row.addWidget(analyze)
        row.addWidget(blueprint)
        layout.addLayout(row)
        self.refresh()

    def refresh(self):
        self.list.clear()
        for item in self.programs:
            exists = Path(item["path"]).is_file()
            self.list.addItem(f"{'●' if exists else '○'} {item['name']}\n    {item['path']}")

    def _show_details(self, row: int):
        if 0 <= row < len(self.programs):
            self.details.setPlainText(
                f"Registro: {self.programs[row]['name']}\n"
                f"Ruta: {self.programs[row]['path']}\n\n"
                "Pulsa «Analizar» para la ficha técnica de solo lectura.")

    def analyze_selected(self):
        row = self.list.currentRow()
        if not (0 <= row < len(self.programs)):
            self.details.setPlainText("Selecciona primero un programa de la lista.")
            return
        path = self.programs[row]["path"]
        try:
            summary = artifact_summary(path)
        except (OSError, ValueError) as exc:
            self.details.setPlainText(f"No se pudo analizar: {exc}")
            return
        text = summary["text"]
        if summary.get("urls"):
            text += (
                "\n\nPara que IGRIS estudié estas técnicas y proponga su PROPIA "
                "implementación, pídeselo por chat (no clona código: reimplementa "
                "lo que observes aquí).")
        self.details.setPlainText(text)

    def blueprint_selected(self):
        row = self.list.currentRow()
        if not (0 <= row < len(self.programs)):
            self.details.setPlainText(
                "Selecciona primero un programa de la lista.")
            return
        path = self.programs[row]["path"]
        try:
            summary = blueprint_summary(path)
        except (OSError, ValueError) as exc:
            self.details.setPlainText(f"No se pudo generar el plan: {exc}")
            return
        self.details.setPlainText(summary["text"])

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
            self.details.clear()


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
        self._result = deep_diagnostic()

    def _consume(self):
        if self._result is None:
            return
        data, self._result = self._result, None
        lines = [
            "══ DIAGNÓSTICO COMPLETO DEL EQUIPO ══",
            f"Sistema: {data['platform']}",
            f"Tiempo encendido: {data['uptime']}",
            "",
            "── HARDWARE ──",
            f"CPU: {data['cpu_logical']} núcleos lógicos  ·  uso {data['cpu_percent']}%",
            f"RAM: {data['ram_used_gb']} / {data['ram_total_gb']} GB  ({data['ram_percent']}%)",
        ]
        for drive in data.get("drives", []):
            lines.append(
                f"Disco {drive['path']}: {drive['free_gb']} GB libres de "
                f"{drive['total_gb']} GB  ({drive['percent']}% usado)")
        lines += [
            "",
            "── RED ──",
            f"Enviado: {data['net_sent_mb']} MB  ·  Recibido: {data['net_recv_mb']} MB",
            "",
            "── PROCESOS (mayor uso de RAM) ──",
        ]
        lines += [f"  · {p}" for p in data.get("top_processes", [])] or ["  · sin datos"]
        lines += [
            "",
            "── SALUD DE IGRIS OS ──",
            f"Versión: {data['igris_version']}  ·  Python {data['python']}",
            f"Módulos Python: {data['igris_modules']}  ·  Ficheros de test: {data['igris_tests']}",
            f"Raíz del código: {data['igris_root']}",
            "",
            "Nota: diagnóstico de solo lectura. No modifica nada del equipo.",
        ]
        self.output.setPlainText("\n".join(lines))

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
            self._result = {**deep_diagnostic(), "scan_message": message}
        threading.Thread(target=run, daemon=True).start()

