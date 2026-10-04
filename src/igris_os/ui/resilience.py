"""Barreras de resiliencia para callbacks de UI.

Ninguna excepción ordinaria de un slot Qt debe cerrar IGRIS. Las excepciones se
registran y se convierten en un estado visible y recuperable.
"""
from __future__ import annotations

from functools import wraps
from pathlib import Path
import logging
import traceback
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def _log_ui_exception(instance: Any, where: str, exc: BaseException) -> None:
    try:
        runtime = Path(getattr(instance, "runtime", Path.cwd() / "runtime"))
        log_dir = runtime / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        stage = str(getattr(instance, "_submission_stage", "") or "")
        header = where + (f" | stage={stage}" if stage else "")
        text = f"\n=== {header} ===\n{traceback.format_exc()}\n"
        with (log_dir / "ui_errors.log").open("a", encoding="utf-8") as fh:
            fh.write(text)
    except Exception:
        logging.getLogger(__name__).exception("No se pudo registrar el error de UI")

    # La notificación es best-effort y nunca puede provocar una segunda caída.
    try:
        chat = getattr(instance, "chat", None)
        if chat is not None:
            chat.append(
                "\n[SISTEMA] Se ha contenido un error interno de interfaz. "
                "IGRIS sigue abierto. Detalle: runtime/logs/ui_errors.log"
            )
    except Exception:
        pass
    try:
        status = getattr(instance, "status", None)
        if status is not None:
            status.setText("● Estado: Error controlado; sistema disponible")
    except Exception:
        pass
    try:
        galaxy = getattr(instance, "galaxy", None)
        if galaxy is not None:
            galaxy.set_busy(False)
    except Exception:
        pass


def log_nonfatal_ui_exception(instance: Any, where: str, exc: BaseException) -> None:
    """Registra un fallo auxiliar sin interrumpir ni notificar al usuario."""
    try:
        runtime = Path(getattr(instance, "runtime", Path.cwd() / "runtime"))
        log_dir = runtime / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        stage = str(getattr(instance, "_submission_stage", "") or "")
        header = where + (f" | stage={stage}" if stage else "")
        text = (f"\n=== NONFATAL {header} ===\n"
                f"{''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))}\n")
        with (log_dir / "ui_errors.log").open("a", encoding="utf-8") as fh:
            fh.write(text)
    except Exception:
        logging.getLogger(__name__).exception("No se pudo registrar el error auxiliar de UI")


def resilient_slot(func: F) -> F:
    """Convierte una excepción de callback Qt en un fallo controlado."""
    @wraps(func)
    def wrapped(self, *args: Any, **kwargs: Any):
        try:
            return func(self, *args, **kwargs)
        except Exception as exc:
            _log_ui_exception(self, func.__name__, exc)
            return None
    return wrapped  # type: ignore[return-value]
