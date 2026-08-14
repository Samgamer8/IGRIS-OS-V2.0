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

    def select_embedding_model(self) -> str | None:
        """Elige automaticamente un modelo de embeddings local disponible,
        priorizando los conocidos y validando el primero con una llamada real."""
        available = set(self.models())
        if not available:
            return None
        preferred = ("nomic-embed-text", "mxbai-embed-large",
                     "all-minilm", "bge-m3", "granite-embedding:278m")
        candidates = [name for name in preferred if name in available]
        candidates += [name for name in sorted(available)
                       if any(hint in name for hint in
                              ("embed", "minilm", "bge", "mxbai"))]
        seen: set[str] = set()
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            ok, _ = self.embed([".", "test"], candidate)
            if ok:
                return candidate
        return None

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

    def embed(self, texts: list[str], model: str) -> tuple[bool, list[list[float]]]:
        """Vectoriza textos con un modelo de embeddings local (loopback)."""
        if not texts or not model.strip():
            return False, []
        body = json.dumps({"model": model, "input": texts}).encode()
        request = urllib.request.Request(
            self.endpoint + "/api/embed", data=body,
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.load(response)
            vectors = data.get("embeddings")
            if not isinstance(vectors, list) or not all(
                    isinstance(item, list) for item in vectors):
                return False, []
            return True, [[float(value) for value in item] for item in vectors]
        except (OSError, ValueError, urllib.error.URLError, TypeError):
            return False, []
