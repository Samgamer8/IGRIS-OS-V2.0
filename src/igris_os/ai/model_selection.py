"""Seleccion de modelos basada en capacidades y politica de coste.

El nombre del proveedor no forma parte de la logica del agente. IGRIS puede usar
Ollama, Xinference u OpenAI-compatible remoto sin cambiar el resto del sistema.
"""
import os
import re


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes", "si", "sí", "on"}


def _allow_cloud() -> bool:
    return _truthy(os.environ.get("IGRIS_ALLOW_CLOUD_MODELS"))


def _usable(models):
    names = tuple(dict.fromkeys(name for name in models if isinstance(name, str) and name))
    excluded = ("embed", "minilm", "bge", "mxbai", "stable-code")
    result = []
    for name in names:
        low = name.casefold()
        if any(marker in low for marker in excluded):
            continue
        if ":cloud" in low and not _allow_cloud():
            continue
        if (low.startswith("moonshot/") or low.startswith("cloud/")) and not _allow_cloud():
            continue
        result.append(name)
    return result


def _small(name: str) -> bool:
    size = re.search(r"(?:[:\-/])([0-9]+(?:\.[0-9]+)?)b\b", name.casefold())
    return bool(size and float(size.group(1)) < 4)


def _remote(name: str) -> bool:
    low = name.casefold()
    return low.startswith(("moonshot/", "cloud/")) or ":cloud" in low


def _quality_first() -> bool:
    return os.environ.get("IGRIS_MODEL_POLICY", "local-first").strip().casefold() in {
        "quality", "quality-first", "frontier", "best"
    }


def _frontier(name: str) -> bool:
    low = name.casefold()
    return "kimi-k3" in low or "gpt-5" in low or "claude" in low


def select_installed_model(models, preferred="qwen2.5-coder:7b") -> str:
    names = tuple(name for name in models if isinstance(name, str))
    if preferred in names:
        return preferred
    usable = _usable(names)

    def priority(name):
        low = name.casefold()
        return (
            _remote(name) and not _quality_first(),
            not (_frontier(name) and _quality_first()),
            _small(name),
            "qwen3" not in low,
            "instruct" not in low,
            "qwen" not in low,
            "deepseek-r1" in low,
            name,
        )
    return next(iter(sorted(usable, key=priority)), "")


def coding_model_candidates(models, preferred="") -> tuple[str, ...]:
    """Candidatos para codigo; la calidad real se demuestra con tests, no por nombre."""
    names = tuple(dict.fromkeys(name for name in models if isinstance(name, str) and name))
    explicit = preferred or os.environ.get("IGRIS_PROGRAMMING_MODEL", "").strip()
    if explicit and explicit not in names:
        raise ValueError("El modelo de programacion configurado no esta instalado: " + explicit)
    usable = _usable(names)

    def priority(name):
        low = name.casefold()
        return (
            _remote(name) and not _quality_first(),
            not (_frontier(name) and _quality_first()),
            _small(name),
            "qwen3" not in low,
            "coder" not in low,
            "instruct" not in low,
            "deepseek-r1" in low,
            name,
        )
    ordered = sorted(usable, key=priority)
    if explicit:
        ordered = [explicit] + [name for name in ordered if name != explicit]
    return tuple(ordered)


def select_coding_model(models, preferred="") -> str:
    return next(iter(coding_model_candidates(models, preferred)), "")


def cognitive_model_candidates(models, preferred="") -> tuple[str, ...]:
    """Comprension y planificacion: capacidad primero, modelos diminutos al final."""
    names = tuple(dict.fromkeys(name for name in models if isinstance(name, str) and name))
    explicit = preferred or os.environ.get("IGRIS_COGNITIVE_MODEL", "").strip()
    if explicit and explicit not in names:
        raise ValueError("El modelo cognitivo configurado no esta instalado: " + explicit)
    usable = _usable(names)

    def priority(name):
        low = name.casefold()
        return (
            _remote(name) and not _quality_first(),
            not (_frontier(name) and _quality_first()),
            _small(name),
            "qwen3" not in low,
            "deepseek-r1" not in low,
            "instruct" not in low,
            "coder" in low,
            name,
        )
    ordered = sorted(usable, key=priority)
    if explicit:
        ordered = [explicit] + [name for name in ordered if name != explicit]
    return tuple(ordered)
