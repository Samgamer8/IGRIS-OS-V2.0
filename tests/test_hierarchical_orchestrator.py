import threading

import pytest

from igris_os.application.approval import ApprovalAuthority
from igris_os.multi_agent.hierarchy import (
    ClarificationGate,
    Evidence,
    HierarchicalOrchestrator,
    Specialist,
    WorkOrder,
)


def test_questioners_have_one_bounded_deduplicated_round():
    gate = ClarificationGate(max_questions=2)
    contract = gate.prepare(
        "Haz un juego", "Juego original", ("compila", "es jugable"),
        question_sets=(
            ("Que estilo visual?", "Que plataforma?"),
            ("�Que estilo visual?", "Que controles?"),
        ))

    assert not contract.confirmed
    assert len(contract.clarification_questions) == 2
    with pytest.raises(ValueError):
        contract.to_work_order()

    confirmed = gate.confirm(contract, ("clasico moderno", "Windows"))
    assert confirmed.confirmed
    assert not confirmed.clarification_questions
    assert "INTENT_DIGEST:" in confirmed.to_work_order().context


def test_igris_selects_only_best_verified_proposal():
    authority = ApprovalAuthority(secret=b"test-secret")
    specialists = (
        Specialist("architect-a", "architect", lambda order: "safe design"),
        Specialist("architect-b", "architect", lambda order: "better safe design"),
    )

    def evaluate(order, proposal):
        del order
        score = 0.9 if proposal.specialist == "architect-b" else 0.6
        return Evidence(True, score, ("contract", "tests"))

    decision = HierarchicalOrchestrator(
        specialists, evaluate, approval_authority=authority,
        parallelism=2).execute(
            WorkOrder("build", ("tests pass",)))

    assert decision.approved
    assert decision.winner is not None
    assert decision.winner.proposal.specialist == "architect-b"
    assert authority.verify(
        decision.approval_token, decision.approval_binding,
        "apply_hierarchical_result")
    assert authority.consume(
        decision.approval_token, decision.approval_binding,
        "apply_hierarchical_result")
    assert not authority.consume(
        decision.approval_token, decision.approval_binding,
        "apply_hierarchical_result")


def test_igris_rejects_round_without_objective_evidence():
    specialists = (
        Specialist("one", "programmer", lambda order: "proposal one"),
        Specialist("two", "programmer", lambda order: "proposal two"),
    )
    decision = HierarchicalOrchestrator(
        specialists,
        lambda order, proposal: Evidence(False, 1.0, diagnostics=("failed",)),
    ).execute(WorkOrder("build", ("compile",)))

    assert not decision.approved
    assert decision.winner is None


def test_specialists_run_on_bounded_worker_pool():
    threads: set[str] = set()
    lock = threading.Lock()

    def execute(order):
        del order
        with lock:
            threads.add(threading.current_thread().name)
        return "candidate"

    specialists = tuple(
        Specialist(f"worker-{index}", "programmer", execute)
        for index in range(5))
    decision = HierarchicalOrchestrator(
        specialists,
        lambda order, proposal: Evidence(True, 0.5),
        parallelism=2,
    ).execute(WorkOrder("build", ("valid",)))

    assert decision.approved
    assert 1 <= len(threads) <= 2
    assert len(decision.candidates) == 5


@pytest.mark.parametrize("parallelism", (1, 6))
def test_parallelism_is_restricted_to_safe_user_range(parallelism):
    specialists = (
        Specialist("one", "role", lambda order: "one"),
        Specialist("two", "role", lambda order: "two"),
    )
    with pytest.raises(ValueError):
        HierarchicalOrchestrator(
            specialists, lambda order, proposal: Evidence(True, 1.0),
            parallelism=parallelism)


def test_pool_size_and_scores_fail_closed():
    six = tuple(
        Specialist(f"worker-{index}", "role", lambda order: "candidate")
        for index in range(6))
    with pytest.raises(ValueError):
        HierarchicalOrchestrator(
            six, lambda order, proposal: Evidence(True, 1.0))

    two = six[:2]
    decision = HierarchicalOrchestrator(
        two, lambda order, proposal: Evidence(True, float("nan"))
    ).execute(WorkOrder("build", ("valid",)))
    assert not decision.approved
    assert all(
        "puntuacion no finita" in item.evidence.diagnostics
        for item in decision.candidates)
