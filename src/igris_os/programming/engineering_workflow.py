from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

from igris_os.security.sandbox import JobObjectSandbox, SandboxRun
from igris_os.security.restricted import _filtered_env

from .preflight import PreflightReport, ProgrammingPreflight


@dataclass(frozen=True, slots=True)
class EngineeringRunResult:
    preflight: PreflightReport
    executed: bool
    allowed: bool
    run: SandboxRun | None = None
    reason: str = ""


class EngineeringWorkflow:
    """Une inspección previa y ejecución verificada en un workspace."""

    _ALLOWED = {"python", "python.exe", "py", "py.exe", "git", "git.exe",
                "pytest", "pytest.exe", "ffmpeg", "ffmpeg.exe",
                "ffprobe", "ffprobe.exe"}

    def __init__(self, *, preflight: ProgrammingPreflight | None = None,
                 sandbox: JobObjectSandbox | None = None) -> None:
        self.preflight = preflight or ProgrammingPreflight()
        self.sandbox = sandbox or JobObjectSandbox(
            memory_limit_mb=512, cpu_seconds=60, max_processes=4)

    def run(self, root: Path, command: list[str] | tuple[str, ...], *,
            confirmed: bool = False, timeout: int = 30) -> EngineeringRunResult:
        project_root = root.resolve()
        report = self.preflight.inspect(project_root)
        if not report.ok:
            return EngineeringRunResult(
                report, False, False, reason="Preflight contiene hallazgos criticos")
        if not confirmed:
            return EngineeringRunResult(
                report, False, False, reason="Se necesita confirmacion")
        if not isinstance(command, (list, tuple)) or not command:
            return EngineeringRunResult(
                report, False, False, reason="El comando debe ser una lista no vacia")
        normalized = [str(item) for item in command]
        name = Path(normalized[0]).name.casefold()
        if name not in self._ALLOWED and normalized[0] != sys.executable:
            return EngineeringRunResult(
                report, False, False, reason="Ejecutable no permitido")
        if name in {"python", "python.exe", "py", "py.exe"}:
            normalized[0] = sys.executable
        safe_timeout = min(120, max(1, int(timeout)))
        run = self.sandbox.run(
            normalized, cwd=str(project_root), timeout=safe_timeout, env=_filtered_env())
        return EngineeringRunResult(
            report, True, True, run=run,
            reason="ok" if run.returncode == 0 and not run.timed_out else "comando fallo")
