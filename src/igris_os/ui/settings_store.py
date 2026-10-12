"""Persistencia de la configuracion del panel (sin dependencias Qt).

Almacena ``runtime/settings.json`` con las preferencias del panel. Hoy el
campo clave es el endpoint OpenAI-compatible (puerto 30000 por defecto):
``apply_ai_settings`` lo traduce a ``IGRIS_OPENAI_ENDPOINT`` y fuerza la
re-deteccion multi-backend para que el cambio surta efecto sin reiniciar.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

SETTINGS_FILENAME = "settings.json"

DEFAULTS: dict[str, Any] = {
    "panel_mode": "modern",
    "openai_endpoint": "http://127.0.0.1:30000",
    "preferred_backend": "",
    "exclusive_backend": False,
    "native_executable": "",
    "native_model_path": "",
    "native_model_alias": "qwen2.5-coder:7b",
    "native_idle_seconds": 180,
    "native_context_size": 0,
}

logger = logging.getLogger(__name__)


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
    except (OSError, ValueError) as exc:
        logger.warning("No se pudo cargar la configuracion de %s: %s", path, exc)
    if settings.get('panel_mode') not in {'modern', 'original'}:
        settings['panel_mode'] = DEFAULTS['panel_mode']
    return settings


def save_settings(runtime_root: Path, settings: dict[str, Any]) -> None:
    """Persiste las preferencias; nunca lanza (fallo de escritura se ignora)."""
    try:
        path = settings_path(runtime_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(settings, indent=2, ensure_ascii=False),
            encoding="utf-8")
    except OSError as exc:
        logger.warning("No se pudo guardar la configuracion: %s", exc)


def apply_ai_settings(settings: dict[str, Any]) -> str:
    """Aplica el endpoint OpenAI-compatible a la capa AI y re-detecta.

    Devuelve el endpoint efectivo (el guardado o el default 30000).
    """
    endpoint = str(settings.get("openai_endpoint") or "").strip()
    if not endpoint:
        endpoint = str(DEFAULTS["openai_endpoint"])
    os.environ["IGRIS_OPENAI_ENDPOINT"] = endpoint
    preferred = str(settings.get('preferred_backend') or '').strip().lower()
    if preferred not in {'', 'ollama', 'lmstudio', 'openai'}:
        raise ValueError('Motor preferido invalido')
    os.environ['IGRIS_PREFERRED_BACKEND'] = preferred
    os.environ['IGRIS_EXCLUSIVE_BACKEND'] = str(bool(settings.get('exclusive_backend', False))).lower()
    for key in ('native_executable', 'native_model_path', 'native_model_alias', 'native_idle_seconds',
                'native_context_size'):
        os.environ['IGRIS_' + key.upper()] = str(settings.get(key, DEFAULTS[key]) or '')
    try:
        from igris_os.ai import ollama as ollama_mod
        ollama_mod.reset_backend_detection()
    except ImportError:
        pass
    return endpoint
