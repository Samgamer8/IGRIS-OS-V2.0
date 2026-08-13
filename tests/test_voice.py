from igris_os.voice import WindowsVoice
from igris_os.voice.windows import POWERSHELL, SPEAK


def test_empty_speech_is_rejected():
    assert not WindowsVoice().speak("  ")


def test_voice_service_exposes_local_operations():
    voice = WindowsVoice()
    assert callable(voice.speak)
    assert callable(voice.listen)
    assert not voice.play_sample(__import__("pathlib").Path("missing.wav"))


def test_voice_uses_safe_male_spanish_pablo_voice():
    assert "Pablo" in SPEAK
    assert "David" not in SPEAK
    assert "Jorge" not in SPEAK
    assert POWERSHELL == "powershell.exe"
