from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ToolStatus:
    name: str
    category: str
    state: str
    path: str = ""

    @property
    def available(self) -> bool:
        return self.state != "missing"


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    category: str
    commands: tuple[str, ...]
    bundled: tuple[str, ...] = ()


class RuntimeProbe:
    """Catalogo de dependencias externas de IGRIS y su estado real.

    Cada herramienta puede estar: 'internal' (empaquetada en .tools/),
    'external' (disponible en el sistema) o 'missing'. Es la base para
    la autosuficiencia: saber que falta es el primer paso para empaquetarlo.
    """

    _BUNDLE_DIR = ".tools"

    TOOLS: tuple[ToolSpec, ...] = (
        ToolSpec("ollama", "llm", ("ollama",), ("ollama.exe", "ollama")),
        ToolSpec("lmstudio", "llm", ("lms",), ("lms.exe",)),
        ToolSpec("k3", "llm", ("k3", "kimi-k3"), ("k3.exe",)),
        ToolSpec("git", "vcs", ("git",), ("git.exe",)),
        ToolSpec("ffmpeg", "media", ("ffmpeg",), ("ffmpeg.exe",)),
        ToolSpec("ffprobe", "media", ("ffprobe",), ("ffprobe.exe",)),
        ToolSpec("godot", "games", ("godot", "godot4"), ("Godot*.exe", "godot.exe", "godot")),
        ToolSpec("node", "languages", ("node",), ("node.exe",)),
        ToolSpec("npm", "languages", ("npm", "npm.cmd"), ("npm.cmd", "npm-cli.js")),
        ToolSpec("typescript", "languages", ("tsc", "tsc.cmd"), ("tsc.cmd", "tsc.js", "tsc")),
        ToolSpec("go", "languages", ("go",), ("go.exe",)),
        ToolSpec("cargo", "languages", ("cargo", "cargo.exe"), ("cargo.exe",)),
        ToolSpec("rustc", "languages", ("rustc", "rustc.exe"), ("rustc.exe",)),
        ToolSpec("cmake", "languages", ("cmake", "cmake.exe"), ("cmake.exe",)),
        ToolSpec("gcc", "languages", ("gcc", "gcc.exe"), ("gcc.exe",)),
        ToolSpec("java", "languages", ("java", "java.exe"), ("java.exe",)),
        ToolSpec("powershell", "system", ("powershell.exe", "pwsh"), ("powershell.exe",)),
        ToolSpec("python", "runtime", ("python", "python.exe"), ("python.exe", "python")),
    )

    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root or os.getcwd()).resolve()
        self.bundle = self.root / self._BUNDLE_DIR

    def probe(self) -> dict[str, ToolStatus]:
        statuses: dict[str, ToolStatus] = {}
        for spec in self.TOOLS:
            statuses[spec.name] = self._probe_one(spec)
        return statuses

    def _probe_one(self, spec: ToolSpec) -> ToolStatus:
        bundled = self._find_bundled(spec.bundled)
        if bundled:
            return ToolStatus(spec.name, spec.category, "internal", str(bundled))
        for command in spec.commands:
            path = shutil.which(command)
            if path:
                return ToolStatus(spec.name, spec.category, "external", path)
        return ToolStatus(spec.name, spec.category, "missing")

    def _find_bundled(self, patterns: tuple[str, ...]) -> Path | None:
        if not self.bundle.is_dir():
            return None
        for pattern in patterns:
            match = next((p for p in self.bundle.rglob(pattern) if p.is_file()), None)
            if match:
                return match
        return None

    def summary(self) -> str:
        lines = []
        for status in self.probe().values():
            mark = {"internal": "EMP", "external": "SYS", "missing": "FALTA"}[status.state]
            lines.append(f"[{mark}] {status.name:12s} {status.category:10s} {status.path}")
        return "\n".join(lines)

    def missing(self) -> list[ToolStatus]:
        return [status for status in self.probe().values() if not status.available]
