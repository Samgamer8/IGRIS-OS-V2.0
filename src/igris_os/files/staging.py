import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from igris_os.files.repository import EXCLUDED
from igris_os.tools import safe_output


@dataclass(frozen=True, slots=True)
class StagingResult:
    root: str
    files: int
    total_bytes: int
    manifest: str
    verified: bool
    truncated: bool


class RepositoryStager:
    def __init__(self, workspace: Path, *, max_files: int = 5000,
                 max_file_bytes: int = 2 * 1024 * 1024,
                 max_total_bytes: int = 128 * 1024 * 1024) -> None:
        self.workspace = workspace.resolve()
        self.max_files = max_files
        self.max_file_bytes = max_file_bytes
        self.max_total_bytes = max_total_bytes

    def stage(self, source: Path, *, confirmed: bool = False,
              on_progress: Callable[[int, str], None] | None = None) -> StagingResult:
        if not confirmed:
            raise PermissionError("Se necesita confirmacion")
        source = source.resolve()
        if not source.is_dir() or source.is_symlink():
            raise ValueError("Repositorio no valido")
        target = safe_output(self.workspace, "working/repository")
        if target.exists():
            raise FileExistsError("La copia aislada ya existe")
        records, total, truncated = [], 0, False
        target.mkdir(parents=True)
        try:
            for index, path in enumerate(sorted(source.rglob("*"))):
                if len(records) >= self.max_files:
                    truncated = True
                    break
                if not path.is_file() or path.is_symlink():
                    continue
                relative = path.relative_to(source)
                if any(part in EXCLUDED for part in relative.parts):
                    continue
                size = path.stat().st_size
                if size > self.max_file_bytes:
                    continue
                if total + size > self.max_total_bytes:
                    truncated = True
                    break
                destination = (target / relative).resolve()
                if not destination.is_relative_to(target):
                    raise ValueError("Ruta de copia fuera del workspace")
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)
                original_hash = self._hash(path)
                copied_hash = self._hash(destination)
                if original_hash != copied_hash:
                    raise OSError("Fallo de integridad al copiar")
                records.append({"path": relative.as_posix(), "size": size,
                                "sha256": original_hash})
                total += size
                if on_progress:
                    on_progress(min(95, int(100 * (index + 1) / self.max_files)),
                                f"Copiando {relative.as_posix()}")
            if on_progress:
                on_progress(96, "Escribiendo manifiesto")
            manifest = safe_output(self.workspace, "output/staging_manifest.json")
            manifest.write_text(json.dumps({
                "schema": 1, "source": str(source), "staged": str(target),
                "files": records, "total_bytes": total,
                "truncated": truncated, "source_modified": False,
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            return StagingResult(str(target), len(records), total,
                                 str(manifest), True, truncated)
        except Exception:
            if target.is_dir() and target.resolve().is_relative_to(self.workspace):
                shutil.rmtree(target)
            raise

    @staticmethod
    def _hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()
