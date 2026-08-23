from __future__ import annotations

from igris_os.application import CapabilityRegistry
from igris_os.domain import ActionRisk, CapabilitySpec, ExecutionResult
from igris_os.voice import WindowsVoice


def _voice_set(payload):
    voice = WindowsVoice()
    objective = str(payload.get("objective", "")).strip()
    text = str(payload.get("text", "")).strip()
    if not text:
        text = "Hola, soy IGRIS. Esta es una prueba de voz en español."
    voices = WindowsVoice.get_installed_voices()
    if not voices:
        return ExecutionResult.failure(
            "No hay voces de Windows instaladas para reproducir audio.",
            "VOICE_UNAVAILABLE")
    ok = voice.speak(text)
    if not ok:
        return ExecutionResult.failure(
            "No se pudo iniciar la reproduccion de voz.", "VOICE_FAILED")
    return ExecutionResult.success(
        "Voz reproducida con Windows",
        played=ok, text=text, voices=voices)


def register_voice_capabilities(registry: CapabilityRegistry) -> None:
    registry.register(
        CapabilitySpec("voice.set", "Reproduce texto con voz local",
                       ActionRisk.READ_ONLY, False), _voice_set)
