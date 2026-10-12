"""Verified, reversible source evolution for isolated development copies."""
from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

logger = logging.getLogger("igris.evolution")


@dataclass(frozen=True, slots=True)
class EvolutionPatch:
    target_file: Path
    old_content: str
    new_content: str
    reason: str
    version_tag: str


@dataclass(frozen=True, slots=True)
class EvolutionResult:
    ok: bool
    message: str
    applied_patches: list[EvolutionPatch] = field(default_factory=list)
    rollback_performed: bool = False
    snapshot_id: str = ""


class EvolutionCore:
    """Apply a patch batch only after an external verifier accepts it."""

    PROTECTED_FILES = frozenset({
        "src/igris_os/ui/cinematic.py",
        "src/igris_os/ui/panel_presentation.py",
    })

    def __init__(self, project_root: Path,
                 backup_dir: str = ".evolution_backups") -> None:
        self.root = Path(project_root).resolve()
        if not self.root.is_dir():
            raise ValueError("La raíz del proyecto no existe")
        backup = Path(backup_dir)
        self.backup_path = (backup if backup.is_absolute() else self.root / backup).resolve()
        if not self.backup_path.is_relative_to(self.root):
            raise ValueError("La carpeta de snapshots debe estar dentro del proyecto")

    @staticmethod
    def _hash(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def _relative_target(self, path: Path, *, must_exist: bool) -> Path:
        raw = Path(path)
        candidate = raw if raw.is_absolute() else self.root / raw
        if candidate.is_symlink():
            raise ValueError("No se permiten enlaces simbólicos como destino")
        target = candidate.resolve(strict=False)
        try:
            relative = target.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("El destino queda fuera del proyecto") from exc
        normalized = relative.as_posix().casefold()
        if normalized in self.PROTECTED_FILES:
            raise ValueError("El panel protegido no admite autoevolución")
        if target == self.backup_path or self.backup_path in target.parents:
            raise ValueError("Los snapshots no pueden modificarse como código")
        if must_exist and (not target.is_file() or target.is_symlink()):
            raise ValueError("El destino no es un archivo normal existente")
        return relative

    def create_snapshot(self, files: list[Path]) -> str:
        """Copy requested files under their project-relative paths and hash them."""
        snapshot_id = "snap_" + uuid.uuid4().hex
        snapshot_dir = self.backup_path / snapshot_id
        snapshot_dir.mkdir(parents=True, exist_ok=False)
        entries: list[dict[str, str]] = []
        seen: set[str] = set()
        try:
            for file in files:
                relative = self._relative_target(file, must_exist=True)
                key = relative.as_posix().casefold()
                if key in seen:
                    continue
                seen.add(key)
                source = self.root / relative
                destination = snapshot_dir / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                entries.append({"path": relative.as_posix(),
                                "sha256": self._hash(destination.read_bytes())})
            manifest = {"schema": 1, "snapshot_id": snapshot_id, "files": entries}
            (snapshot_dir / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")
            return snapshot_id
        except Exception:
            shutil.rmtree(snapshot_dir, ignore_errors=True)
            raise

    def apply_patch(self, patch: EvolutionPatch) -> bool:
        """Apply only an exact-baseline patch inside the unprotected project tree."""
        try:
            relative = self._relative_target(patch.target_file, must_exist=True)
            target = self.root / relative
            current = target.read_text(encoding="utf-8")
            if (current != patch.old_content or current == patch.new_content
                    or not patch.reason.strip() or not patch.version_tag.strip()):
                logger.warning("Evolution patch rejected: baseline/no-op/metadata check failed")
                return False
            target.write_text(patch.new_content, encoding="utf-8", newline="")
            return True
        except (OSError, UnicodeError, ValueError, TypeError) as exc:
            logger.error("Evolution patch rejected: %s", exc)
            return False
    def evolve(self, patches: list[EvolutionPatch], *,
               verifier: Callable[[Path], bool] | None = None) -> EvolutionResult:
        """Patch, externally verify, and restore the exact snapshot on any failure.

        A verifier is mandatory and must return the literal boolean ``True``.
        The callback should run the project's independent test/security gates.
        """
        if not patches:
            return EvolutionResult(False, "No hay cambios que evaluar")
        if not callable(verifier):
            return EvolutionResult(False, "Falta un verificador externo; no se modificó el proyecto")

        targets: list[Path] = []
        seen: set[str] = set()
        try:
            for patch in patches:
                relative = self._relative_target(patch.target_file, must_exist=True)
                target = self.root / relative
                key = relative.as_posix().casefold()
                if key in seen:
                    raise ValueError("Hay más de un parche para el mismo archivo")
                seen.add(key)
                if target.read_text(encoding="utf-8") != patch.old_content:
                    raise ValueError(f"La base cambió desde que se preparó el parche: {relative}")
                if not patch.reason.strip() or not patch.version_tag.strip():
                    raise ValueError("Cada parche requiere motivo y etiqueta de versión")
                targets.append(target)
            snapshot_id = self.create_snapshot(targets)
        except (OSError, UnicodeError, ValueError, TypeError) as exc:
            return EvolutionResult(False, f"Evolución rechazada: {exc}")

        applied: list[EvolutionPatch] = []
        try:
            for patch in patches:
                if not self.apply_patch(patch):
                    raise RuntimeError(f"No se pudo aplicar {patch.target_file}")
                applied.append(patch)
            if verifier(self.root) is not True:
                raise RuntimeError("El verificador externo no devolvió True")
            return EvolutionResult(True, "Cambio verificado; pendiente de promoción explícita",
                                   applied, False, snapshot_id)
        except Exception as exc:
            restored = self.trigger_rollback(snapshot_id)
            message = f"Evolución rechazada: {exc}"
            if not restored:
                message += "; atención: restauración incompleta"
            return EvolutionResult(False, message, applied, restored, snapshot_id)

    def trigger_rollback(self, snapshot_id: str,
                         files: list[Path] | None = None) -> bool:
        """Restore only manifest-listed files whose snapshot hashes still match."""
        if not re.fullmatch(r"snap_[0-9a-f]{32}", snapshot_id):
            return False
        snapshot_dir = (self.backup_path / snapshot_id).resolve()
        if snapshot_dir.parent != self.backup_path or not snapshot_dir.is_dir():
            return False
        try:
            manifest = json.loads((snapshot_dir / "manifest.json").read_text(encoding="utf-8"))
            if manifest.get("schema") != 1 or manifest.get("snapshot_id") != snapshot_id:
                return False
            entries = manifest.get("files")
            if not isinstance(entries, list):
                return False
            restored = True
            for entry in entries:
                relative = Path(entry["path"])
                if relative.is_absolute() or ".." in relative.parts:
                    restored = False
                    continue
                backup = (snapshot_dir / relative).resolve()
                if not backup.is_relative_to(snapshot_dir) or not backup.is_file():
                    restored = False
                    continue
                data = backup.read_bytes()
                if self._hash(data) != entry.get("sha256"):
                    restored = False
                    continue
                target = self.root / relative
                self._relative_target(target, must_exist=False)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            return restored
        except (OSError, UnicodeError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            logger.error("Evolution rollback failed: %s", exc)
            return False
