# -*- coding: utf-8 -*-
"""Contrato de especialista delegado.

El director de misiones no compite con los agentes de codificacion existentes
(Claude Code, Aider...): los ORQUESTA. Este contrato define el acuerdo minimo
para entregar una tarea a un especialista externo y recibir un resultado
verificable:

- ``DelegatedTask``: que se pide, donde se trabaja (workspace aislado), que
  criterios de aceptacion hay y con que limites (herramientas, turnos, tiempo).
- ``DelegatedResult``: que se obtuvo, que archivos cambiaron (siempre dentro
  del workspace), si se verifico (comando de pruebas exitoso) y si se detecto
  alguna violacion de contencion (canarios tocados).

La contencion se DETECTA (snapshot antes/despues + canarios), no se impone por
sistema de archivos: el Job Object limita CPU/memoria, pero el especialista
corre con los permisos del usuario. La garantia dura de aislamiento sigue siendo
AppContainer/Windows Sandbox (trabajo futuro documentado).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# Herramientas minimas y seguras para una tarea de codigo. Se restringe Bash a
# prefijos concretos (git, python, pytest) para reducir la superficie de riesgo.
DEFAULT_ALLOWED_TOOLS: tuple[str, ...] = (
    "Read",
    "Edit",
    "Write",
    "Bash(git:*)",
    "Bash(python:*)",
    "Bash(pytest:*)",
)


@dataclass(frozen=True, slots=True)
class DelegatedTask:
    """Tarea entregada a un especialista externo."""

    objective: str
    workspace: Path
    acceptance: tuple[str, ...] = field(default_factory=tuple)
    constraints: tuple[str, ...] = field(default_factory=tuple)
    max_turns: int = 20
    timeout_seconds: int = 600
    model: str = ""
    allowed_tools: tuple[str, ...] = DEFAULT_ALLOWED_TOOLS
    # Archivos que el especialista puede editar (relativos al workspace).
    # Vacio = autodescubrimiento (fuentes no-test). Requerido por el
    # especialista local, que no navega el arbol por si mismo.
    target_files: tuple[str, ...] = field(default_factory=tuple)
    # Comando (relativo al workspace) que verifica la entrega. Exit 0 = ok.
    verify_command: tuple[str, ...] = field(default_factory=tuple)
    # Archivos/carpetas que NO deben cambiar; cualquier cambio = violacion.
    canaries: tuple[Path, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.objective.strip():
            raise ValueError("El objetivo de la tarea no puede estar vacio")
        if self.max_turns < 1 or self.max_turns > 200:
            raise ValueError("max_turns fuera de rango [1, 200]")
        if self.timeout_seconds < 5 or self.timeout_seconds > 7200:
            raise ValueError("timeout_seconds fuera de rango [5, 7200]")


@dataclass(frozen=True, slots=True)
class DelegatedResult:
    """Resultado verificable de un especialista externo."""

    ok: bool
    message: str
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""
    changed_files: tuple[str, ...] = field(default_factory=tuple)
    verified: bool | None = None  # None = sin comando de verificacion
    verify_output: str = ""
    sandboxed: bool = False
    timed_out: bool = False
    containment_violations: tuple[str, ...] = field(default_factory=tuple)
    # Numero de ciclos generar+verificar que necesito el especialista para
    # entregar un resultado valido (0 = sin reparaciones necesarias).
    attempts: int = 0
    # Diagnostico de cada intento fallido (uno por intento, en orden).
    verification_history: tuple[str, ...] = field(default_factory=tuple)

    @property
    def contained(self) -> bool:
        return not self.containment_violations
