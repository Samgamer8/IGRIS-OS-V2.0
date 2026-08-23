"""Tests para ``igris_os.ui.backend_status`` — helpers puros de la barra
de estado del panel (sin Qt ni IO)."""

from __future__ import annotations

from igris_os.ui.backend_status import (
    build_status_line,
    build_status_tooltip,
    summarize_backends,
)


def test_summarize_backends_shortens_loopback():
    out = summarize_backends([("ollama", "http://127.0.0.1:11434")])
    assert out == ["ollama:11434"]


def test_summarize_backends_skips_duplicates():
    out = summarize_backends([
        ("ollama", "http://127.0.0.1:11434"),
        ("ollama", "http://127.0.0.1:11434"),
        ("openai", "http://127.0.0.1:30000"),
    ])
    assert out == ["ollama:11434", "openai:30000"]


def test_summarize_backends_keeps_non_loopback_host():
    out = summarize_backends([("remote", "http://10.0.0.5:8080")])
    assert out == ["remote:10.0.0.5:8080"]


def test_build_status_line_uses_last_model_and_backend():
    line = build_status_line(
        [("ollama", "http://127.0.0.1:11434")],
        ("gemma4:26b", "qwen2.5-coder:7b"),
        last_backend="ollama",
        last_model="qwen2.5-coder:7b",
    )
    assert line == "qwen2.5-coder:7b · ollama"


def test_build_status_line_falls_back_to_first_model():
    line = build_status_line(
        [("ollama", "http://127.0.0.1:11434")],
        ("qwen2.5-coder:7b",),
    )
    assert line == "qwen2.5-coder:7b · ollama:11434"


def test_build_status_line_multiple_backends():
    line = build_status_line([
        ("ollama", "http://127.0.0.1:11434"),
        ("openai", "http://127.0.0.1:30000"),
    ])
    assert "ollama:11434" in line
    assert "openai:30000" in line


def test_build_status_line_offline():
    line = build_status_line([], ())
    assert "offline" in line


def test_build_status_tooltip_lists_endpoints():
    tip = build_status_tooltip(
        [("ollama", "http://127.0.0.1:11434")],
        endpoint="http://127.0.0.1:30000",
    )
    assert "ollama -> http://127.0.0.1:11434" in tip
    assert "Endpoint IA configurado: http://127.0.0.1:30000" in tip


def test_build_status_tooltip_empty_backends():
    tip = build_status_tooltip([])
    assert "(ninguno alcanzable)" in tip
