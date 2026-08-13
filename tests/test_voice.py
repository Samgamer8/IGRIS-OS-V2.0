from igris_os.voice import WindowsVoice
from igris_os.voice.windows import SPEAK


def test_empty_speech_is_rejected():
    assert not WindowsVoice().speak("  ")


def test_voice_service_exposes_local_operations():
    voice = WindowsVoice()
    assert callable(voice.speak)
    assert callable(voice.listen)
    assert not voice.play_sample(__import__("pathlib").Path("missing.wav"))


def test_voice_prefers_jorge_when_installed():
    assert "Jorge|Loquendo" in SPEAK
    assert "es-ES" in SPEAK
