import pytest

from igris_os.ai.server import (
    OllamaServer,
    _path_ollama,
    bundled_ollama,
    is_ollama_running,
    server_status,
    ensure_ollama_server,
)


def test_bundled_ollama_returns_path_when_present():
    bundled = bundled_ollama()
    assert bundled is None or bundled.is_file()


def test_path_ollama_returns_path_or_none():
    result = _path_ollama()
    assert result is None or result.is_file()


def test_is_running_returns_false_on_closed_port():
    assert is_ollama_running("http://127.0.0.1:1") is False


def test_server_status_has_required_keys():
    status = server_status()
    assert isinstance(status, dict)
    assert "running" in status
    assert "internal" in status
    assert isinstance(status["internal"], bool)


def test_server_with_nonexistent_executable_fails():
    server = OllamaServer(
        executable=__import__("pathlib").Path("C:\\nonexistent\\ollama.exe"),
        endpoint="http://127.0.0.1:1",
    )
    assert server.is_running() is False
    assert server.start(wait=0.1) is False


def test_server_stop_does_not_raise():
    server = OllamaServer(endpoint="http://127.0.0.1:1")
    server.stop()
    assert server.is_running() is False


def test_ensure_not_auto_does_not_start():
    assert ensure_ollama_server(auto=False) is False or is_ollama_running()
