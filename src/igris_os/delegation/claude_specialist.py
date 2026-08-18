# -*- coding: utf-8 -*-
"""Especialista delegado: Claude Code ejecutado como subproceso confinado.

Convierte una ``DelegatedTask`` en una invocacion headless de Claude Code
(``claude -p``) y devuelve un ``DelegatedResult`` verificable. La ejecucion
corre dentro del ``JobObjectSandbox`` existente (limites de memoria/CPU/tiempo
y KILL_ON_JOB_CLOSE) con el directorio de trabajo fijado al workspace de la
mision.

Limite honesto (igual que en el resto del taller): el Job Object confina
recursos, NO el sistema de archivos ni la red. Por eso:

- se restringen las herramientas (``--allowedTools``) a lo minimo necesario;
- el entorno se filtra antes de lanzar el proceso (sin secretos);
- la contencion se DETECTA tras la ejecucion (snapshot + canarios), y cualquier
  cambio fuera de lo esperado se reporta como violacion, no se ignora.

La frontera dura (AppContainer/contenedor) sigue siendo el endurecimiento
pendiente. Este modulo no promete lo que no hace.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

from igris_os.delegation.contract import DelegatedResult, DelegatedTask
from igris_os.security.sandbox import JobObjectSandbox

_SENSITIVE_ENV = ("KEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD",
                  "CREDENTIAL", "PRIVATE")

_PROMPT_TEMPLATE = """You are an elite autonomous coding specialist working inside an isolated workspace.

OBJECTIVE:
{objective}

CONSTRAINTS:
- Work ONLY inside the workspace directory: {workspace}
- Do not read or write files outside the workspace.
- Do not install packages, touch the network, or modify the system.
{constraints}

ACCEPTANCE CRITERIA:
{acceptance}

Make the minimal change that satisfies the objective and acceptance criteria, then stop."""


def clean_env() -> dict[str, str]:
    """Copia del entorno sin variables que puedan contener secretos."""
    clean: dict[str, str] = {}
    for key, value in os.environ.items():
        if any(frag in key.upper() for frag in _SENSITIVE_ENV):
            continue
        clean[key] = value
    return clean


def _resolve_claude() -> str:
    path = shutil.which("claude")
    if not path:
        raise FileNotFoundError(
            "Claude Code no esta disponible: ejecuta 'claude' en el PATH")
    return path


def _build_prompt(task: DelegatedTask) -> str:
    constraints = "\n".join(f"- {item}" for item in task.constraints)
    acceptance = "\n".join(f"- {item}" for item in task.acceptance) or "- (none)"
    return _PROMPT_TEMPLATE.format(
        objective=task.objective,
        workspace=str(task.workspace),
        constraints=constraints,
        acceptance=acceptance,
    )


def _build_argv(claude: str | tuple[str, ...], task: DelegatedTask,
                prompt: str) -> list[str]:
    argv = ([claude] if isinstance(claude, str) else list(claude))
    argv += ["-p", prompt, "--output-format", "json",
             "--max-turns", str(task.max_turns)]
    if task.model:
        argv += ["--model", task.model]
    if task.allowed_tools:
        argv += ["--allowedTools", ",".join(task.allowed_tools)]
    return argv


def _parse_output(stdout: str) -> str:
    """Extrae el texto del resultado de la salida headless de Claude.

    Claude Code devuelve JSON con ``--output-format json``; si el parseo falla
    (claude fake en pruebas, versiones antiguas) se devuelve el texto crudo.
    """
    text = stdout.strip()
    if not text:
        return ""
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text
    if isinstance(data, dict):
        for key in ("result", "content", "text", "message"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        if isinstance(data.get("content"), list):
            parts = []
            for block in data["content"]:
                if isinstance(block, dict) and isinstance(block.get("text"), str):
                    parts.append(block["text"])
            if parts:
                return "\n".join(parts).strip()
    return text


def _snapshot(root: Path) -> dict[str, str]:
    """Mapa ruta -> sha256. Si ``root`` es archivo, solo ese archivo.

    Ignora bytecode (``__pycache__``/``*.pyc``): son artefactos de compilacion,
    no cambios de codigo fuente.
    """
    if root.is_file():
        try:
            return {str(root): hashlib.sha256(root.read_bytes()).hexdigest()}
        except OSError:
            return {}
    if not root.is_dir():
        return {}
    snapshot: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(root)
        if path.suffix == ".pyc" or "__pycache__" in rel.parts:
            continue
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            continue
        snapshot[str(rel)] = digest
    return snapshot


def _changed(before: dict[str, str], after: dict[str, str]) -> tuple[str, ...]:
    keys = set(before) | set(after)
    return tuple(sorted(
        key for key in keys if before.get(key) != after.get(key)))


class DelegatedSpecialist:
    """Ejecuta una tarea en Claude Code (o un claude fake inyectable)."""

    def __init__(self, claude_command: str | tuple[str, ...] | None = None, *,
                 memory_limit_mb: int = 2048,
                 cpu_seconds: int = 300) -> None:
        self.claude_command = claude_command or _resolve_claude()
        self.memory_limit_mb = memory_limit_mb
        self.cpu_seconds = cpu_seconds

    def run(self, task: DelegatedTask) -> DelegatedResult:
        workspace = task.workspace.resolve()
        if not workspace.is_dir():
            return DelegatedResult(
                False, "Workspace invalido o inexistente",
                returncode=-1)

        before = _snapshot(workspace)
        canaries_before = {str(p): _snapshot(p) for p in task.canaries}

        prompt = _build_prompt(task)
        argv = _build_argv(self.claude_command, task, prompt)
        sandbox = JobObjectSandbox(memory_limit_mb=self.memory_limit_mb,
                                   cpu_seconds=self.cpu_seconds)
        run = sandbox.run(argv, timeout=task.timeout_seconds,
                          cwd=str(workspace), env=clean_env())

        after = _snapshot(workspace)
        changed = _changed(before, after)
        violations = self._canary_violations(task, canaries_before)

        if run.timed_out:
            return DelegatedResult(
                False, "El especialista agoto el tiempo",
                returncode=run.returncode, stdout=run.stdout,
                stderr=run.stderr, changed_files=changed,
                sandboxed=run.sandboxed, timed_out=True,
                containment_violations=violations)

        if run.returncode != 0:
            error = _parse_output(run.stdout)
            detail = (error or run.stderr.strip())
            message = "El especialista fallo (exit %d)" % run.returncode
            if detail:
                message += " · " + detail[:300]
            return DelegatedResult(
                False, message, returncode=run.returncode,
                stdout=run.stdout, stderr=run.stderr,
                changed_files=changed, sandboxed=run.sandboxed,
                timed_out=False, containment_violations=violations)

        verified: bool | None = None
        verify_output = ""
        if task.verify_command:
            verify_run = sandbox.run(
                list(task.verify_command), timeout=task.timeout_seconds,
                cwd=str(workspace), env=clean_env())
            verified = verify_run.returncode == 0
            verify_output = (verify_run.stdout + verify_run.stderr)[-4000:]

        output = _parse_output(run.stdout)
        ok = bool(changed) or verified is True or bool(output)
        return DelegatedResult(
            ok, output or "Especialista completado", returncode=run.returncode,
            stdout=run.stdout, stderr=run.stderr, changed_files=changed,
            verified=verified, verify_output=verify_output,
            sandboxed=run.sandboxed, timed_out=False,
            containment_violations=violations)

    @staticmethod
    def _canary_violations(task: DelegatedTask,
                           before: dict[str, dict[str, str]]) -> tuple[str, ...]:
        violations: list[str] = []
        for raw in task.canaries:
            path = Path(str(raw)).resolve()
            key = str(path)
            after = _snapshot(path)
            if before.get(key) != after:
                violations.append(str(path))
        return tuple(violations)
