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

