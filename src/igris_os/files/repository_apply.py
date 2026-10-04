from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from uuid import uuid4

from igris_os.tools import safe_output


@dataclass(frozen=True, slots=True)
class RepositoryApplyResult:
    source_root: str
    backup_root: str
    report: str
    changed_files: tuple[str, ...]


class RepositoryChangeApplier:
    """Aplica cambios verificados con control de conflictos y rollback."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = Path(workspace).resolve()

    def apply(self, source_root: Path, staged_root: Path,
              changed_files: tuple[str, ...] | list[str],
              staging_manifest: Path, *,
              confirmed: bool = False) -> RepositoryApplyResult:
        if not confirmed:
            raise PermissionError("La aplicación requiere autorización explícita")
        source = Path(source_root).resolve()
        staged = Path(staged_root).resolve()
        manifest_path = Path(staging_manifest).resolve()
        if (not source.is_dir() or source.is_symlink() or
                not staged.is_dir() or staged.is_symlink()):
            raise ValueError("Repositorio original o staging no válido")
        evidence_workspace = staged.parent.parent
        expected_staging = evidence_workspace / "working" / "repository"
        expected_manifest = evidence_workspace / "output" / "staging_manifest.json"
        if source == staged or staged != expected_staging.resolve():
            raise ValueError("El staging no pertenece a una misión de IGRIS")
        if (not manifest_path.is_file() or manifest_path.is_symlink() or
                manifest_path != expected_manifest.resolve()):
            raise ValueError("Manifiesto de staging no válido")

        document = json.loads(manifest_path.read_text(encoding="utf-8"))
        if Path(str(document.get("source", ""))).resolve() != source:
            raise ValueError("El manifiesto no corresponde al repositorio original")
        if Path(str(document.get("staged", ""))).resolve() != staged:
            raise ValueError("El manifiesto no corresponde al staging verificado")
        originals = {
            str(item["path"]): str(item["sha256"])
            for item in document.get("files", ())
            if isinstance(item, dict) and "path" in item and "sha256" in item
        }
        paths = self._validate_paths(source, staged, changed_files, originals)

        operation_id = uuid4().hex
        backup = safe_output(
            self.workspace, "backups/repository_apply_" + operation_id)
        backup.mkdir(parents=True)
        applied: list[tuple[str, bool]] = []
        temporaries: list[Path] = []
        try:
            for relative, source_file, staged_file in paths:
                existed = source_file.is_file()
                if existed:
                    backup_file = backup / relative
                    backup_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_file, backup_file)
                source_file.parent.mkdir(parents=True, exist_ok=True)
                temporary = source_file.with_name(
                    "." + source_file.name + ".igris-" + operation_id + ".tmp")
                temporaries.append(temporary)
                shutil.copy2(staged_file, temporary)
                os.replace(temporary, source_file)
                temporaries.remove(temporary)
                applied.append((relative, existed))
                if self._hash(source_file) != self._hash(staged_file):
                    raise OSError("Fallo de integridad al aplicar " + relative)
            report = safe_output(
                self.workspace, "output/repository_apply_" + operation_id + ".json")
            report.write_text(json.dumps({
                "schema": 1,
                "source": str(source),
                "staged": str(staged),
                "manifest": str(manifest_path),
                "backup": str(backup),
                "changed_files": [item[0] for item in paths],
                "verified_after_copy": True,
            }, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            for temporary in temporaries:
                if temporary.is_file() and temporary.resolve().is_relative_to(source):
                    temporary.unlink()
            self._rollback(source, backup, applied)
            raise

        return RepositoryApplyResult(
            str(source), str(backup), str(report),
            tuple(item[0] for item in paths))

    def _validate_paths(self, source: Path, staged: Path,
                        changed_files: tuple[str, ...] | list[str],
                        originals: dict[str, str]
                        ) -> list[tuple[str, Path, Path]]:
        if not isinstance(changed_files, (tuple, list)) or not changed_files:
            raise ValueError("No hay cambios verificados para aplicar")
        if len(changed_files) > 100:
            raise ValueError("Demasiados archivos en una sola aplicación")
        result: list[tuple[str, Path, Path]] = []
        seen: set[str] = set()
        for raw in changed_files:
            value = str(raw).replace("\\", "/")
            windows = PureWindowsPath(value)
            relative_path = Path(value)
            if (not value or value.startswith("/") or relative_path.is_absolute() or windows.drive or
                    ".." in relative_path.parts):
                raise ValueError("Ruta de cambio no permitida")
            relative = relative_path.as_posix()
            key = relative.casefold()
            if key in seen:
                raise ValueError("Ruta de cambio duplicada")
            seen.add(key)
            staged_file = (staged / relative).resolve()
            source_file = (source / relative).resolve()
            if (not staged_file.is_relative_to(staged) or
                    not source_file.is_relative_to(source) or
                    not staged_file.is_file() or staged_file.is_symlink()):
                raise ValueError("Archivo de staging no válido: " + relative)
            expected = originals.get(relative)
            if expected is None:
                if source_file.exists():
                    raise ValueError("Conflicto en archivo nuevo: " + relative)
            elif (not source_file.is_file() or source_file.is_symlink() or
                  self._hash(source_file) != expected):
                raise ValueError(
                    "El original cambió después del staging: " + relative)
            result.append((relative, source_file, staged_file))
        return result

    @staticmethod
    def _rollback(source: Path, backup: Path,
                  applied: list[tuple[str, bool]]) -> None:
        for relative, existed in reversed(applied):
            target = (source / relative).resolve()
            if not target.is_relative_to(source):
                continue
            saved = backup / relative
            if existed and saved.is_file():
                shutil.copy2(saved, target)
            elif not existed and target.is_file():
                target.unlink()

    @staticmethod
    def _hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()
