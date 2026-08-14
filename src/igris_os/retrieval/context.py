import json
from pathlib import Path

from igris_os.retrieval.semantic import SemanticRetriever


class RepositoryContextStore:
    """Persiste el indice semantico de repositorios analizados y permite
    consultar fragmentos relevantes desde la mision contextual del chat."""

    def __init__(self, runtime: Path) -> None:
        self.runtime = Path(runtime).resolve()
        self.directory = self.runtime / "context"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.index_path = self.directory / "repository_context.json"

    def remember(self, root: Path, records) -> None:
        compact = [{"path": item["path"], "symbols": item.get("symbols", []),
                    "excerpt": item.get("text", "")[:600]}
                   for item in records]
        payload = {"root": str(Path(root).resolve()),
                   "records": compact}
        self.index_path.write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def retrieve(self, query: str, limit: int = 8) -> list[dict]:
        if not self.index_path.exists():
            return []
        try:
            payload = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        documents = [{
            "path": item["path"],
            "text": (item["path"] + " " + " ".join(item.get("symbols", [])) +
                     " " + item.get("excerpt", "")).casefold(),
        } for item in payload.get("records", [])]
        matched = {item.path: item
                   for item in SemanticRetriever().retrieve(query, documents)}
        results = []
        for item in payload.get("records", []):
            match = matched.get(item["path"])
            if match:
                results.append({"path": item["path"], "score": match.score,
                                "lexical": match.lexical,
                                "excerpt": item.get("excerpt", "")[:300]})
        return sorted(results, key=lambda entry: (-entry["score"], entry["path"]))[:limit]
