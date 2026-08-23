"""Gestion del servidor LLM local (Ollama o LM Studio).

IGRIS OS autocontenido: el binario de Ollama vive en .tools/ollama/ (copiado
del instalador, con libs CPU + CUDA; Apache-2.0) y este modulo lo arranca,
comprueba y apaga en loopback. Tambien soporta LM Studio via API OpenAI.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_BUNDLED = _PROJECT_ROOT / ".tools" / "ollama" / "ollama.exe"
DEFAULT_ENDPOINT = "http://127.0.0.1:11434"
LMSTUDIO_ENDPOINT = "http://127.0.0.1:1234"

_GLOBAL_SERVER: OllamaServer | None = None


def bundled_ollama() -> Path | None:
    """Ruta al binario Ollama empaquetado en .tools/, o None si no existe."""
    exe = _BUNDLED
    return exe if exe.is_file() else None


def _path_ollama() -> Path | None:
    bundled = bundled_ollama()
    if bundled:
        return bundled
    found = shutil.which("ollama")
    return Path(found) if found else None


def is_lmstudio_running() -> bool:
    """True si un servidor LM Studio responde en localhost:1234."""
    try:
        with urllib.request.urlopen(LMSTUDIO_ENDPOINT + "/v1/models",
                                    timeout=1.5) as resp:
            return resp.status == 200
    except (OSError, ValueError, urllib.error.URLError):
        return False


def is_ollama_running(endpoint: str = DEFAULT_ENDPOINT) -> bool:
    """True si un servidor Ollama responde en el endpoint (loopback)."""
    try:
        with urllib.request.urlopen(endpoint + "/api/tags", timeout=1.5) as resp:
            return resp.status == 200
    except (OSError, ValueError, urllib.error.URLError):
        return False


def is_local_llm_running() -> bool:
    """True si Ollama o LM Studio estan activos."""
    return is_ollama_running() or is_lmstudio_running()


def detect_backend() -> str:
    """Devuelve 'ollama', 'lmstudio' o 'none'."""
    if is_ollama_running():
        return "ollama"
    if is_lmstudio_running():
        return "lmstudio"
    return "none"


class OllamaServer:
    """Servidor Ollama interno: arranque, comprobacion y apagado."""

    def __init__(self, executable: Path | None = None,
                 endpoint: str = DEFAULT_ENDPOINT) -> None:
        self.executable = executable or _path_ollama()
        if not endpoint.startswith(("http://127.0.0.1", "http://localhost")):
            raise ValueError("Ollama debe usar loopback")
        self.endpoint = endpoint.rstrip("/")
        self._proc: subprocess.Popen | None = None

    def is_running(self) -> bool:
        return is_ollama_running(self.endpoint)

    def start(self, wait: float = 25.0) -> bool:
        if self.is_running():
            return True
        if self.executable is None or not Path(self.executable).is_file():
            return False
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        flags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        self._proc = subprocess.Popen(
            [str(self.executable), "serve"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=flags,
        )
        deadline = time.monotonic() + wait
        delay = 0.3
        while time.monotonic() < deadline:
            if self.is_running():
                return True
            time.sleep(delay)
            delay = min(delay * 2, 2.0)
        return False

    def stop(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except OSError:
                pass
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None

    def ensure_running(self) -> bool:
        return self.is_running() or self.start()


def ensure_ollama_server(auto: bool = False) -> bool:
    """Asegura un servidor LLM en loopback (Ollama o LM Studio).

    Con ``auto=False`` (por defecto) solo comprueba; nunca arranca procesos,
    para que las llamadas desde tests o chequeos no lancen nada.

    Mantiene una referencia global al servidor para evitar procesos huerfanos.
    """
    global _GLOBAL_SERVER
    if is_local_llm_running():
        return True
    if not auto:
        return False
    if _GLOBAL_SERVER is None:
        _GLOBAL_SERVER = OllamaServer()
    return _GLOBAL_SERVER.start()


def server_status() -> dict:
    exe = _path_ollama()
    ollama_ok = is_ollama_running()
    lmstudio_ok = is_lmstudio_running()
    running = ollama_ok or lmstudio_ok
    backend = "ollama" if ollama_ok else ("lmstudio" if lmstudio_ok else "none")
    return {
        "running": running,
        "backend": backend,
        "internal": bundled_ollama() is not None,
        "executable": str(exe) if exe else None,
        "endpoint": LMSTUDIO_ENDPOINT if backend == "lmstudio" else DEFAULT_ENDPOINT,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(server_status(), ensure_ascii=False, indent=2))
