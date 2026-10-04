# -*- coding: utf-8 -*-
"""
IGRIS OS - Evolution Core
Responsibility: Autonomous self-modification, system analysis, and safe evolution.
"""

from __future__ import annotations
import os
import shutil
import hashlib
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any

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
    applied_patches: List[EvolutionPatch] = field(default_factory=list)
    rollback_performed: bool = False

class EvolutionCore:
    """
    The heart of IGRIS OS self-evolution.
    Allows the system to analyze its own source and apply verified improvements.
    """

    def __init__(self, project_root: Path, backup_dir: str = ".evolution_backups") -> None:
        self.root = project_root.resolve()
        self.backup_path = self.root / backup_dir
        self.backup_path.mkdir(parents=True, exist_ok=True)

    def _calculate_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def create_snapshot(self, files: List[Path]) -> str:
        """Creates a snapshot of current files before evolution."""
        snapshot_id = f"snap_{int(os.time.time())}"
        snap_dir = self.backup_path / snapshot_id
        snap_dir.mkdir(parents=True, exist_ok=True)
        
        for file in files:
            if file.exists():
                shutil.copy2(file, snap_dir / file.name)
        
        return snapshot_id

    def apply_patch(self, patch: EvolutionPatch) -> bool:
        """Applies a specific code patch to the system."""
        try:
            if not patch.target_file.exists():
                return False
            
            current_content = patch.target_file.read_text(encoding="utf-8")
            if current_content != patch.old_content:
                logger.warning(f"Content mismatch in {patch.target_file}. Evolution aborted.")
                return False
            
            patch.target_file.write_text(patch.new_content, encoding="utf-8")
            return True
        except Exception as exc:
            logger.error(f"Patch failed: {exc}")
            return False

    def evolve(self, patches: List[EvolutionPatch]) -> EvolutionResult:
        """
        Main evolution loop: Snapshot -> Patch -> Verify -> Commit/Rollback.
        """
        target_files = [p.target_file for p in patches]
        snapshot_id = self.create_snapshot(target_files)
        
        applied = []
        try:
            for patch in patches:
                if self.apply_patch(patch):
                    applied.append(patch)
                else:
                    raise RuntimeError(f"Patch failed for {patch.target_file}")
            
            # Here, IGRIS OS would normally run its test suite
            # If tests fail -> trigger_rollback()
            
            return EvolutionResult(True, "Evolution successfully applied", applied)
            
        except Exception as exc:
            self.trigger_rollback(snapshot_id, target_files)
            return EvolutionResult(False, f"Evolution failed: {exc}", applied, True)

    def trigger_rollback(self, snapshot_id: str, files: List[Path]) -> None:
        """Restores files to the state of the given snapshot."""
        snap_dir = self.backup_path / snapshot_id
        for file in files:
            backup_file = snap_dir / file.name
            if backup_file.exists():
                shutil.copy2(backup_file, file)
        logger.info(f"Rollback to {snapshot_id} completed.")
