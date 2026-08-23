from pathlib import Path

from igris_os.application import CapabilityRegistry, IgrisKernel
from igris_os.application.mission_queue import MissionQueue
from igris_os.domain import ActionRisk, CapabilitySpec, ExecutionResult, Mission
from igris_os.security import PermissionPolicy
from igris_os.storage.audit import AuditLog
from igris_os.storage.workspace import MissionWorkspace


def build_kernel(tmp_path: Path):
    registry = CapabilityRegistry()
    kernel = IgrisKernel(
        registry, PermissionPolicy(),
        AuditLog(tmp_path / "audit.jsonl"),
        MissionWorkspace(tmp_path / "missions"))
    return kernel, registry


def test_panel_flow_issues_approval_token_and_executes(tmp_path):
    """Reproduce el flujo del panel (submit -> cola -> run_job):
    el token HMAC se emite al confirmar y viaja en __approval del payload."""
    kernel, registry = build_kernel(tmp_path)
    registry.register(
        CapabilitySpec("write", "escribe", ActionRisk.WRITE_WORKSPACE),
        lambda request: ExecutionResult.success(
            "escrito", workspace=request.get("workspace")))

    objective = "crea un archivo"
    capability = "write"

    # submit(): tras confirmacion, el panel emite el token y lo guarda
    payload = {"__approval": kernel.issue_approval(objective, capability)}

    queue = MissionQueue(tmp_path / "missions_queue.json")
    job = queue.enqueue(objective, "capability", capability, payload)

    # run_job(): ejecuta con approval extraido del payload
    reply = kernel.execute(
        Mission(job.objective), job.capability, job.payload,
        approval=job.payload.get("__approval"))
    queue.finish(job.id, reply.ok, reply.message)

    assert reply.ok
    assert queue.summary()["completed"] == 1


def test_panel_job_without_token_is_denied(tmp_path):
    """Si el payload no lleva __approval, la capacidad con confirmacion se niega."""
    kernel, registry = build_kernel(tmp_path)
    registry.register(
        CapabilitySpec("write", "escribe", ActionRisk.WRITE_WORKSPACE),
        lambda request: ExecutionResult.success("ok"))
    queue = MissionQueue(tmp_path / "missions_queue.json")
    job = queue.enqueue("objetivo", "capability", "write", {})
    reply = kernel.execute(
        Mission(job.objective), job.capability, job.payload,
        approval=job.payload.get("__approval"))
    assert not reply.ok
    assert reply.code == "CONFIRMATION_REQUIRED"
