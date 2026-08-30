import pytest

from igris_os.application.approval import ApprovalAuthority
from igris_os.multi_agent.factory import Department, FactoryOrchestrator
from igris_os.multi_agent.hierarchy import (
    ClarificationGate,
    Evidence,
    Specialist,
)


def specialists(prefix):
    return tuple(
        Specialist(
            f"{prefix}-{index}", prefix,
            lambda order, value=index: order.objective + f" result {value}")
        for index in range(2))


def evaluator(order, proposal):
    del order
    return Evidence(True, 0.8, ("department_contract",))


def test_factory_runs_departments_assembles_and_igris_signs():
    authority = ApprovalAuthority(secret=b"factory-test")
    contract = ClarificationGate().prepare(
        "Build product", "Build verified product",
        ("components pass",), question_sets=())
    departments = (
        Department("design", specialists("design"), evaluator),
        Department(
            "production", specialists("production"), evaluator,
            dependencies=("design",)),
        Department(
            "quality", specialists("quality"), evaluator,
            dependencies=("production",)),
    )
    factory = FactoryOrchestrator(
        departments,
        lambda contract, winners: "|".join(sorted(winners)),
        lambda contract, assembled: Evidence(
            assembled == "design|production|quality", 1.0,
            ("assembly", "acceptance")),
        authority,
        max_active_departments=2,
    )

    result = factory.execute(contract)

    assert result.approved
    assert [item.name for item in result.departments] == [
        "design", "production", "quality"]
    assert authority.consume(
        result.approval_token, result.approval_binding,
        "deliver_factory_result")
    assert not authority.consume(
        result.approval_token, result.approval_binding,
        "deliver_factory_result")


def test_factory_stops_when_department_fails_quality_gate():
    contract = ClarificationGate().prepare(
        "Build", "Build", ("pass",), question_sets=())
    departments = (
        Department(
            "bad", specialists("bad"),
            lambda order, proposal: Evidence(False, 0.0)),
        Department(
            "downstream", specialists("downstream"), evaluator,
            dependencies=("bad",)),
    )
    result = FactoryOrchestrator(
        departments,
        lambda contract, winners: "never",
        lambda contract, assembled: Evidence(True, 1.0),
    ).execute(contract)

    assert not result.approved
    assert [item.name for item in result.departments] == ["bad"]


def test_factory_rejects_dependency_cycle():
    with pytest.raises(ValueError):
        FactoryOrchestrator(
            (
                Department(
                    "a", specialists("a"), evaluator, dependencies=("b",)),
                Department(
                    "b", specialists("b"), evaluator, dependencies=("a",)),
            ),
            lambda contract, winners: "",
            lambda contract, assembled: Evidence(True, 1.0),
        )
