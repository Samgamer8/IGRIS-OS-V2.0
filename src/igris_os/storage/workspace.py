"""Workspace con context manager, cleanup y limites."""
import logging
import shutil
from pathlib import Path
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class MissionWorkspace:
    MAX_SIZE_MB = 500  # Limite de tamaño por workspace
    
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def create(self, mission_id: str) -> Path:
        """Crea workspace aislado con estructura estandar."""
        if not self._is_valid_id(mission_id):
            raise ValueError(f"ID invalido: {mission_id}")
        
        target = (self.root / mission_id).resolve()
        
        # Validar path traversal
        if not target.is_relative_to(self.root):
            raise ValueError("Workspace fuera de raiz permitida")
        
        # Crear estructura
        for name in ("input", "working", "output", "tests", "logs"):
            (target / name).mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Workspace creado: {target}")
        return target

    @contextmanager
    def temporary_workspace(self, mission_id: str):
        """Context manager: crea, limpia automaticamente."""
        workspace = self.create(mission_id)
        try:
            yield workspace
        finally:
            self.cleanup(workspace)

    def cleanup(self, workspace: Path) -> None:
        """Elimina workspace completamente (despues de ejecucion)."""
        try:
            if workspace.exists() and workspace.is_relative_to(self.root):
                shutil.rmtree(workspace, ignore_errors=True)
                logger.info(f"Workspace limpiado: {workspace}")
        except Exception as e:
            logger.error(f"Fallo limpiando workspace: {e}")

    def get_size_mb(self, workspace: Path) -> float:
        """Calcula tamaño en MB."""
        total = sum(f.stat().st_size for f in workspace.rglob("*") if f.is_file())
        return total / (1024 * 1024)

    @staticmethod
    def _is_valid_id(mission_id: str) -> bool:
        """Valida ID: alphanumeric + guion bajo."""
        return mission_id and len(mission_id) <= 50 and all(c.isalnum() or c == "_" for c in mission_id)