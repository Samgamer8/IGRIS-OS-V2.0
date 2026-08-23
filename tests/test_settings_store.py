"""Persistencia y aplicacion de la configuracion del panel.

El panel guarda sus preferencias en ``runtime/settings.json``; la clave
relevante para la capa AI es el endpoint OpenAI-compatible (puerto 30000
por defecto), que ``apply_ai_settings`` traduce a ``IGRIS_OPENAI_ENDPOINT``
y fuerza la re-deteccion multi-backend.
"""

from __future__ import annotations

import os
from pathlib import Path

from igris_os.ui.settings_store import (
    DEFAULTS, apply_ai_settings, load_settings, save_settings,
    settings_path)


def test_defaults_usan_puerto_30000(tmp_path: Path):
    settings = load_settings(tmp_path)
    assert settings["openai_endpoint"] == "http://127.0.0.1:30000"
    assert settings_path(tmp_path) == tmp_path / "settings.json"


def test_save_y_load_roundtrip(tmp_path: Path):
    save_settings(tmp_path, {"openai_endpoint": "http://127.0.0.1:39999"})
    assert load_settings(tmp_path)["openai_endpoint"] == "http://127.0.0.1:39999"


def test_load_ignora_archivo_corrupto(tmp_path: Path):
    settings_path(tmp_path).write_text("{no json", encoding="utf-8")
    settings = load_settings(tmp_path)
    assert settings["openai_endpoint"] == DEFAULTS["openai_endpoint"]


def test_load_ignora_faltante(tmp_path: Path):
    assert load_settings(tmp_path)["openai_endpoint"] == \
        DEFAULTS["openai_endpoint"]


def test_apply_ai_settings_define_env_y_resetea(monkeypatch, tmp_path: Path):
    from igris_os.ai import ollama as ollama_mod
    monkeypatch.setattr(ollama_mod, "_backend_probed", True)
    endpoint = apply_ai_settings({"openai_endpoint": "http://127.0.0.1:30001"})
    assert endpoint == "http://127.0.0.1:30001"
    assert os.environ.get("IGRIS_OPENAI_ENDPOINT") == "http://127.0.0.1:30001"
    assert ollama_mod._backend_probed is False
    # Restaurar estado global para no contaminar otros tests
    ollama_mod.reset_backend_detection()


def test_apply_ai_settings_con_default_si_vacio(monkeypatch, tmp_path: Path):
    from igris_os.ai import ollama as ollama_mod
    monkeypatch.setattr(ollama_mod, "_backend_probed", True)
    endpoint = apply_ai_settings({})
    assert endpoint == "http://127.0.0.1:30000"
    assert os.environ.get("IGRIS_OPENAI_ENDPOINT") == "http://127.0.0.1:30000"
    ollama_mod.reset_backend_detection()
