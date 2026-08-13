from pathlib import Path

from igris_os.application import CapabilityRegistry, IgrisKernel
from igris_os.capabilities import (
    register_core_capabilities, register_creation_capabilities,
    register_system_health,
)
from igris_os.security import PermissionPolicy
from igris_os.storage.audit import AuditLog
from igris_os.storage.workspace import MissionWorkspace


def build_igris(runtime: Path | None = None) -> IgrisKernel:
    root = Path(runtime or "runtime")
    registry = CapabilityRegistry()
    register_system_health(registry)
    register_core_capabilities(registry)
    register_creation_capabilities(registry)
    return IgrisKernel(
        registry,
        PermissionPolicy(),
        AuditLog(root / "audit" / "events.jsonl"),
        MissionWorkspace(root / "missions"),
    )
