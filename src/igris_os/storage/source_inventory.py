import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


EXCLUDED = {".git", "__pycache__", ".pytest_cache", "node_modules",
            "build", "dist", "runtime"}


def inventory_source(root: Path, *, max_hash_bytes: int = 64 * 1024 * 1024) -> dict:
    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f"Fuente no valida: {root}")
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in EXCLUDED for part in relative.parts):
            continue
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
    return {"source": str(root),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "file_count": len(files),
            "total_bytes": sum(item["size"] for item in files),
            "files": files}


def write_inventory(sources: list[Path], output: Path) -> dict:
    document = {"schema": 1,
                "sources": [inventory_source(source) for source in sources]}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, ensure_ascii=False, indent=2),
                      encoding="utf-8")
    return document
