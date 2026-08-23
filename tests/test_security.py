from pathlib import Path

import pytest

from igris_os.application import CapabilityRegistry
from igris_os.domain import ActionRisk, CapabilitySpec
from igris_os.security import PermissionPolicy
from igris_os.storage.workspace import MissionWorkspace


def test_destructive_capability_is_always_denied():
    decision = PermissionPolicy().evaluate(CapabilitySpec("delete", "borra", ActionRisk.DESTRUCTIVE), confirmed=True)
    assert not decision.allowed


def test_duplicate_capabilities_are_rejected():
    registry = CapabilityRegistry()
    spec = CapabilitySpec("same", "uno", ActionRisk.READ_ONLY)
    registry.register(spec, lambda _: None)
    with pytest.raises(ValueError):
        registry.register(spec, lambda _: None)


def test_workspace_rejects_path_traversal(tmp_path: Path):
    workspaces = MissionWorkspace(tmp_path / "missions")
    with pytest.raises(ValueError):
        workspaces.create("../escape")


def test_workspace_builds_expected_layout(tmp_path: Path):
    target = MissionWorkspace(tmp_path / "missions").create("abc123")
    assert target.is_relative_to((tmp_path / "missions").resolve())
    assert all((target / name).is_dir() for name in ("input", "working", "output", "tests", "logs"))

