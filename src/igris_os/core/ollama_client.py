"""
IGRIS OS v2.0 - Cliente Ollama
==============================

Wrapper HTTP para Ollama local.

Requiere:
    - Ollama ejecutandose (http://localhost:11434)
    - requests >= 2.31
    - Modelo descargado (ej: qwen2.5-coder:7b)
"""

from __future__ import annotations

import requests
from requests.exceptions import ConnectionError, Timeout

from src.igris_os.utils.logger import get_logger

logger = get_logger("core.ollama_client")


class OllamaClient:
    """Cliente HTTP para Ollama. Una instancia por conexion."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5-coder:7b",
        timeout: int = 120,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._session = requests.Session()
        logger.info(f"OllamaClient listo: {self.base_url} | modelo={self.model}")

    def health_check(self) -> bool:
        try:
            resp = self._session.get(f"{self.base_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                modelos = resp.json().get("models", [])
                nombres = [m.get("name", "") for m in modelos]
                logger.info(f"Ollama OK. {len(modelos)} modelos: {nombres}")
                return True
            logger.error(f"Ollama devolvio codigo {resp.status_code}")
            return False
        except ConnectionError:
            logger.error("No se puede conectar a Ollama. Esta ejecutandose?")
            return False
        except Exception as exc:
            logger.exception(f"Error en health_check: {exc}")
            return False

    def list_models(self) -> list[str]:
        try:
            resp = self._session.get(f"{self.base_url}/api/tags", timeout=5)
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]
        except Exception as exc:
            logger.error(f"Error listando modelos: {exc}")
            return []

    def generate(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        mensajes: list[dict] = []
        if system:
            mensajes.append({"role": "system", "content": system})
        mensajes.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": mensajes,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        try:
            resp = self._session.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"].strip()
        except Exception as exc:
            logger.exception(f"Error en generate: {exc}")
            return ""

    def generate_code(
        self,
        task: str,
        language: str = "python",
        temperature: float = 0.2,
    ) -> str:
        system_prompt = (
            f"Eres un programador senior experto en {language}. "
            "Responde SOLO con codigo funcional, sin explicaciones, "
            "sin markdown, sin bloques ```. "
            "El codigo debe ser production-ready con type hints y manejo de errores."
        )
        return self.generate(
            prompt=task,
            system=system_prompt,
            temperature=temperature,
        )

    def explain(self, topic: str) -> str:
        system = (
            "Eres un mentor tecnico. Responde en espanol, "
            "claro, directo y con ejemplos practicos. Maximo 200 palabras."
        )
        return self.generate(prompt=topic, system=system, temperature=0.5)
