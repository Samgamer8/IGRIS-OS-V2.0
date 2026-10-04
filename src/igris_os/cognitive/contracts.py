"""Contratos de acciones entre el Cognitive Core y el kernel.

El LLM nunca entrega un comando de shell como autoridad. El runtime traduce la
intención a una capability conocida y este módulo valida el payload antes de que
el kernel evalúe permisos o ejecute el handler.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Mapping


class ContractViolation(ValueError):
    """El payload no cumple el contrato de una capability protegida."""


@dataclass(frozen=True, slots=True)
class CompiledAction:
    capability: str
    payload: dict[str, Any]
    contract: str


_DRIVE = re.compile(r"^[A-Za-z]:$")


def _text(value: Any, name: str, *, max_len: int = 8000, required: bool = False) -> str:
    result = str(value or "").strip()
    if required and not result:
        raise ContractViolation(f"Falta {name}")
    if len(result) > max_len:
        raise ContractViolation(f"{name} supera el límite de {max_len} caracteres")
    return result


def _boolean(value: Any, name: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ContractViolation(f"{name} debe ser booleano")


def _strict_keys(payload: Mapping[str, Any], allowed: set[str]) -> None:
    extra = set(payload) - allowed
    if extra:
        raise ContractViolation("Campos no permitidos: " + ", ".join(sorted(extra)))


def validate_capability_payload(capability: str, payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """Valida contratos de las capabilities de mayor impacto.

    Las capacidades históricas no listadas conservan compatibilidad. Las nuevas
    capacidades de administración Windows usan contratos cerrados para impedir
    que el modelo inyecte comandos o argumentos no previstos por el kernel.
    """
    raw = dict(payload or {})

    if capability == 'image.neural_sphere':
        raw.pop('__approval', None)
        _strict_keys(raw, {'count', 'width', 'height'})
        result = {'count': 2, 'width': 1920, 'height': 1080}
        result.update(raw)
        for key, value in result.items():
            if isinstance(value, bool) or not isinstance(value, int):
                raise ContractViolation(key + ' debe ser entero')
        if result['count'] not in {1, 2} or not 640 <= result['width'] <= 2560 or not 480 <= result['height'] <= 1440:
            raise ContractViolation('Resolucion o numero de esferas fuera de limites')
        if result['width'] < result['height'] or result['width'] * result['height'] > 3_686_400:
            raise ContractViolation('Se requiere un formato horizontal acotado')
        return result

    if capability == "host.windows.diagnose":
        allowed = {"visible_console", "semantic_goal", "optimization_requested"}
        _strict_keys(raw, allowed)
        result: dict[str, Any] = {}
        if "visible_console" in raw:
            result["visible_console"] = _boolean(raw["visible_console"], "visible_console")
        if "optimization_requested" in raw:
            result["optimization_requested"] = _boolean(
                raw["optimization_requested"], "optimization_requested")
        if "semantic_goal" in raw:
            result["semantic_goal"] = _text(raw["semantic_goal"], "semantic_goal", max_len=2000)
        return result

    if capability == "host.windows.repair":
        allowed = {"semantic_goal"}
        _strict_keys(raw, allowed)
        result = {}
        if "semantic_goal" in raw:
            result["semantic_goal"] = _text(raw["semantic_goal"], "semantic_goal", max_len=2000)
        return result

    if capability == "host.windows.disk_repair":
        allowed = {"drive", "recover_bad_sectors", "reboot"}
        _strict_keys(raw, allowed)
        drive = _text(raw.get("drive", "C:"), "drive", max_len=3)
        if not _DRIVE.fullmatch(drive):
            raise ContractViolation("drive debe tener formato C:")
        result = {"drive": drive.upper()}
        for key in ("recover_bad_sectors", "reboot"):
            if key in raw:
                result[key] = _boolean(raw[key], key)
        return result

    if capability == "host.windows.memory_diagnostic":
        _strict_keys(raw, set())
        return {}

    if capability == "programming.mission":
        # Contrato deliberadamente compatible con las reanudaciones existentes:
        # valida campos críticos sin romper metadatos internos de la cola.
        result = dict(raw)
        result["objective"] = _text(raw.get("objective"), "objective", required=True, max_len=12000)
        if "semantic_goal" in raw:
            result["semantic_goal"] = _text(raw["semantic_goal"], "semantic_goal", max_len=4000)
        if "semantic_intent" in raw:
            result["semantic_intent"] = _text(raw["semantic_intent"], "semantic_intent", max_len=80)
        if "root" in raw and str(raw.get("root") or "").strip():
            root = Path(str(raw["root"])).expanduser()
            result["root"] = str(root)
        if "requires_existing" in raw:
            result["requires_existing"] = _boolean(raw["requires_existing"], "requires_existing")
        if "allow_downloads" in raw:
            result["allow_downloads"] = _boolean(raw["allow_downloads"], "allow_downloads")
        if "max_calls" in raw:
            try:
                calls = int(raw["max_calls"])
            except (TypeError, ValueError) as exc:
                raise ContractViolation("max_calls debe ser entero") from exc
            if not 1 <= calls <= 64:
                raise ContractViolation("max_calls fuera de rango [1,64]")
            result["max_calls"] = calls
        if "max_seconds" in raw:
            try:
                seconds = int(raw["max_seconds"])
            except (TypeError, ValueError) as exc:
                raise ContractViolation("max_seconds debe ser entero") from exc
            if not 30 <= seconds <= 3600:
                raise ContractViolation("max_seconds fuera de rango [30,3600]")
            result["max_seconds"] = seconds
        return result

    return raw


def compile_action(capability: str, payload: Mapping[str, Any] | None) -> CompiledAction:
    normalized = validate_capability_payload(capability, payload)
    contract = "strict" if capability.startswith("host.windows.") else (
        "programming" if capability == "programming.mission" else "legacy-compatible")
    return CompiledAction(capability=capability, payload=normalized, contract=contract)
