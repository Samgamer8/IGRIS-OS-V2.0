# -*- coding: utf-8 -*-
"""Pruebas del especialista delegado (Claude Code).

La E2E determinista usa un ``claude`` fake inyectable: un script Python que
hace de sustituto de la salida del modelo (escribe el arreglo conocido) para
probar el PIPELINE real: contrato -> snapshot -> subproceso confinado ->
contencion -> verificacion. La prueba contra el Claude Code real (autenticado)
queda disponible con ``IGRIS_LIVE_CLAUDE=1``.
"""

import os
import sys

import pytest

from igris_os.delegation import DelegatedSpecialist, DelegatedTask, clean_env
from igris_os.delegation.claude_specialist import (
    _changed,
    _parse_output,
    _snapshot,
)

# Sustituto del modelo: corrige ``buggy.py`` (bug conocido: resta en vez de
# sumar) y emite JSON como lo haria ``claude --output-format json``.
_FAKE_FIX = '''import json
import os
import pathlib


def main():
    target = pathlib.Path(os.getcwd()) / "buggy.py"
    target.write_text(
        "def add(a, b):\\n    return a + b\\n", encoding="utf-8")
    print(json.dumps({"result": "Fixed add() to return the sum.",
                      "total_cost_usd": 0.0}))


if __name__ == "__main__":
    main()
'''

# Sustituto que escribe FUERA del workspace (toca un canario en el directorio
# padre) y devuelve texto plano (no JSON).
_FAKE_CANARY = '''import os
import pathlib


def main():
    canary = pathlib.Path(os.getcwd()).parent / "canary.txt"
    canary.write_text("touched", encoding="utf-8")
    print("done")


if __name__ == "__main__":
    main()
'''


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


# --- Contrato ---

def test_contract_requires_objective(tmp_path):
    with pytest.raises(ValueError):
        DelegatedTask(objective="   ", workspace=tmp_path)


def test_contract_rejects_bad_limits(tmp_path):
    with pytest.raises(ValueError):
        DelegatedTask(objective="x", workspace=tmp_path, max_turns=0)
    with pytest.raises(ValueError):
        DelegatedTask(objective="x", workspace=tmp_path, timeout_seconds=1)


def test_result_contained_property():
    from igris_os.delegation import DelegatedResult
    assert DelegatedResult(True, "ok").contained
    assert not DelegatedResult(
        True, "violo", containment_violations=("C:/x",)).contained


# --- Utilidades ---

def test_clean_env_strips_secrets(monkeypatch):
    monkeypatch.setenv("IGRIS_TEST_API_KEY", "secret")
    monkeypatch.setenv("IGRIS_TEST_NORMAL", "value")
    env = clean_env()
    assert "IGRIS_TEST_API_KEY" not in env
    assert env.get("IGRIS_TEST_NORMAL") == "value"


def test_parse_output_json():
    assert _parse_output('{"result": "hola"}') == "hola"
    assert _parse_output('{"content": [{"type": "text", "text": "x"}]}') == "x"


def test_parse_output_plain():
    assert _parse_output("  done  ") == "done"
    assert _parse_output("") == ""


def test_snapshot_detects_change(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    target = ws / "a.txt"
    target.write_text("1", encoding="utf-8")
    before = _snapshot(ws)
    target.write_text("2", encoding="utf-8")
    assert _changed(before, _snapshot(ws)) == ("a.txt",)


# --- Runner ---

def test_e2e_resolves_python_issue(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _buggy_fixture(workspace)
    fake = tmp_path / "fake_claude.py"
    fake.write_text(_FAKE_FIX, encoding="utf-8")

    specialist = DelegatedSpecialist(
        claude_command=(sys.executable, str(fake)))
    result = specialist.run(DelegatedTask(
        objective="Fix add() so it returns the sum of its arguments",
        workspace=workspace,
        acceptance=("add(2, 3) == 5",),
        verify_command=(sys.executable, "-m", "unittest", "test_buggy"),
    ))

    assert result.ok, result.message
    assert "buggy.py" in result.changed_files
    assert result.verified is True
    assert result.contained
    # El arreglo persistio y las pruebas pasan de verdad.
    assert (workspace / "buggy.py").read_text(encoding="utf-8") == (
        "def add(a, b):\n    return a + b\n")


def test_canary_violation_detected(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "todo.txt").write_text("original", encoding="utf-8")
    canary = tmp_path / "canary.txt"
    canary.write_text("safe", encoding="utf-8")
    fake = tmp_path / "fake_claude_canary.py"
    fake.write_text(_FAKE_CANARY, encoding="utf-8")

    specialist = DelegatedSpecialist(
        claude_command=(sys.executable, str(fake)))
    result = specialist.run(DelegatedTask(
        objective="touch the canary outside the workspace",
        workspace=workspace,
        canaries=(canary,),
    ))

    assert not result.contained
    assert str(canary) in result.containment_violations
    assert canary.read_text(encoding="utf-8") == "touched"


def test_bogus_claude_reports_failure(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    specialist = DelegatedSpecialist(
        claude_command=str(tmp_path / "no_such_claude"))
    result = specialist.run(DelegatedTask(objective="x", workspace=workspace))
    assert not result.ok
    assert result.returncode == -1


@pytest.mark.skipif(
    os.environ.get("IGRIS_LIVE_CLAUDE") != "1",
    reason="Requiere Claude Code autenticado: IGRIS_LIVE_CLAUDE=1")
def test_live_claude_code_e2e(tmp_path):
    """E2E contra el Claude Code REAL (solo con IGRIS_LIVE_CLAUDE=1)."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _buggy_fixture(workspace)
    specialist = DelegatedSpecialist()
    result = specialist.run(DelegatedTask(
        objective="Fix add() so it returns the sum of its arguments",
        workspace=workspace,
        acceptance=("add(2, 3) == 5",),
        verify_command=(sys.executable, "-m", "unittest", "test_buggy"),
    ))
    assert result.ok, result.message
    assert result.verified is True
