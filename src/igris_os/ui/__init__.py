"""UI package with lazy imports.

Importing lightweight helpers such as ``igris_os.ui.resilience`` must not force
PyQt6 or construct the full GUI. The heavy Qt modules are loaded only when a
public GUI symbol is actually requested.
"""
from __future__ import annotations

from importlib import import_module

__all__ = ["run_cinematic_panel", "run_panel", "SettingsDialog"]


def __getattr__(name: str):
    if name == "run_cinematic_panel":
        return import_module(".cinematic", __name__).run_cinematic_panel
    if name == "run_panel":
        return import_module(".panel", __name__).run_panel
    if name == "SettingsDialog":
        return import_module(".settings_dialog", __name__).SettingsDialog
    raise AttributeError(name)
