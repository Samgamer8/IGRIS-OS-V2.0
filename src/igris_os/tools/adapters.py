import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ToolAdapter:
    name: str
    executable: str | None
    domains: tuple[str, ...]

    @property
    def available(self) -> bool:
        return bool(self.executable)


class ToolCatalog:
    DEFINITIONS = {
        "ffmpeg": ("video", "audio"),
        "ffprobe": ("video", "audio"),
        "blender": ("video", "image", "3d"),
        "godot": ("games",),
        "git": ("programming",),
    }

    def discover(self) -> tuple[ToolAdapter, ...]:
        return tuple(ToolAdapter(name, shutil.which(name), domains)
                     for name, domains in self.DEFINITIONS.items())

    def for_domain(self, domain: str) -> tuple[ToolAdapter, ...]:
        return tuple(tool for tool in self.discover() if domain in tool.domains)


def safe_output(workspace: Path, relative: str) -> Path:
    root = workspace.resolve()
    target = (root / relative).resolve()
    if not target.is_relative_to(root):
        raise ValueError("Salida fuera del workspace")
    target.parent.mkdir(parents=True, exist_ok=True)
    return target
