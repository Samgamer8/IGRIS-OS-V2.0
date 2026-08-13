from igris_os.voice import WindowsVoice


def test_empty_speech_is_rejected():
    assert not WindowsVoice().speak("  ")


def test_voice_service_exposes_local_operations():
    voice = WindowsVoice()
    assert callable(voice.speak)
    assert callable(voice.listen)
