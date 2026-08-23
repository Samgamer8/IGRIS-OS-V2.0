from __future__ import annotations

from igris_os.application import CapabilityRegistry
from igris_os.domain import ActionRisk, CapabilitySpec, ExecutionResult
from igris_os.tools.git_ops import MissionGitManager


def register_git_capabilities(registry: CapabilityRegistry) -> None:
    registry.register(
        CapabilitySpec("git.mission.start", "Inicia rama de mision Git",
                       ActionRisk.WRITE_WORKSPACE, True), _git_mission_start)
    registry.register(
        CapabilitySpec("git.mission.checkpoint", "Commit de checkpoint en rama de mision",
                       ActionRisk.WRITE_WORKSPACE, True), _git_mission_checkpoint)
    registry.register(
        CapabilitySpec("git.mission.rollback", "Rollback a commit anterior",
                       ActionRisk.DESTRUCTIVE, True), _git_mission_rollback)
    registry.register(
        CapabilitySpec("git.mission.diff", "Diff de cambios desde inicio de mision",
                       ActionRisk.READ_ONLY), _git_mission_diff)


def _git_mission_start(payload):
    workspace = payload.get("workspace", ".")
    mission_id = str(payload.get("mission_id", "default"))
    description = str(payload.get("description", "mission"))
    mgr = MissionGitManager(workspace, mission_id)
    result = mgr.start_mission(description)
    return ExecutionResult.success(
        "Rama de mision iniciada",
        branch=result.branch,
        message=result.message,
    )


def _git_mission_checkpoint(payload):
    workspace = payload.get("workspace", ".")
    mission_id = str(payload.get("mission_id", "default"))
    message = str(payload.get("message", "checkpoint"))
    mgr = MissionGitManager(workspace, mission_id)
    commit = mgr.checkpoint(message)
    return ExecutionResult.success(
        "Checkpoint creado",
        commit_hash=commit.hash,
        short_hash=commit.short_hash,
        message=commit.message,
        branch=commit.branch,
    )


def _git_mission_rollback(payload):
    workspace = payload.get("workspace", ".")
    mission_id = str(payload.get("mission_id", "default"))
    ref = str(payload.get("ref", ""))
    if not ref:
        return ExecutionResult.failure("Se necesita ref", "GIT_MISSING_REF")
    mgr = MissionGitManager(workspace, mission_id)
    result = mgr.rollback(ref)
    return ExecutionResult.success(
        "Rollback completado",
        branch=result.branch,
        message=result.message,
    )


def _git_mission_diff(payload):
    workspace = payload.get("workspace", ".")
    mission_id = str(payload.get("mission_id", "default"))
    mgr = MissionGitManager(workspace, mission_id)
    diffs = mgr.diff_since_start()
    return ExecutionResult.success(
        "Diff calculado",
        files=[{"file": d.file, "additions": d.additions, "deletions": d.deletions}
               for d in diffs],
    )
