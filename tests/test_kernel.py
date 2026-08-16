from pathlib import Path

from igris_os.application import CapabilityRegistry, IgrisKernel
from igris_os.domain import ActionRisk, CapabilitySpec, ExecutionResult, Mission
from igris_os.security import PermissionPolicy
from igris_os.storage.audit import AuditLog
from igris_os.storage.workspace import MissionWorkspace


def make_kernel(tmp_path: Path):
    registry = CapabilityRegistry()
    return IgrisKernel(registry, PermissionPolicy(), AuditLog(tmp_path / "audit.jsonl"), MissionWorkspace(tmp_path / "missions")), registry


def test_unknown_capability_is_controlled(tmp_path):
    kernel, _ = make_kernel(tmp_path)
    result = kernel.execute(Mission("prueba"), "missing")
    assert not result.ok
    assert result.code == "NOT_FOUND"


def test_handler_failure_does_not_escape(tmp_path):
    kernel, registry = make_kernel(tmp_path)
    registry.register(CapabilitySpec("broken", "falla", ActionRisk.READ_ONLY), lambda _: 1 / 0)
    result = kernel.execute(Mission("prueba"), "broken")
    assert result.code == "CAPABILITY_FAILED"


def test_write_requires_confirmation(tmp_path):
    kernel, registry = make_kernel(tmp_path)
    registry.register(CapabilitySpec("write", "escribe", ActionRisk.WRITE_WORKSPACE), lambda _: ExecutionResult.success("ok"))
    mission = Mission("prueba")
    denied = kernel.execute(mission, "write")
    token = kernel.issue_approval(mission.objective, "write")
    allowed = kernel.execute(mission, "write", approval=token)
    assert denied.code == "CONFIRMATION_REQUIRED"
    assert allowed.ok


def test_audit_recent_skips_corrupt_lines(tmp_path):
    audit = AuditLog(tmp_path / "audit.jsonl")
    mission = Mission("prueba")
    audit.record(mission, "health", ExecutionResult.success("ok"))
    with audit.path.open("a", encoding="utf-8") as stream:
        stream.write("linea dañada\n")
    events = audit.recent()
    assert len(events) == 1
    assert events[0]["capability"] == "health"


def test_audit_redacts_secrets_in_message_and_stack(tmp_path):
    audit = AuditLog(tmp_path / "audit.jsonl")
    audit.record_execution(
        "m1", "cap", ok=False, code="FAILED",
        message="fallo con token=AKIAIOSFODNN7EXAMPLE y Bearer abcDEF123",
        stack_trace="Traceback... password=supersecreto",
    )
    event = audit.recent()[0]
    assert "AKIAIOSFODNN7EXAMPLE" not in event["message"]
    assert "abcDEF123" not in event["message"]
    assert "supersecreto" not in event["stack_trace"]
    assert "***REDACTED***" in event["message"]


def test_kernel_forwards_progress_callback_to_handler(tmp_path):
    kernel, registry = make_kernel(tmp_path)
    seen = []

    def handler(request):
        callback = request.get("on_progress")
        if callback:
            callback(50, "mitad")
        return ExecutionResult.success("ok")

    registry.register(
        CapabilitySpec("prog", "progreso", ActionRisk.READ_ONLY), handler)
    result = kernel.execute(
        Mission("prueba"), "prog", on_progress=lambda pct, msg: seen.append((pct, msg)))
    assert result.ok
    assert seen == [(50, "mitad")]


def test_kernel_executes_without_progress_callback(tmp_path):
    kernel, registry = make_kernel(tmp_path)
    registry.register(
        CapabilitySpec("plain", "simple", ActionRisk.READ_ONLY),
        lambda request: ExecutionResult.success("ok"))
    assert kernel.execute(Mission("prueba"), "plain").ok
