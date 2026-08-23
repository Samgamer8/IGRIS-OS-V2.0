"""Persistencia de la configuracion del panel (sin dependencias Qt).

Almacena ``runtime/settings.json`` con las preferencias del panel. Hoy el
campo clave es el endpoint OpenAI-compatible (puerto 30000 por defecto):
``apply_ai_settings`` lo traduce a ``IGRIS_OPENAI_ENDPOINT`` y fuerza la
re-deteccion multi-backend para que el cambio surta efecto sin reiniciar.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

SETTINGS_FILENAME = "settings.json"

DEFAULTS: dict[str, Any] = {
    "openai_endpoint": "http://127.0.0.1:30000",
}


def settings_path(runtime_root: Path) -> Path:
    return Path(runtime_root) / SETTINGS_FILENAME


def load_settings(runtime_root: Path) -> dict[str, Any]:
    """Lee las preferencias del panel; devuelve los defaults si no existen."""
    settings: dict[str, Any] = dict(DEFAULTS)
    path = settings_path(runtime_root)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            settings.update({k: v for k, v in data.items() if v is not None})
    except (OSError, ValueError):
        pass
    return settings


def save_settings(runtime_root: Path, settings: dict[str, Any]) -> None:
    """Persiste las preferencias; nunca lanza (fallo de escritura se ignora)."""
    try:
        path = settings_path(runtime_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(settings, indent=2, ensure_ascii=False),
            encoding="utf-8")
    except OSError:
        pass


def apply_ai_settings(settings: dict[str, Any]) -> str:
    """Aplica el endpoint OpenAI-compatible a la capa AI y re-detecta.

    Devuelve el endpoint efectivo (el guardado o el default 30000).
    """
    endpoint = str(settings.get("openai_endpoint") or "").strip()
    if not endpoint:
        endpoint = str(DEFAULTS["openai_endpoint"])
    os.environ["IGRIS_OPENAI_ENDPOINT"] = endpoint
    try:
        from igris_os.ai import ollama as ollama_mod
        ollama_mod.reset_backend_detection()
    except ImportError:
        pass
    return endpoint
