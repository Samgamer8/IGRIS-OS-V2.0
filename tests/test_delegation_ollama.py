# -*- coding: utf-8 -*-
"""Pruebas del especialista local (Ollama) y la cadena con fallback.

Usan un cliente fake (duck-typed) que sustituye la llamada HTTP a Ollama,
devolviendo el arreglo conocido. El resto del pipeline es real: descubrimiento
de archivos, escritura confinada al workspace, verificacion en el Job Object y
deteccion de escrituras fuera del workspace.
"""

import json
import sys

import pytest

from igris_os.ai import ModelReply
from igris_os.delegation import (
    DelegatedResult,
    DelegatedTask,
    OllamaSpecialist,
    ResilientSpecialist,
    build_resilient_specialist,
)
from igris_os.delegation.ollama_specialist import (
    _discover_targets,
    _parse_edits,
)


class _FakeClient:
    def __init__(self, text: str, ok: bool = True, error: str = "") -> None:
        self.text = text
        self.ok = ok
        self.error = error

    def generate(self, prompt: str, model: str) -> ModelReply:
        return ModelReply(self.ok, self.text, model, self.error)


class _AlwaysFail:
    def run(self, task) -> DelegatedResult:
        return DelegatedResult(False, "primary down", returncode=1)


def _buggy_fixture(workspace) -> None:
    (workspace / "buggy.py").write_text(
        "def add(a, b):\n    return a - b\n", encoding="utf-8")
    (workspace / "test_buggy.py").write_text(
        "import unittest\n"
        "from buggy import add\n"
        "class TestAdd(unittest.TestCase):\n"
        "    def test_add(self):\n"
        "        self.assertEqual(add(2, 3), 5)\n",
        encoding="utf-8")


def _fix_reply() -> str:
    return json.dumps({"files": {"buggy.py": "def add(a, b):\n    return a + b\n"}})


# --- Parseo y descubrimiento ---

def test_parse_edits_json():
    edits = _parse_edits(_fix_reply(), ("buggy.py",))
    assert edits["buggy.py"] == "def add(a, b):\n    return a + b\n"


def test_parse_edits_fenced_fallback():
    text = "```python\ndef add(a, b):\n    return a + b\n```"
    assert _parse_edits(text, ("buggy.py",))["buggy.py"] == (
        "def add(a, b):\n    return a + b")


def test_discover_targets_excludes_tests(tmp_path):
    _buggy_fixture(tmp_path)
    assert _discover_targets(tmp_path) == ("buggy.py",)


# --- Especialista local ---

def test_ollama_specialist_resolves_issue(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _buggy_fixture(workspace)
    specialist = OllamaSpecialist(
        model="qwen2.5-coder:7b", client=_FakeClient(_fix_reply()))
    result = specialist.run(DelegatedTask(
        objective="Fix add() so it returns the sum",
        workspace=workspace,
        acceptance=("add(2, 3) == 5",),
        verify_command=(sys.executable, "-m", "unittest", "test_buggy"),
    ))
    assert result.ok, result.message
    assert result.changed_files == ("buggy.py",)
    assert result.verified is True
    assert result.contained
    assert (workspace / "buggy.py").read_text(encoding="utf-8") == (
        "def add(a, b):\n    return a + b\n")


def test_ollama_specialist_blocks_outside_write(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "buggy.py").write_text("def add(a, b):\n    return a - b\n",
                                        encoding="utf-8")
    evil = json.dumps({"files": {"../evil.py": "x = 1"}})
    specialist = OllamaSpecialist(
        model="qwen2.5-coder:7b", client=_FakeClient(evil))
    result = specialist.run(DelegatedTask(
        objective="escape", workspace=workspace,
        target_files=("buggy.py",)))
    assert not result.ok
    assert "fuera del workspace" in result.message
    assert not (tmp_path / "evil.py").exists()


def test_ollama_specialist_model_down(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "buggy.py").write_text("def add(a, b):\n    return a - b\n",
                                        encoding="utf-8")
    specialist = OllamaSpecialist(
        model="qwen2.5-coder:7b",
        client=_FakeClient("", ok=False, error="connection refused"))
    result = specialist.run(DelegatedTask(
        objective="fix", workspace=workspace, target_files=("buggy.py",)))
    assert not result.ok
    assert "connection refused" in result.message


# --- Cadena resiliente ---

def test_resilient_falls_back_to_ollama(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _buggy_fixture(workspace)
    local = OllamaSpecialist(
        model="qwen2.5-coder:7b", client=_FakeClient(_fix_reply()))
    chain = ResilientSpecialist([_AlwaysFail(), local])
    result = chain.run(DelegatedTask(
        objective="Fix add()", workspace=workspace,
        verify_command=(sys.executable, "-m", "unittest", "test_buggy"),
    ))
    assert result.ok
    assert result.verified is True


def test_resilient_returns_failure_when_all_fail(tmp_path):
    chain = ResilientSpecialist([_AlwaysFail(), _AlwaysFail()])
    result = chain.run(DelegatedTask(
        objective="x", workspace=tmp_path))
    assert not result.ok


def test_build_resilient_specialist_has_local_fallback():
    chain = build_resilient_specialist(local_model="qwen2.5-coder:7b")
    assert isinstance(chain, ResilientSpecialist)
    assert any(isinstance(s, OllamaSpecialist) for s in chain.specialists)


# --- Bucle de auto-reparacion ---

class _RecordingClient:
    """Devuelve respuestas en secuencia y registra cuantas llamadas hubo."""

    def __init__(self, *texts: str) -> None:
        self.texts = list(texts)
        self.calls = 0

    def generate(self, prompt: str, model: str) -> ModelReply:
        self.calls += 1
        if self.calls > len(self.texts):
            return ModelReply(False, "", model, "no more replies")
        return ModelReply(True, self.texts[self.calls - 1], model, "")


def _times_reply() -> str:
    return json.dumps({"files": {"buggy.py": "def add(a, b):\n    return a * b\n"}})


def _unittest_verify() -> tuple[str, ...]:
    return (sys.executable, "-m", "unittest", "test_buggy")


def test_delegation_repairs_in_loop(tmp_path):
    """Primer arreglo erroneo -> realimenta el nuevo diagnostico -> segundo acierta."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _buggy_fixture(workspace)  # add() resta en vez de sumar
    client = _RecordingClient(_times_reply(), _fix_reply())
    specialist = OllamaSpecialist(model="qwen2.5-coder:7b", client=client)
    result = specialist.run(DelegatedTask(
        objective="Fix add() so it returns the sum",
        workspace=workspace,
        acceptance=("add(2, 3) == 5",),
        verify_command=_unittest_verify(),
    ), max_attempts=3)
    assert result.ok, result.message
    assert result.verified is True
    assert result.attempts == 2
    assert len(result.verification_history) == 1  # solo el primer fallo
    assert client.calls == 2
    assert (workspace / "buggy.py").read_text(encoding="utf-8") == (
        "def add(a, b):\n    return a + b\n")


def test_delegation_gives_up_after_max_attempts(tmp_path):
    """Si el modelo no acierta, se rinde sin loop infinito ni mitad de cambios."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _buggy_fixture(workspace)
    client = _RecordingClient(_times_reply(), _times_reply())
    specialist = OllamaSpecialist(model="qwen2.5-coder:7b", client=client)
    result = specialist.run(DelegatedTask(
        objective="Fix add() so it returns the sum",
        workspace=workspace,
        verify_command=_unittest_verify(),
    ), max_attempts=2)
    assert not result.ok
    assert "no supero la verificacion" in result.message
    assert result.attempts == 2
    assert result.verified is False
    assert len(result.verification_history) == 2
    assert client.calls == 2


def test_delegation_skips_model_when_already_ok(tmp_path):
    """Si el workspace ya cumple los criterios, no se llama al modelo."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "ok.py").write_text("def add(a, b):\n    return a + b\n",
                                     encoding="utf-8")
    (workspace / "test_ok.py").write_text(
        "import unittest\n"
        "from ok import add\n"
        "class T(unittest.TestCase):\n"
        "    def test_add(self):\n"
        "        self.assertEqual(add(2, 3), 5)\n",
        encoding="utf-8")
    client = _RecordingClient()
    specialist = OllamaSpecialist(model="qwen2.5-coder:7b", client=client)
    result = specialist.run(DelegatedTask(
        objective="Fix add()", workspace=workspace,
        verify_command=(sys.executable, "-m", "unittest", "test_ok"),
    ))
    assert result.ok, result.message
    assert result.verified is True
    assert result.attempts == 0
    assert result.changed_files == ()
    assert client.calls == 0
