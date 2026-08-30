import urllib.error

from igris_os.voice import FishAudioVoice, WindowsVoice
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


def test_voice_hides_powershell_window():
    from igris_os.voice.windows import _powershell_kwargs

    kwargs = _powershell_kwargs()
    assert isinstance(kwargs, dict)
    if hasattr(__import__("subprocess"), "STARTUPINFO"):
        assert "startupinfo" in kwargs


def test_fish_audio_uses_api_key_and_falls_back(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout=0):
        captured["authorization"] = request.get_header("Authorization")
        raise urllib.error.URLError("offline")

    class Fallback:
        def speak(self, text, voice_name=None):
            captured["fallback_text"] = text
            captured["fallback_voice"] = voice_name
            return True

    monkeypatch.setattr("igris_os.voice.fish.urllib.request.urlopen", fake_urlopen)
    voice = FishAudioVoice(api_key="secret", fallback=Fallback())
    assert voice.speak("hola") is True
    assert captured["authorization"] == "Bearer secret"
    assert captured["fallback_text"] == "hola"
