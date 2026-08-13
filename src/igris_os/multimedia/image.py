from dataclasses import dataclass
from pathlib import Path

from igris_os.tools import safe_output


@dataclass(frozen=True, slots=True)
class ImageResult:
    ok: bool
    message: str
    output: str = ""


class ImageEngine:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.resolve()

    def resize(self, source: Path, output: str, width: int, height: int,
               *, confirmed: bool = False) -> ImageResult:
        if not confirmed:
            return ImageResult(False, "Se necesita confirmacion")
        if width < 1 or height < 1 or width > 16384 or height > 16384:
            return ImageResult(False, "Dimensiones invalidas")
        try:
            from PIL import Image
        except ImportError:
            return ImageResult(False, "Pillow no esta instalado")
        if not source.is_file():
            return ImageResult(False, "Imagen no disponible")
        target = safe_output(self.workspace, output)
        try:
            with Image.open(source) as image:
                image.thumbnail((width, height), Image.Resampling.LANCZOS)
                image.save(target)
        except (OSError, ValueError) as exc:
            return ImageResult(False, str(exc))
        return ImageResult(True, "Imagen procesada", str(target))
