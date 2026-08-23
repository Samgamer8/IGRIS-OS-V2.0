from __future__ import annotations

from .settings_dialog import SettingsDialog


class SettingsPanel:
    def __init__(self, settings: dict, parent=None) -> None:
        self.settings = dict(settings)
        self.parent = parent
        self.dialog = SettingsDialog(self.settings, parent)

    def open(self) -> dict:
        if self.dialog.exec() == self.dialog.DialogCode.Accepted:
            return dict(self.settings)
        return {}

    def apply(self, settings: dict) -> None:
        self.settings = dict(settings)
        self.dialog = SettingsDialog(self.settings, self.parent)
