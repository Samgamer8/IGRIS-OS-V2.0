"""Gestion del servidor LLM local (Ollama o LM Studio).

IGRIS OS autocontenido: el binario de Ollama vive en .tools/ollama/ (copiado
del instalador, con libs CPU + CUDA; Apache-2.0) y este modulo lo arranca,
comprueba y apaga en loopback. Tambien soporta LM Studio via API OpenAI.
"""
from __future__ import annotations

import os
import json
import shutil
import subprocess
import time
import urllib.request
from urllib.parse import urlsplit
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
    """Comprueba todos los motores locales admitidos por el cliente."""
    return is_ollama_running() or is_lmstudio_running() or is_openai_running()


def is_openai_running(endpoint: str | None = None) -> bool:
    from igris_os.ai.ollama import _is_loopback_endpoint, _openai_endpoint_from_env

    endpoint = endpoint or _openai_endpoint_from_env()
    if not _is_loopback_endpoint(endpoint):
        return False
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(endpoint + '/v1/models', timeout=1.5) as response:
            data = json.load(response)
            return response.status == 200 and isinstance(data, dict) and isinstance(data.get('data'), list)
    except (OSError, ValueError, urllib.error.URLError):
        return False


def detect_backend() -> str:
    """Devuelve 'ollama', 'lmstudio' o 'none'."""
    if os.environ.get('IGRIS_PREFERRED_BACKEND') == 'openai' and is_openai_running():
        return 'openai'
    if is_ollama_running():
        return "ollama"
    if is_lmstudio_running():
        return "lmstudio"
    if is_openai_running():
        return "openai"
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


class LlamaCppServer(OllamaServer):
    def __init__(self, executable: Path, model: Path, endpoint: str,
                 alias: str = 'qwen2.5-coder:7b', idle_seconds: int = 180):
        from igris_os.ai.ollama import _is_loopback_endpoint

        if not _is_loopback_endpoint(endpoint):
            raise ValueError('El motor nativo debe usar loopback')
        if not alias.strip() or not 30 <= idle_seconds <= 3600:
            raise ValueError('Configuracion nativa invalida')
        self.executable = Path(executable)
        self.model = Path(model)
        self.endpoint = endpoint.rstrip('/')
        self.alias = alias
        self.idle_seconds = idle_seconds
        self._proc = None

    def is_running(self) -> bool:
        return is_openai_running(self.endpoint)

    def start(self, wait: float = 45.0) -> bool:
        if self.is_running():
            return True
        if not self.executable.is_file() or not self.model.is_file():
            return False
        with self.model.open('rb') as model_file:
            if model_file.read(4) != b'GGUF':
                return False
        address = urlsplit(self.endpoint)
        command = [str(self.executable), '--model', str(self.model), '--alias', self.alias,
                   '--host', address.hostname, '--port', str(address.port or 80),
                   '--ctx-size', '4096', '--parallel', '1', '--n-gpu-layers', '99',
                   '--cache-type-k', 'q8_0', '--cache-type-v', 'q8_0', '--flash-attn', 'on',
                   '--threads', str(min(os.cpu_count() or 4, 8)),
                   '--sleep-idle-seconds', str(self.idle_seconds), '--no-webui',
                   '--cors-origins', self.endpoint, '--no-cors-credentials']
        log = _PROJECT_ROOT / 'runtime/logs/native_inference.log'
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open('a', encoding='utf-8') as output:
            self._proc = subprocess.Popen(command, stdout=output, stderr=output,
                                          creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        deadline = time.monotonic() + wait
        while time.monotonic() < deadline:
            if self._proc.poll() is not None:
                return False
            if self.is_running():
                return True
            time.sleep(0.2)
        self.stop()
        return False


def ensure_ollama_server(auto: bool = False) -> bool:
    """Asegura un servidor LLM en loopback (Ollama o LM Studio).

    Con ``auto=False`` (por defecto) solo comprueba; nunca arranca procesos,
    para que las llamadas desde tests o chequeos no lancen nada.

    Mantiene una referencia global al servidor para evitar procesos huerfanos.
    """
    global _GLOBAL_SERVER
    native_executable = os.environ.get('IGRIS_NATIVE_EXECUTABLE', '').strip()
    native_model = os.environ.get('IGRIS_NATIVE_MODEL_PATH', '').strip()
    if os.environ.get('IGRIS_PREFERRED_BACKEND') == 'openai' and native_executable and native_model:
        if is_openai_running():
            return True
        if not auto:
            return False
        if not isinstance(_GLOBAL_SERVER, LlamaCppServer):
            from igris_os.ai.ollama import _openai_endpoint_from_env

            if _GLOBAL_SERVER is not None:
                _GLOBAL_SERVER.stop()
            _GLOBAL_SERVER = LlamaCppServer(
                Path(native_executable), Path(native_model), _openai_endpoint_from_env(),
                os.environ.get('IGRIS_NATIVE_MODEL_ALIAS', 'qwen2.5-coder:7b'),
                int(os.environ.get('IGRIS_NATIVE_IDLE_SECONDS', '180')))
        return _GLOBAL_SERVER.start()
    if is_local_llm_running():
        return True
    if not auto:
        return False
    if _GLOBAL_SERVER is None:
        _GLOBAL_SERVER = OllamaServer()
    return _GLOBAL_SERVER.start()


def stop_owned_server() -> None:
    global _GLOBAL_SERVER
    if _GLOBAL_SERVER is not None:
        _GLOBAL_SERVER.stop()
        _GLOBAL_SERVER = None


def server_status() -> dict:
    from igris_os.ai.ollama import _openai_endpoint_from_env

    exe = _path_ollama()
    ollama_ok = is_ollama_running()
    lmstudio_ok = is_lmstudio_running()
    openai_ok = is_openai_running()
    running = ollama_ok or lmstudio_ok or openai_ok
    backend = "ollama" if ollama_ok else ("lmstudio" if lmstudio_ok else ("openai" if openai_ok else "none"))
    if os.environ.get('IGRIS_PREFERRED_BACKEND') == 'openai' and openai_ok:
        backend = 'openai'
    endpoint = (DEFAULT_ENDPOINT if backend == 'ollama' else
                LMSTUDIO_ENDPOINT if backend == 'lmstudio' else _openai_endpoint_from_env())
    return {
        "running": running,
        "backend": backend,
        "internal": backend == 'ollama' and bundled_ollama() is not None,
        "executable": (str(exe) if exe and backend == 'ollama' else
                   os.environ.get('IGRIS_NATIVE_EXECUTABLE') if backend == 'openai' else None),
        "endpoint": endpoint if running else DEFAULT_ENDPOINT,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(server_status(), ensure_ascii=False, indent=2))
