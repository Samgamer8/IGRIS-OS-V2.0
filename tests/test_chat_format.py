"""Tests del formateador puro del chat (sin Qt)."""

from igris_os.ui.chat_format import (
    REASONING_LIMIT,
    chat_reply_html,
)


def test_sin_reasoning_linea_simple():
    html = chat_reply_html("Hola mundo")
    assert "[IGRIS] Hola mundo" in html
    assert "⚙" not in html


def test_razonamiento_incluido_y_atenuado():
    html = chat_reply_html("Respuesta", reasoning="pensamiento interno")
    assert "pensamiento interno" in html
    assert "font-style:italic" in html
    assert "Respuesta" in html
    # el razonamiento va antes de la respuesta
    assert html.index("pensamiento interno") < html.index("Respuesta")


def test_razonamiento_capado():
    largo = "x" * (REASONING_LIMIT + 100)
    html = chat_reply_html("Respuesta", reasoning=largo)
    assert "…" in html
    assert len(largo) not in (len(html),)  # el bloque esta capado


def test_error_con_color_de_advertencia():
    html = chat_reply_html("fallo", ok=False)
    assert "#efb74f" in html


def test_metaincluye_modelo_y_backend():
    html = chat_reply_html("ok", model="qwen2.5-coder:7b", backend="ollama")
    assert "[IGRIS · qwen2.5-coder:7b · ollama]" in html


def test_texto_y_razonamiento_escapados():
    html = chat_reply_html("<script>", reasoning="<b>interno</b>")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;b&gt;interno&lt;/b&gt;" in html
