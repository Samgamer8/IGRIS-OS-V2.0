"""
IGRIS OS v2.0 - Sistema de logging centralizado.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)-20s | %(message)s"
_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)-20s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_initialized = False


def get_logger(name: str) -> logging.Logger:
    """
    Obtiene un logger configurado. Inicializa el sistema solo una vez.

    Uso:
        logger = get_logger("core.ollama_client")
        logger.info("Iniciando conexion con Ollama")
    """
    global _initialized

    if not _initialized:
        _setup_root_logger()
        _initialized = True

    return logging.getLogger(name)


def _setup_root_logger() -> None:
    """Configura el logger raiz con salida a consola."""
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    if root.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)
    handler.setFormatter(formatter)
    root.addHandler(handler)
