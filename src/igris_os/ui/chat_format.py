"""Formateo puro del chat del panel (sin dependencias Qt, testeable).

Centraliza como se compone una respuesta de IGRIS en el widget de chat:
encabezado con modelo/backend y, cuando el modelo devuelve razonamiento,
un bloque atenuado con la cadena de pensamiento antes de la respuesta final.
"""

from __future__ import annotations

from html import escape

REASONING_LIMIT = 800
WARN_COLOR = "#efb74f"
REASON_COLOR = "#8a93a6"


def _cap(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


def _header(model: str, backend: str, ok: bool) -> str:
    meta = " · ".join(part for part in (model, backend) if part)
    head = f"[IGRIS{(' · ' + meta) if meta else ''}]"
    if not ok:
        head = f'<span style="color:{WARN_COLOR}">{escape(head)}</span>'
    return head


def chat_reply_html(
    text: str,
    reasoning: str = "",
    model: str = "",
    backend: str = "",
    ok: bool = True,
) -> str:
    """Fragmento HTML para ``QTextEdit.append`` de una respuesta de IGRIS.

    El razonamiento se muestra atenuado y en cursiva antes de la respuesta,
    capado a REASONING_LIMIT caracteres para no inundar el chat. El texto y
    el razonamiento se escapan para evitar romper el HTML del widget.
    """
    head = _header(model, backend, ok)
    body = escape(text)
    if reasoning:
        block = (
            f'<span style="color:{REASON_COLOR};font-style:italic;">'
            f"⚙ {escape(_cap(reasoning, REASONING_LIMIT))}</span><br>"
        )
        return f"<br>{head} {block}{body}"
    return f"<br>{head} {body}"
