"""Puerta de entrega: IGRIS no declara terminado lo que no puede ejecutar."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from igris_os.application.approval import ApprovalAuthority
from igris_os.security.sandbox import JobObjectSandbox, SandboxRun

EXECUTE_CAPABILITY = "execute_generated_project"


@dataclass(frozen=True, slots=True)
class DeliveryReport:
    ok: bool
    kind: str
    project: str
    message: str
    command: tuple[str, ...] = ()
    returncode: int | None = None
    duration_seconds: float = 0.0
    sandboxed: bool = False
    timed_out: bool = False
    stdout: str = ""
    stderr: str = ""
    files: dict[str, str] = field(default_factory=dict)

    def write(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        return path


class DeliveryVerifier:
    def __init__(self, authority: ApprovalAuthority,
                 sandbox: JobObjectSandbox | None = None) -> None:
        self.authority = authority
        self.sandbox = sandbox or JobObjectSandbox(
            memory_limit_mb=1024, cpu_seconds=120, max_processes=8)

    def verify_python(self, project: Path, token: str | None,
                      *, timeout: int = 180,
                      kind: str = "software") -> DeliveryReport:
        project = self._project(project)
        if kind not in {"software", "game"}:
            raise ValueError("kind debe ser 'software' o 'game'")
        denied = self._authorize(project, token, kind)
        if denied:
            return denied
        required = ("README.md", "pyproject.toml", "tests")
        missing = [name for name in required if not (project / name).exists()]
        if missing:
            return self._failure(kind, project,
                                 "Entrega incompleta: faltan " + ", ".join(missing))
        return self._run(kind, project,
                         (sys.executable, "-m", "pytest", "-q"), timeout)

    def verify_godot(self, project: Path, token: str | None,
                     *, timeout: int = 120) -> DeliveryReport:
        project = self._project(project)
        denied = self._authorize(project, token, "game")
        if denied:
            return denied
        if not (project / "project.godot").is_file():
            return self._failure("game", project, "Entrega incompleta: falta project.godot")
        godot = shutil.which("godot4") or shutil.which("godot")
        if not godot:
            return self._failure("game", project,
                                 "No verificable: Godot 4 no está instalado o no está en PATH")
        return self._run("game", project,
                         (godot, "--headless", "--path", str(project), "--quit-after", "5"),
                         timeout)

    def _authorize(self, project: Path, token: str | None,
                   kind: str) -> DeliveryReport | None:
        if self.authority.consume(token, str(project), EXECUTE_CAPABILITY):
            return None
        return self._failure(kind, project,
                             "Permiso denegado: se requiere aprobación válida de un solo uso")

    def _run(self, kind: str, project: Path, command: tuple[str, ...],
             timeout: int) -> DeliveryReport:
        started = time.monotonic()
        result: SandboxRun = self.sandbox.run(
            list(command), cwd=str(project), timeout=timeout,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        files = self._hash_files(project)
        ok = result.returncode == 0 and not result.timed_out
        return DeliveryReport(
            ok, kind, str(project),
            "Entrega ejecutada y verificada" if ok else "La entrega no superó la verificación",
            command, result.returncode, round(time.monotonic() - started, 3),
            result.sandboxed, result.timed_out, result.stdout[-8000:],
            result.stderr[-8000:], files)

    @staticmethod
    def _project(project: Path) -> Path:
        resolved = Path(project).resolve()
        if not resolved.is_dir():
            raise ValueError(f"El proyecto no existe: {resolved}")
        return resolved

    @staticmethod
    def _failure(kind: str, project: Path, message: str) -> DeliveryReport:
        return DeliveryReport(False, kind, str(project), message)

    @staticmethod
    def _hash_files(project: Path) -> dict[str, str]:
        ignored = {".git", ".pytest_cache", "__pycache__"}
        hashes: dict[str, str] = {}
        for path in sorted(project.rglob("*")):
            if not path.is_file() or any(part in ignored for part in path.parts):
                continue
            hashes[path.relative_to(project).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        return hashes
