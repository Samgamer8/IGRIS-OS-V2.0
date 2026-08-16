from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QIcon, QPalette
from PyQt6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class SettingsDialog(QDialog):
    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Configuración de IGRIS")
        self.setModal(True)
        self.resize(700, 500)
        self._build_ui()

    def _build_ui(self):
        tabs = QTabWidget()
        general_tab = self._build_general_tab()
        appearance_tab = self._build_appearance_tab()
        voice_tab = self._build_voice_tab()
        advanced_tab = self._build_advanced_tab()
        tabs.addTab(general_tab, "General")
        tabs.addTab(appearance_tab, "Apariencia")
        tabs.addTab(voice_tab, "Voz")
        tabs.addTab(advanced_tab, "Avanzado")
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Guardar")
        save.clicked.connect(self._save)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        main = QVBoxLayout()
        main.addWidget(tabs)
        main.addLayout(buttons)
        self.setLayout(main)

    def _build_general_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)
        self.language_combo = QComboBox()
        self.language_combo.addItems(["es", "en", "fr", "de", "pt", "auto"])
        self.language_combo.setCurrentText(self.settings.get("language", "auto"))
        form.addRow("Idioma:", self.language_combo)
        self.template_combo = QComboBox()
        self.template_combo.addItems(["militar", "minimal", "cyber", "claro"])
        self.template_combo.setCurrentText(self.settings.get("template", "militar"))
        form.addRow("Plantilla:", self.template_combo)
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(["1280x720", "1920x1080", "2560x1440", "3840x2160"])
        self.resolution_combo.setCurrentText(self.settings.get("resolution", "1920x1080"))
        form.addRow("Resolución:", self.resolution_combo)
        self.start_max = QCheckBox()
        self.start_max.setChecked(bool(self.settings.get("start_maximized", False)))
        form.addRow("Iniciar maximizado:", self.start_max)
        self.fullscreen_check = QCheckBox()
        self.fullscreen_check.setChecked(bool(self.settings.get("fullscreen", False)))
        form.addRow("Pantalla completa:", self.fullscreen_check)
        return widget

    def _build_appearance_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        form = QFormLayout()
        self.primary_color = QPushButton(self.settings.get("primary_color", "#d11124"))
        self.primary_color.clicked.connect(self._pick_color("primary_color"))
        form.addRow("Color primario:", self.primary_color)
        self.secondary_color = QPushButton(self.settings.get("secondary_color", "#ffd98a"))
        self.secondary_color.clicked.connect(self._pick_color("secondary_color"))
        form.addRow("Color secundario:", self.secondary_color)
        self.background_color = QPushButton(self.settings.get("background_color", "#030307"))
        self.background_color.clicked.connect(self._pick_color("background_color"))
        form.addRow("Fondo:", self.background_color)
        layout.addLayout(form)
        layout.addStretch()
        return widget

    def _build_voice_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)
        self.voice_combo = QComboBox()
        self.voice_combo.addItems(self._list_voices())
        self.voice_combo.setCurrentText(self.settings.get("voice_name", "Voz predeterminada"))
        form.addRow("Voz:", self.voice_combo)
        self.rate_slider = QSlider(Qt.Orientation.Horizontal)
        self.rate_slider.setRange(-10, 10)
        self.rate_slider.setValue(int(self.settings.get("voice_rate", -1)))
        form.addRow("Velocidad:", self.rate_slider)
        self.pitch_slider = QSlider(Qt.Orientation.Horizontal)
        self.pitch_slider.setRange(-10, 10)
        self.pitch_slider.setValue(int(self.settings.get("voice_pitch", 0)))
        form.addRow("Tono:", self.pitch_slider)
        sample_layout = QHBoxLayout()
        self.sample_input = QLineEdit()
        self.sample_input.setPlaceholderText("Texto de muestra...")
        self.sample_btn = QPushButton("Probar")
        self.sample_btn.clicked.connect(self._play_sample)
        sample_layout.addWidget(self.sample_input)
        sample_layout.addWidget(self.sample_btn)
        form.addRow("Prueba:", sample_layout)
        clone_layout = QHBoxLayout()
        self.clone_path = QLineEdit()
        self.clone_path.setPlaceholderText("Ruta a muestra de voz...")
        self.clone_browse = QPushButton("Examinar")
        self.clone_browse.clicked.connect(self._browse_voice_sample)
        self.clone_btn = QPushButton("Escanear y aprender")
        self.clone_btn.clicked.connect(self._clone_voice)
        clone_layout.addWidget(self.clone_path)
        clone_layout.addWidget(self.clone_browse)
        form.addRow("Clonación:", clone_layout)
        form.addRow("", self.clone_btn)
        return widget

    def _build_advanced_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)
        self.context_size = QSpinBox()
        self.context_size.setRange(500, 32000)
        self.context_size.setValue(int(self.settings.get("context_size", 8000)))
        form.addRow("Contexto:", self.context_size)
        self.repair_attempts = QSpinBox()
        self.repair_attempts.setRange(1, 10)
        self.repair_attempts.setValue(int(self.settings.get("repair_attempts", 3)))
        form.addRow("Reparaciones máx.:", self.repair_attempts)
        self.debug_mode = QCheckBox()
        self.debug_mode.setChecked(bool(self.settings.get("debug_mode", False)))
        form.addRow("Modo debug:", self.debug_mode)
        return widget

    def _pick_color(self, key: str):
        def _pick():
            current = QColor(self.settings.get(key, "#000000"))
            color = QColorDialog.getColor(current, self, f"Seleccionar {key}")
            if color.isValid():
                self.settings[key] = color.name()
                if key == "primary_color":
                    self.primary_color.setText(color.name())
                elif key == "secondary_color":
                    self.secondary_color.setText(color.name())
                elif key == "background_color":
                    self.background_color.setText(color.name())
        return _pick

    def _list_voices(self) -> list[str]:
        try:
            script = (
                "Add-Type -AssemblyName System.Speech;"
                "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
                "$s.GetInstalledVoices()|%{$_.VoiceInfo.Name}")
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command", script],
                capture_output=True, text=True, timeout=10, check=False,
            )
            if result.returncode == 0:
                names = [line.strip() for line in result.stdout.splitlines() if line.strip()]
                if names:
                    return names
        except Exception:
            pass
        return ["Voz predeterminada"]

    def _play_sample(self):
        text = self.sample_input.text().strip() or "Hola, soy IGRIS. Esta es una prueba de voz."
        rate = self.rate_slider.value()
        pitch = self.pitch_slider.value()
        voice_name = self.voice_combo.currentText()
        voice_select = ""
        if voice_name and voice_name != "Voz predeterminada":
            escaped_voice = voice_name.replace("'", "''")
            voice_select = f"$s.SelectVoice('{escaped_voice}');"
        script = (
            "Add-Type -AssemblyName System.Speech;"
            f"$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
            f"{voice_select}"
            f"$s.Rate={rate};"
            f"$s.Volume=100;"
            "$s.Speak([Console]::In.ReadToEnd())")
        try:
            subprocess.Popen(
                ["powershell.exe", "-NoProfile", "-Command", script],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, text=True).communicate(text)
        except OSError:
            pass

    def _browse_voice_sample(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar muestra de voz",
            str(Path.home()), "Audio (*.wav *.mp3 *.ogg *.flac)")
        if path:
            self.clone_path.setText(path)

    def _clone_voice(self):
        path = self.clone_path.text().strip()
        if not path or not Path(path).exists():
            return
        if Path(path).suffix.casefold() == ".wav":
            try:
                import wave
                with wave.open(str(path), "rb") as wf:
                    if wf.getnchannels() == 0:
                        raise ValueError("Archivo WAV vacío")
            except Exception as exc:
                QMessageBox.warning(self, "Voz", f"El archivo WAV no es válido: {exc}")
                return
        try:
            import shutil
            dest = Path(self.settings.get("runtime", "runtime")) / "voice_sample" / Path(path).name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            self.settings["voice_sample"] = str(dest)
            QMessageBox.information(self, "Voz", "Muestra de voz guardada. Se usará para personalizar la salida.")
        except Exception as exc:
            QMessageBox.warning(self, "Voz", f"No se pudo guardar la muestra: {exc}")

    def _save(self):
        self.settings["language"] = self.language_combo.currentText()
        self.settings["template"] = self.template_combo.currentText()
        self.settings["resolution"] = self.resolution_combo.currentText()
        self.settings["fullscreen"] = self.fullscreen_check.isChecked()
        self.settings["start_maximized"] = self.start_max.isChecked()
        self.settings["voice_rate"] = str(self.rate_slider.value())
        self.settings["voice_pitch"] = str(self.pitch_slider.value())
        self.settings["voice_name"] = self.voice_combo.currentText()
        self.settings["context_size"] = str(self.context_size.value())
        self.settings["repair_attempts"] = str(self.repair_attempts.value())
        self.settings["debug_mode"] = str(self.debug_mode.isChecked())
        self.accept()
