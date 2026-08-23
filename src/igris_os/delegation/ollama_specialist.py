# -*- coding: utf-8 -*-
"""Especialista delegado con modelo local (Ollama/LM Studio).

Comparte el MISMO contrato y verificacion que el especialista Claude Code, pero
no depende de credito externo: usa el modelo local ya instalado (por defecto
``qwen2.5-coder:7b``). La diferencia honesta es de capacidad:

- Claude Code es un agente con bucle de herramientas (lee, edita, ejecuta).
- El modelo local es \"genera-y-escribe\": lee los archivos objetivo, recibe el
  diagnostico de la prueba que falla, genera el codigo corregido y lo escribe.
  No navega el arbol por si mismo, por eso usa ``target_files`` (explicito o
  autodescubierto).

La escritura queda confinada al workspace (se verifica con ``is_relative_to``)
y la entrega se valida ejecutando el ``verify_command`` en el Job Object, igual
que el resto del taller.

Desde la integracion del bucle de auto-reparacion, el especialista no se rinde
a la primera: si el arreglo no supera la verificacion, realimenta el NUEVO
diagnostico (no el de la primera pasada) y pide un nuevo arreglo, hasta
``max_attempts`` ciclos. El numero de intentos y el historial de diagnosticos
quedan registrados en ``DelegatedResult.attempts`` y
``DelegatedResult.verification_history``.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from igris_os.ai import ModelReply, OllamaClient
from igris_os.delegation.claude_specialist import (
    clean_env,
    _changed,
    _snapshot,
)
from igris_os.delegation.contract import DelegatedResult, DelegatedTask
from igris_os.security.sandbox import JobObjectSandbox, SandboxRun

_SOURCE_EXTENSIONS = {".py", ".js", ".ts", ".rs", ".c", ".cpp", ".h",
                      ".java", ".go", ".cs", ".rb", ".php", ".swift"}
_TEST_HINTS = ("test", "spec")


def _is_test_file(name: str) -> bool:
    lowered = name.lower()
    return lowered.startswith("test") or lowered.startswith("spec") or \
        ".test." in lowered or "_test." in lowered or "test_" in lowered


def _discover_targets(workspace: Path) -> tuple[str, ...]:
    """Fuentes editables: archivos de codigo que no parecen tests."""
    sources = sorted(
        path.relative_to(workspace).as_posix()
        for path in workspace.rglob("*")
        if path.is_file() and path.suffix in _SOURCE_EXTENSIONS
        and not _is_test_file(path.name)
    )
    if sources:
        return tuple(sources)
    # Si no hay fuentes claras, todo archivo de codigo es candidato.
    return tuple(sorted(
        path.relative_to(workspace).as_posix()
        for path in workspace.rglob("*")
        if path.is_file() and path.suffix in _SOURCE_EXTENSIONS))


def _build_prompt(task: DelegatedTask, files: dict[str, str],
                  diagnostics: str, attempt: int,
                  max_attempts: int) -> str:
    listing = "\n\n".join(
        f"=== {name} ===\n{content}" for name, content in files.items())
    acceptance = "\n".join(f"- {item}" for item in task.acceptance) or "- (none)"
    constraints = "\n".join(f"- {item}" for item in task.constraints)
    diag = diagnostics[:4000] if diagnostics else "(sin diagnostico)"
    cycle = f"\n\nCYCLE {attempt}/{max_attempts}. " \
        "The previous fix failed; use the NEW diagnostics below, not the " \
        "first failure." if attempt > 1 else ""
    return (
        "You are an elite coding specialist fixing code inside an isolated "
        "workspace.\n\n"
        f"OBJECTIVE:\n{task.objective}\n\n"
        f"ACCEPTANCE CRITERIA:\n{acceptance}\n\n"
        f"CONSTRAINTS:\n{constraints}\n\n"
        f"CURRENT FILES:\n{listing}\n\n"
        f"TEST FAILURE DIAGNOSTICS:\n{diag}{cycle}\n\n"
        'Return ONLY a JSON object with schema '
        '{"files": {"<relative path>": "<full corrected content>"}}. '
        "Include every file you changed with its complete new content. "
        "No markdown, no explanations outside the JSON."
    )


def _parse_edits(text: str, targets: tuple[str, ...]) -> dict[str, str]:
    """Extrae el mapeo archivo -> contenido corregido de la respuesta."""
    stripped = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", stripped,
                     flags=re.IGNORECASE).strip()
    try:
        data = json.loads(cleaned, strict=False)
    except (json.JSONDecodeError, TypeError, ValueError):
        data = None
    if isinstance(data, dict):
        files = data.get("files")
        if isinstance(files, dict):
            edits = {str(k).strip(): str(v) for k, v in files.items()
                     if str(k).strip() and isinstance(v, str)}
            if edits:
                return edits
        for key in ("code", "source"):
            value = data.get(key)
            if isinstance(value, str) and len(targets) == 1 and value.strip():
                return {targets[0]: value.strip()}
    # Fallback: ultimo bloque de codigo delimitado para el unico objetivo.
    blocks = re.findall(r"```[^\n]*\n(.*?)```", stripped, flags=re.DOTALL)
    if len(targets) == 1 and blocks:
        return {targets[0]: blocks[-1].strip()}
    # Fallback: texto entero sin cercas para el unico objetivo.
    if len(targets) == 1:
        body = re.sub(r"^```[^\n]*\n?", "", stripped)
        body = re.sub(r"\n?```\s*$", "", body)
        if body.strip():
            return {targets[0]: body.strip()}
    return {}


class OllamaSpecialist:
    """Especialista local: genera el arreglo con Ollama y verifica en sandbox.

    Ciclo de trabajo (bucle de auto-reparacion):

    1. Si hay ``verify_command``, correrlo primero. Si ya pasa, entregar sin
       gastar tokens (sin cambios del modelo).
    2. Si falla, pedir el arreglo al modelo con el diagnostico REAL.
    3. Escribir los cambios (contenido confinado al workspace).
    4. Re-verificar. Si sigue fallando, realimentar el nuevo diagnostico y
       repetir hasta ``max_attempts`` ciclos.
    """

    def __init__(self, model: str = "qwen2.5-coder:7b",
                 client: OllamaClient | None = None,
                 memory_limit_mb: int = 512,
                 cpu_seconds: int = 60) -> None:
        self.model = model
        self.client = client or OllamaClient()
        self.sandbox = JobObjectSandbox(memory_limit_mb=memory_limit_mb,
                                        cpu_seconds=cpu_seconds)

    def run(self, task: DelegatedTask,
            max_attempts: int = 3) -> DelegatedResult:
        workspace = task.workspace.resolve()
        if not workspace.is_dir():
            return DelegatedResult(False, "Workspace invalido o inexistente",
                                   returncode=-1)

        before = _snapshot(workspace)
        canaries_before = {str(p): _snapshot(p) for p in task.canaries}

        targets = task.target_files or _discover_targets(workspace)
        if not targets:
            return DelegatedResult(
                False, "No se encontraron archivos objetivo para editar",
                returncode=-1)

        files: dict[str, str] = {}
        for rel in targets:
            path = (workspace / rel).resolve()
            if not path.is_relative_to(workspace):
                return DelegatedResult(
                    False, "Archivo objetivo fuera del workspace: " + rel,
                    returncode=-1)
            try:
                files[rel] = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                return DelegatedResult(
                    False, "No se pudo leer el archivo: " + rel,
                    returncode=-1)

        # Verificacion previa: si el workspace ya cumple, no gastar tokens.
        verify = self._verify(task, workspace)
        if verify is not None and verify.returncode == 0:
            after = _snapshot(workspace)
            return DelegatedResult(
                True, "El workspace ya cumple los criterios (sin cambios)",
                returncode=0, verified=True, sandboxed=verify.sandboxed,
                changed_files=_changed(before, after), attempts=0)

        history: list[str] = []
        attempts = 0
        current_files = dict(files)
        diag_text = ""
        if verify is not None and verify.returncode != 0:
            diag_text = (verify.stdout + verify.stderr)[-4000:]

        final_reply = ""

        while attempts < max_attempts:
            attempts += 1
            prompt = _build_prompt(task, current_files, diag_text,
                                   attempts, max_attempts)
            reply: ModelReply = self.client.generate(prompt, self.model)
            if not reply.ok:
                return DelegatedResult(
                    False, "Modelo local sin respuesta: " + (reply.error or ""),
                    returncode=-1)
            final_reply = reply.text

            edits = _parse_edits(reply.text, targets)
            if not edits:
                return DelegatedResult(
                    False, "No se pudo extraer el codigo corregido del modelo",
                    returncode=-1)

            for rel, content in edits.items():
                target = (workspace / rel).resolve()
                if not target.is_relative_to(workspace):
                    return DelegatedResult(
                        False,
                        "El modelo intento escribir fuera del workspace: " + rel,
                        returncode=-1)
                try:
                    target.write_text(content, encoding="utf-8")
                except OSError as exc:
                    return DelegatedResult(
                        False, "Fallo escribiendo " + rel + ": " + str(exc),
                        returncode=-1)

            # Invalida el bytecode viejo: si el arreglo tiene el mismo tamano
            # que el original, Python podria reusar un .pyc obsoleto y
            # verificar mal.
            self._clear_pycache(workspace)

            verify = self._verify(task, workspace)
            sandboxed = verify.sandboxed if verify is not None else False
            if verify is not None:
                verify_output = (verify.stdout + verify.stderr)[-4000:]
                if verify.returncode == 0:
                    break
                history.append(verify_output)
                diag_text = verify_output
                # Aunque la ultima pasada fuera fallida, se hubiera guardado su
                # diagnostico; el siguiente intento lo usa como contexto.
                # Releer los archivos: el contenido ya es el del arreglo previo.
                current_files = {}
                for rel in targets:
                    path = (workspace / rel).resolve()
                    current_files[rel] = path.read_text(encoding="utf-8")
            else:
                # Sin comando de verificacion: el cambio del modelo se entrega.
                break

        after = _snapshot(workspace)
        changed = _changed(before, after)
        violations = tuple(
            str(Path(raw).resolve()) for raw in task.canaries
            if canaries_before.get(str(raw)) != _snapshot(Path(raw)))

        verified: bool | None = None
        if verify is not None:
            verified = verify.returncode == 0

        ok = bool(changed) and verified is not False
        message = "Especialista local completado"
        if verified is False:
            message = ("El arreglo local no supero la verificacion tras " +
                       str(attempts) + " intento(s)")
        elif not changed:
            message = "El modelo no produjo cambios"
        elif attempts > 1:
            message = ("Especialista local reparado en " + str(attempts) +
                       " intentos")
        return DelegatedResult(
            ok, message, returncode=0, stdout=final_reply, stderr="",
            changed_files=changed, verified=verified,
            verify_output=verify_output, sandboxed=sandboxed,
            timed_out=False, containment_violations=violations,
            attempts=attempts, verification_history=tuple(history))

    def _verify(self, task: DelegatedTask,
                workspace: Path) -> SandboxRun | None:
        if not task.verify_command:
            return None
        return self.sandbox.run(list(task.verify_command),
                                timeout=task.timeout_seconds,
                                cwd=str(workspace), env=clean_env())

    @staticmethod
    def _clear_pycache(workspace: Path) -> None:
        for cache_dir in workspace.rglob("__pycache__"):
            if cache_dir.is_dir():
                shutil.rmtree(cache_dir, ignore_errors=True)