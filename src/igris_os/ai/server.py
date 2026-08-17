"""Gestion del servidor Ollama interno de IGRIS.

IGRIS OS autocontenido: el binario de Ollama vive en .tools/ollama/ (copiado
del instalador, con libs CPU + CUDA; Apache-2.0) y este modulo lo arranca,
comprueba y apaga en loopback. Los modelos siguen en ~/.ollama/models.
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


def is_ollama_running(endpoint: str = DEFAULT_ENDPOINT) -> bool:
    """True si un servidor Ollama responde en el endpoint (loopback)."""
    try:
        with urllib.request.urlopen(endpoint + "/api/tags", timeout=1.5) as resp:
            return resp.status == 200
    except (OSError, ValueError, urllib.error.URLError):
        return False


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
        while time.monotonic() < deadline:
            if self.is_running():
                return True
            time.sleep(0.3)
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
    """Asegura un servidor Ollama en loopback usando el binario interno.

    Con ``auto=False`` (por defecto) solo comprueba; nunca arranca procesos,
    para que las llamadas desde tests o chequeos no lancen nada.
    """
    if is_ollama_running():
        return True
    if not auto:
        return False
    return OllamaServer().start()


def server_status() -> dict:
    exe = _path_ollama()
    running = is_ollama_running()
    return {
        "running": running,
        "internal": bundled_ollama() is not None,
        "executable": str(exe) if exe else None,
        "endpoint": DEFAULT_ENDPOINT,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(server_status(), ensure_ascii=False, indent=2))
