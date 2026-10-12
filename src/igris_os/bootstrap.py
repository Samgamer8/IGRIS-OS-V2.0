import os
from pathlib import Path

from igris_os.application import CapabilityRegistry, IgrisKernel
from igris_os.capabilities import (
    register_core_capabilities, register_creation_capabilities,
    register_git_capabilities, register_voice_capabilities, register_system_health,
)
from igris_os.security import PermissionPolicy, SecurityAuditLogger
from igris_os.storage.audit import AuditLog
from igris_os.storage.workspace import MissionWorkspace
from igris_os.capabilities.host import register_host_capabilities
from igris_os.capabilities.reverse_engineering import register_reverse_engineering


def build_igris(runtime: Path | None = None) -> IgrisKernel:
    root = Path(runtime or "runtime")
    registry = CapabilityRegistry()
    register_system_health(registry)
    register_core_capabilities(registry)
    register_host_capabilities(registry)
    register_creation_capabilities(registry)
    register_git_capabilities(registry)
    register_voice_capabilities(registry)
    register_reverse_engineering(registry)
    approval = None
    endpoint = os.environ.get("IGRIS_SAMADMIN_URL", "").strip()
    if endpoint:
        from igris_os.samadmin import SamadminApprovalAuthority, SamadminClient
        approval = SamadminApprovalAuthority(SamadminClient(endpoint))
    return IgrisKernel(
        registry,
        PermissionPolicy(SecurityAuditLogger(root / "logs" / "security_audit.jsonl")),
        AuditLog(root / "audit" / "events.jsonl"),
        MissionWorkspace(root / "missions"),
        approval=approval,
    )
