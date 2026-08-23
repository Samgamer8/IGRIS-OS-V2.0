import hashlib
import mimetypes
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class IndexedFile:
    path: str
    size: int
    mime: str
    sha256: str


class FileIndexer:
    def __init__(self, root: Path, *, max_file_bytes: int = 16 * 1024 * 1024) -> None:
        self.root = root.resolve()
        self.max_file_bytes = max_file_bytes

    def scan(self) -> list[IndexedFile]:
        if not self.root.is_dir():
            raise ValueError("La raiz no existe")
        result = []
        for path in sorted(self.root.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            relative = path.relative_to(self.root)
            if any(part in {".git", "__pycache__", "node_modules", "build", "dist"}
                   for part in relative.parts):
                continue
            size = path.stat().st_size
            if size > self.max_file_bytes:
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            result.append(IndexedFile(str(relative), size,
                                      mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                                      digest))
        return result

    def manifest(self) -> list[dict]:
        return [asdict(item) for item in self.scan()]

    def read_text(self, relative: str, *, max_chars: int = 200_000) -> str:
        target = (self.root / relative).resolve()
        if not target.is_relative_to(self.root) or target.is_symlink():
            raise ValueError("Ruta fuera de la raiz")
        return target.read_text(encoding="utf-8", errors="replace")[:max_chars]
