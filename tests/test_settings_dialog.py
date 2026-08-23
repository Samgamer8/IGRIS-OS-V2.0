import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication

from igris_os.ui.settings_dialog import SettingsDialog


@pytest.fixture(scope="module")
def app():
    app = QApplication.instance() or QApplication([])
    yield app


def test_dialog_ia_tab_tiene_endpoint_por_defecto(app):
    dialog = SettingsDialog({})
    try:
        assert dialog.openai_endpoint.text() == "http://127.0.0.1:30000"
    finally:
        dialog.close()


def test_dialog_ia_tab_carga_endpoint_guardado(app):
    dialog = SettingsDialog({"openai_endpoint": "http://127.0.0.1:39999"})
    try:
        assert dialog.openai_endpoint.text() == "http://127.0.0.1:39999"
    finally:
        dialog.close()


def test_dialog_save_persiste_endpoint(app):
    dialog = SettingsDialog({})
    try:
        dialog.openai_endpoint.setText("http://127.0.0.1:40000")
        dialog._save()
        assert dialog.settings["openai_endpoint"] == "http://127.0.0.1:40000"
    finally:
        dialog.close()


def test_dialog_save_usa_default_si_vacio(app):
    dialog = SettingsDialog({})
    try:
        dialog.openai_endpoint.setText("   ")
        dialog._save()
        assert dialog.settings["openai_endpoint"] == "http://127.0.0.1:30000"
    finally:
        dialog.close()
