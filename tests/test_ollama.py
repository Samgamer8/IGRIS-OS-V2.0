import pytest

from igris_os.ai import OllamaClient


def test_ollama_rejects_non_loopback():
    with pytest.raises(ValueError):
        OllamaClient("http://192.168.1.2:11434")


def test_unavailable_ollama_is_controlled():
    assert OllamaClient("http://127.0.0.1:1").models() == ()
