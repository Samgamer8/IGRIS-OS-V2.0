from __future__ import annotations

from typing import Any, Optional, Protocol, runtime_checkable

from PyQt6.QtWidgets import QTextEdit


@runtime_checkable
class VoiceEngine(Protocol):
    def speak(self, text: str, voice_name: Optional[str] = None) -> Any:
        ...


class ChatController:
    """Wraps a read-only QTextEdit chat widget, centralizing message
    formatting so the panel no longer scatters append calls.

    Mirrors the in-panel prefixes ([USUARIO], [IGRIS], [SISTEMA],
    [PROGRESO], [HERRAMIENTA]) and re-uses the same HTML color scheme.
    append_igris additionally dispatches to the voice engine when enabled.
    """

    OK_COLOR = "#55dc76"
    WARN_COLOR = "#efb74f"

    def __init__(
        self,
        chat_widget: QTextEdit,
        voice_engine: Optional[VoiceEngine] = None,
        settings: Optional[dict[str, Any]] = None,
    ) -> None:
        self.chat = chat_widget
        self.voice_engine = voice_engine
        self.settings: dict[str, Any] = settings if settings is not None else {}
        self.voice_enabled: bool = bool(
            self.settings.get("voice_enabled", True)
        )
        self.tool_statuses: dict[str, str] = {}

    def _safe_append(self, html: str) -> None:
        if self.chat is None:
            return
        try:
            self.chat.append(html)
            self.chat.ensureCursorVisible()
        except RuntimeError:
            pass

    def _speak(self, text: str) -> None:
        if not self.voice_enabled or self.voice_engine is None:
            return
        voice_name = self.settings.get("voice_name")
        try:
            self.voice_engine.speak(text, voice_name)
        except (OSError, ValueError, RuntimeError):
            pass

    def append_user(self, text: str) -> None:
        self._safe_append(f"\n[USUARIO] {text}")

    def append_igris(
        self,
        text: str,
        model: str = "",
        ok: bool = True,
    ) -> None:
        self._speak(text)
        tag = f"[IGRIS · {model}]" if model else "[IGRIS]"
        if not ok:
            tag = f'<span style="color:{self.WARN_COLOR}">{tag}</span>'
        self._safe_append(f"\n{tag} {text}")

    def append_system(self, text: str) -> None:
        self._safe_append(f"\n[SISTEMA] {text}")

    def append_progress(
        self,
        text: str,
        percent: Optional[int] = None,
        job_id: Optional[str] = None,
    ) -> None:
        head = "[PROGRESO]"
        if job_id is not None:
            head = f"[PROGRESO · {job_id[:8]}]"
        if percent is not None:
            head = f"{head} {percent}%"
        self._safe_append(f"\n{head} {text}")

    def append_tool_status(
        self,
        tool: str,
        status: str,
        output: str = "",
        args: str = "",
    ) -> None:
        is_done = status == "done"
        color = self.OK_COLOR if is_done else self.WARN_COLOR
        self.tool_statuses[tool] = status
        label = f'\n[HERRAMIENTA  ● <span style="color:{color}">{status}</span>] {tool}'
        if args:
            label = f"{label}({args[:40]})"
        if output:
            safe_output = str(output).replace("\n", " ")[:200]
            label = f"{label}\n  {safe_output}"
        self._safe_append(label)

    def append_raw(self, text: str) -> None:
        self._safe_append(text)

    def clear(self) -> None:
        if self.chat is not None:
            try:
                self.chat.clear()
            except RuntimeError:
                pass
        self.tool_statuses.clear()

    def set_voice_enabled(self, enabled: bool) -> None:
        self.voice_enabled = bool(enabled)
        self.settings["voice_enabled"] = self.voice_enabled
        state = "activada" if self.voice_enabled else "desactivada"
        self.append_system("Voz local " + state + ".")

    def summary(self) -> dict[str, Any]:
        return {
            "tool_statuses": dict(self.tool_statuses),
            "voice_enabled": self.voice_enabled,
        }