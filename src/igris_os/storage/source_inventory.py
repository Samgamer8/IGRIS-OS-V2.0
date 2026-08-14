import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


EXCLUDED = {".git", "__pycache__", ".pytest_cache", "node_modules",
            "build", "dist", "runtime"}


def inventory_source(root: Path, *, max_hash_bytes: int = 64 * 1024 * 1024,
                     on_progress: Callable[[int, str], None] | None = None) -> dict:
    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f"Fuente no valida: {root}")
    if on_progress:
        on_progress(1, "Explorando fuentes")
    candidates = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in EXCLUDED for part in relative.parts):
            continue
        candidates.append(path)
    files = []
    total = len(candidates)
    for index, path in enumerate(candidates):
        relative = path.relative_to(root)
        size = path.stat().st_size
        digest = None
        status = "too_large"
        if size <= max_hash_bytes:
            value = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    value.update(block)
            digest, status = value.hexdigest(), "hashed"
        files.append({"path": str(relative), "size": size,
                      "sha256": digest, "status": status})
        if on_progress:
            on_progress(1 + int(90 * (index + 1) / max(1, total)),
                        f"Inventariando {relative}")
    if on_progress:
        on_progress(99, "Generando inventario")
    return {"source": str(root),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "file_count": len(files),
            "total_bytes": sum(item["size"] for item in files),
            "files": files}


def write_inventory(sources: list[Path], output: Path,
                    on_progress: Callable[[int, str], None] | None = None) -> dict:
    document = {"schema": 1,
                "sources": [inventory_source(
                    source, on_progress=on_progress) for source in sources]}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, ensure_ascii=False, indent=2),
                      encoding="utf-8")
    return document
