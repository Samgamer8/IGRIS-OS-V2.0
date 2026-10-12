"""Tests del ConsentGate (IGRIS pide permiso antes de pasos de alto calado)."""
from __future__ import annotations

from igris_os.application.consent import ConsentGate, Proposal


def _gate() -> ConsentGate:
    return ConsentGate()


def test_no_pending_by_default():
    gate = _gate()
    assert not gate.has_pending()
    assert gate.pending is None


def test_propose_returns_question_and_stores_pending():
    gate = _gate()
    text = gate.propose("¿Cablear el FallbackChain?", "Editar assistant.py")
    assert "¿Cablear el FallbackChain?" in text
    assert "Responde 'si'" in text
    assert gate.has_pending()
    assert gate.pending.action_id == ""


def test_interpret_affirmative_variants():
    gate = _gate()
    for word in ("si", "sí", "claro", "adelante", "hazlo", "vale", "ok"):
        assert gate.interpret(word) == "yes", word


def test_interpret_negative_variants():
    gate = _gate()
    for word in ("no", "nop", "espera", "mejor no", "luego", "cancela"):
        assert gate.interpret(word) == "no", word


def test_ambiguous_is_unclear_not_no():
    gate = _gate()
    assert gate.interpret("no se, quizas mas tarde") == "unclear"
    assert gate.interpret("") == "unclear"
    assert gate.interpret("  ") == "unclear"


def test_accept_runs_handler_and_clears_pending():
    gate = _gate()
    fired = {"n": 0}

    def handler():
        fired["n"] += 1
        return "hecho"

    gate.propose("¿Hago X?", "Ejecutar X", handler=handler)
    outcome = gate.resolve("si")
    assert outcome["decision"] == "accepted"
    assert fired["n"] == 1
    assert outcome["result"] == "hecho"
    assert not gate.has_pending()


def test_reject_does_not_run_handler():
    gate = _gate()
    fired = {"n": 0}
    gate.propose("¿Hago X?", "Ejecutar X",
                 handler=lambda: fired.__setitem__("n", fired["n"] + 1))
    outcome = gate.resolve("no")
    assert outcome["decision"] == "rejected"
    assert fired["n"] == 0
    assert not gate.has_pending()


def test_unclear_keeps_pending_and_asks_again():
    gate = _gate()
    gate.propose("¿Hago X?", "Ejecutar X")
    outcome = gate.resolve("mmmm no estoy seguro")
    assert outcome["decision"] == "unclear"
    assert gate.has_pending()  # sigue a la espera
    assert "¿Hago X?" in outcome["reason"]


def test_resolve_without_pending_is_safe():
    gate = _gate()
    outcome = gate.resolve("si")
    assert outcome["decision"] == "unclear"
    assert outcome["proposal"] is None


def test_handler_can_be_absent_on_accept():
    gate = _gate()
    gate.propose("¿Hago X?", "Ejecutar X")
    outcome = gate.resolve("claro")
    assert outcome["decision"] == "accepted"
    assert outcome["result"] is None


def test_cancel_clears_pending():
    gate = _gate()
    gate.propose("¿Hago X?", "Ejecutar X")
    gate.cancel()
    assert not gate.has_pending()
