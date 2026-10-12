"""Editor visual de pipelines (lienzo de nodos) de IGRIS OS.

Convierte a IGRIS en una 'IA que crea IAs': arrastras capacidades reales
(las 66 registradas), las conectas por dependencias y defines como los datos
viajan entre nodos con ``{{nodo.data.x}}``. Al ejecutar, delega en
``CapabilityPipeline`` (orden topologico, verificacion, traza).

Todo es local-first y codigo propio (PyQt6 + stdlib). No depende de servicios
web de terceros.
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit,
    QPushButton, QSplitter, QVBoxLayout, QWidget,
)

from igris_os.application.pipeline import (
    CapabilityPipeline, PipelineError, PipelineNode,
)

_DIAG_STYLE = """
QDialog { background: #101418; color: #e6e6e6; }
QListWidget, QPlainTextEdit, QLineEdit, QComboBox {
    background: #161a20; color: #e6e6e6; border: 1px solid #2a2f38;
    border-radius: 6px; selection-background-color: #2f6fbf;
}
QPushButton {
    background: #1e2630; color: #e6e6e6; border: 1px solid #2f6fbf;
    border-radius: 6px; padding: 6px 10px;
}
QPushButton:hover { background: #263241; }
QLabel#title { color: #58a6ff; font-weight: bold; }
"""


class PipelineEditorDialog(QDialog):
    """Lienzo para componer un pipeline de capacidades y ejecutarlo."""

    def __init__(self, pipeline: CapabilityPipeline,
                 capabilities: list[str], executor=None, parent=None) -> None:
        super().__init__(parent)
        self.pipeline = pipeline
        self._capabilities = sorted(capabilities)
        self.setWindowTitle(f"IGRIS — Editor de pipelines: {pipeline.name}")
        self.resize(860, 600)
        self.setStyleSheet(_DIAG_STYLE)
        self._executor = executor  # callable(capability, payload)->result|None
        self._build_ui()
        self._refresh_nodes()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("Lienzo de nodos — compón una 'IA' encadenando capacidades")
        title.setObjectName("title")
        layout.addWidget(title)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # -- panel izquierdo: nodos del grafo ---------------------------
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("Nodos (pasos del pipeline)"))
        self.nodes = QListWidget()
        self.nodes.currentRowChanged.connect(self._node_selected)
        left_layout.addWidget(self.nodes)
        del_btn = QPushButton("Eliminar nodo seleccionado")
        del_btn.clicked.connect(self._delete_node)
        left_layout.addWidget(del_btn)
        splitter.addWidget(left)

        # -- panel derecho: formulario del nodo -------------------------
        right = QWidget()
        form = QFormLayout(right)
        self.id_edit = QLineEdit()
        self.cap_combo = QComboBox()
        self.cap_combo.setEditable(True)
        self.cap_combo.addItems(self._capabilities)
        self.deps_edit = QLineEdit()
        self.deps_edit.setPlaceholderText("nodo1, nodo2 (vacio = sin dependencias)")
        self.payload_edit = QPlainTextEdit()
        self.payload_edit.setPlaceholderText(
            'JSON. Usa {{nodo.data.campo}} para encadenar salidas.')
        form.addRow("ID del nodo", self.id_edit)
        form.addRow("Capacidad", self.cap_combo)
        form.addRow("Depende de", self.deps_edit)
        form.addRow("Payload (JSON)", self.payload_edit)
        add_btn = QPushButton("Añadir / actualizar nodo")
        add_btn.clicked.connect(self._save_node)
        form.addRow(add_btn)
        right.setLayout(form)
        splitter.addWidget(right)

        layout.addWidget(splitter)

        # -- acciones del pipeline --------------------------------------
        row = QHBoxLayout()
        validate_btn = QPushButton("Validar orden y capacidades")
        validate_btn.clicked.connect(self._validate)
        save_btn = QPushButton("Guardar pipeline (JSON)")
        save_btn.clicked.connect(self._save_file)
        run_btn = QPushButton("Ejecutar pipeline")
        run_btn.clicked.connect(self._run)
        row.addWidget(validate_btn)
        row.addWidget(save_btn)
        row.addWidget(run_btn)
        layout.addLayout(row)

        self.status = QLabel("")
        layout.addWidget(self.status)

    # ------------------------------------------------------------------
    # Nodos
    # ------------------------------------------------------------------
    def _refresh_nodes(self) -> None:
        self.nodes.clear()
        for level in self.pipeline.topological_levels_or_none():
            for nid in level:
                node = self.pipeline.nodes[nid]
                deps = ", ".join(node.depends_on) or "—"
                QListWidgetItem(f"{nid}  ·  {node.capability}"
                                + (f"  ·  depende: {deps}" if deps != "—" else ""),
                                self.nodes)

    def _node_selected(self, row: int) -> None:
        if row < 0:
            return
        ids = list(self.pipeline.nodes)
        ordered = [nid for lvl in self.pipeline.topological_levels_or_none()
                   for nid in lvl]
        if not ordered or row >= len(ordered):
            return
        node = self.pipeline.nodes[ordered[row]]
        self.id_edit.setText(node.node_id)
        self.cap_combo.setCurrentText(node.capability)
        self.deps_edit.setText(", ".join(node.depends_on))
        self.payload_edit.setPlainText(
            __import__("json").dumps(node.payload, ensure_ascii=False, indent=2))

    def _save_node(self) -> None:
        import json
        try:
            node_id = self.id_edit.text().strip()
            capability = self.cap_combo.currentText().strip()
            deps = tuple(d.strip() for d in self.deps_edit.text().split(",")
                         if d.strip())
            raw = self.payload_edit.toPlainText().strip() or "{}"
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError("El payload debe ser un objeto JSON")
            node = PipelineNode(node_id, capability, depends_on=deps,
                                payload=payload)
        except (PipelineError, ValueError) as exc:
            QMessageBox.warning(self, "Nodo inválido", str(exc))
            return
        self.pipeline.add_node(node)
        self._refresh_nodes()
        self.status.setText(f"Nodo '{node_id}' guardado.")

    def _delete_node(self) -> None:
        row = self.nodes.currentRow()
        if row < 0:
            return
        ordered = [nid for lvl in self.pipeline.topological_levels_or_none()
                   for nid in lvl]
        if row < len(ordered):
            self.pipeline.nodes.pop(ordered[row], None)
            self._refresh_nodes()

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    def _validate(self) -> None:
        problems = self.pipeline.validate(available=set(self._capabilities))
        if problems:
            QMessageBox.warning(self, "Problemas detectados",
                                "\n".join(problems))
        else:
            QMessageBox.information(self, "Válido",
                                    "El pipeline está bien formado y todas las "
                                    "capacidades existen.")

    def _save_file(self) -> None:
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar pipeline", "pipeline.json", "JSON (*.json)")
        if not path:
            return
        try:
            self.pipeline.save(Path(path))
        except (OSError, PipelineError) as exc:
            QMessageBox.warning(self, "No se pudo guardar", str(exc))
            return
        self.status.setText(f"Guardado en {path}")

    def _run(self) -> None:
        problems = self.pipeline.validate(available=set(self._capabilities))
        if problems:
            QMessageBox.warning(self, "Corrige antes de ejecutar",
                                "\n".join(problems))
            return
        if self._executor is None:
            QMessageBox.warning(
                self, "Sin ejecutor",
                "Abre el editor desde el panel con un kernel conectado para "
                "ejecutar el pipeline.")
            return
        try:
            out = self.pipeline.run(self._executor)
        except PipelineError as exc:
            QMessageBox.warning(self, "Ejecución abortada", str(exc))
            return
        trace = out.get("__trace__", [])
        summary = "\n".join(
            f"{'OK ' if r['ok'] else 'X  '} {r['node']} ({r['capability']}) "
            f"{r.get('message','')}" for r in trace)
        if "__failed_node__" in out:
            QMessageBox.warning(self, "Pipeline detenido",
                                f"Fallo en: {out['__failed_node__']}\n\n{summary}")
        else:
            QMessageBox.information(self, "Pipeline completado", summary)