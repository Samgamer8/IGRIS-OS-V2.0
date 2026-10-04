"""Estado de backends para la barra de estado del panel (sin Qt).

Funciones puras y testeables que resumen los backends detectados y el
ultimo modelo/backend usado en una linea corta para la barra de estado
de ``cinematic.py``. No hacen IO ni dependen de la capa grafica.
"""

from __future__ import annotations

from typing import Any


def _short_endpoint(endpoint: str) -> str:
    """Acorta una URL para la etiqueta: loopback -> solo puerto.

    ``http://127.0.0.1:11434`` -> ``11434``; el resto conserva host:puerto.
    """
    if endpoint.startswith(("http://127.0.0.1", "http://localhost")):
        try:
            return str(endpoint.rsplit(":", 1)[1])
        except IndexError:
            return endpoint
    return endpoint.replace("http://", "").replace("https://", "")


def summarize_backends(backends: list[tuple[str, str]]) -> list[str]:
    """Convierte ``[(nombre, endpoint), ...]`` en etiquetas cortas.

    Ej: ``[("ollama", "http://127.0.0.1:11434")]`` -> ``["ollama:11434"]``.
    Elimina duplicados conservando el orden de preferencia.
    """
    seen: set[str] = set()
    labels: list[str] = []
    for name, endpoint in backends:
        label = f"{name}:{_short_endpoint(endpoint)}"
        if label not in seen:
            seen.add(label)
            labels.append(label)
    return labels


def build_status_line(
    backends: list[tuple[str, str]],
    models: tuple[str, ...] = (),
    last_backend: str = "",
    last_model: str = "",
    endpoint: str = "",
) -> str:
    """Linea corta de estado: ultimo modelo usado + backend activo.

    Si ya hubo una respuesta, muestra el modelo/backend que la atendio
    (mas informativo); si no, el primer modelo instalado y los backends
    alcanzables. Sin backends detectados -> ``offline``.
    """
    del endpoint  # el endpoint configurado ya aparece en el tooltip
    active = summarize_backends(backends)
    if not active:
        return "offline · sin servidor IA disponible"
    model = last_model if last_model in models else (models[0] if models else "")
    if last_backend and last_backend in {name for name, _ in backends} and model:
        parts = [part for part in (model, last_backend) if part]
    else:
        parts = [model] if model else []
        parts.append(", ".join(active))
        if not models:
            parts.append("sin modelos anunciados")
    return " · ".join(parts) if parts else "offline"


def build_status_tooltip(
    backends: list[tuple[str, str]],
    endpoint: str = "",
) -> str:
    """Tooltip detallado: backends detectados y endpoint configurado."""
    lines = ["Backends detectados:"]
    if backends:
        for name, ep in backends:
            lines.append(f"  {name} -> {ep}")
    else:
        lines.append("  (ninguno alcanzable)")
    if endpoint:
        lines.append(f"Endpoint IA configurado: {endpoint}")
    return "\n".join(lines)
