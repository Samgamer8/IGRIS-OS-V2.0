import json
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelReply:
    ok: bool
    text: str
    model: str
    error: str = ""


class OllamaClient:
    def __init__(self, endpoint: str = "http://127.0.0.1:11434",
                 timeout: float = 120) -> None:
        if not endpoint.startswith(("http://127.0.0.1", "http://localhost")):
            raise ValueError("Ollama debe usar loopback")
        self.endpoint = endpoint.rstrip("/")
        self.timeout = timeout

    def models(self) -> tuple[str, ...]:
        try:
            with urllib.request.urlopen(self.endpoint + "/api/tags", timeout=3) as response:
                data = json.load(response)
            return tuple(item["name"] for item in data.get("models", [])
                         if isinstance(item, dict) and item.get("name"))
        except (OSError, ValueError, urllib.error.URLError):
            return ()

    def generate(self, prompt: str, model: str) -> ModelReply:
        if not prompt.strip() or not model.strip():
            return ModelReply(False, "", model, "Solicitud incompleta")
        body = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
        request = urllib.request.Request(
            self.endpoint + "/api/generate", data=body,
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.load(response)
            text = str(data.get("response", "")).strip()
            return ModelReply(bool(text), text, model,
                              "" if text else "Respuesta vacia")
        except (OSError, ValueError, urllib.error.URLError) as exc:
            return ModelReply(False, "", model, str(exc))
