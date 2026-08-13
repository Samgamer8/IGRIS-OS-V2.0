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
    denied = kernel.execute(Mission("prueba"), "write")
    allowed = kernel.execute(Mission("prueba"), "write", confirmed=True)
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
