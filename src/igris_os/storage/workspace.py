from pathlib import Path


class MissionWorkspace:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def create(self, mission_id: str) -> Path:
        if not mission_id.isalnum():
            raise ValueError("Identificador de mision invalido")
        target = (self.root / mission_id).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError("Workspace fuera de la raiz permitida")
        for name in ("input", "working", "output", "tests", "logs"):
            (target / name).mkdir(parents=True, exist_ok=True)
        return target

