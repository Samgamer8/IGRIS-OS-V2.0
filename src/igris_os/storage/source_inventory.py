import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


EXCLUDED = {".git", "__pycache__", ".pytest_cache", "node_modules",
            "build", "dist", "runtime"}

CATEGORIES = {
    "image": {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".tga", ".webp"},
    "audio": {".flac", ".mid", ".midi", ".mp3", ".ogg", ".wav"},
    "video": {".avi", ".mkv", ".mov", ".mp4", ".webm"},
    "executable": {".bat", ".cmd", ".com", ".dll", ".exe", ".ps1", ".vxd"},
    "document": {".doc", ".docx", ".hlp", ".md", ".pdf", ".rtf", ".txt"},
    "archive": {".7z", ".cab", ".gz", ".rar", ".tar", ".zip"},
}


def _category(extension: str) -> str:
    for name, extensions in CATEGORIES.items():
        if extension in extensions:
            return name
    return "other"


def inventory_source(root: Path, *, max_hash_bytes: int = 64 * 1024 * 1024,
                     on_progress: Callable[[int, str], None] | None = None) -> dict:
    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f"Fuente no valida: {root}")
    if on_progress:
        on_progress(1, "Explorando fuentes")
    candidates = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in EXCLUDED for part in relative.parts):
            continue
        candidates.append(path)
    files = []
    errors = []
    category_counts: dict[str, int] = {}
    extension_counts: dict[str, int] = {}
    executables: list[str] = []
    total = len(candidates)
    for index, path in enumerate(candidates):
        relative = path.relative_to(root)
        extension = path.suffix.casefold()
        category = _category(extension)
        try:
            size = path.stat().st_size
            digest = None
            status = "too_large"
            if size <= max_hash_bytes:
                value = hashlib.sha256()
                with path.open("rb") as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        value.update(block)
                digest, status = value.hexdigest(), "hashed"
        except OSError as exc:
            size, digest, status = 0, None, "unreadable"
            errors.append({"path": str(relative), "error": str(exc)})
        files.append({"path": str(relative), "size": size,
                      "extension": extension, "category": category,
                      "sha256": digest, "status": status})
        category_counts[category] = category_counts.get(category, 0) + 1
        extension_counts[extension or "[none]"] = (
            extension_counts.get(extension or "[none]", 0) + 1)
        if category == "executable":
            executables.append(str(relative))
        if on_progress:
            on_progress(1 + int(90 * (index + 1) / max(1, total)),
                        f"Inventariando {relative}")
    if on_progress:
        on_progress(99, "Generando inventario")
    return {"source": str(root),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "file_count": len(files),
            "total_bytes": sum(item["size"] for item in files),
            "summary": {
                "categories": dict(sorted(category_counts.items())),
                "extensions": dict(sorted(extension_counts.items())),
                "executables": executables,
                "error_count": len(errors),
            },
            "errors": errors,
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
