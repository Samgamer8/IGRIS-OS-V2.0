from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from igris_os.ai import OllamaClient
from igris_os.application.node_staging_final import FinalNodeStagingDeveloper
from igris_os.application.project_mission import ProjectMissionFactory
from igris_os.application.project_planning import ProjectMissionPlanner
from igris_os.domain import ActionRisk, CapabilitySpec, ExecutionResult
from igris_os.production_bootstrap_final import build_final_igris


NODE_CAPABILITY = "programming.node.develop"


def _develop_node(payload):
    technology = str(payload.get("technology", "javascript")).casefold()
    if technology not in {"javascript", "typescript", "web"}:
        return ExecutionResult.failure(
            "Tecnologia Node no soportada", "NODE_TECHNOLOGY_UNSUPPORTED")
    workspace = Path(payload["workspace"]).resolve()
    answers = {
        "technology": technology,
        "delivery": "source_and_web" if technology == "web" else "source",
        "destination": str(workspace),
        "acceptance": str(payload.get("acceptance", "las pruebas pasan")),
        "constraints": str(payload.get("constraints", "sin red; sin child_process")),
        "name": str(payload.get("name", "proyecto_node")),
    }
    try:
        mission = ProjectMissionFactory().create(
            str(payload.get("objective", "")), answers)
        planned = ProjectMissionPlanner().plan(mission)
        staging = FinalNodeStagingDeveloper(
            OllamaClient(timeout=float(payload.get("timeout", 240))),
            workspace, str(payload.get("model", "qwen2.5-coder:7b")),
        ).stage(planned)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        return ExecutionResult.failure(str(exc), "NODE_DEVELOPMENT_FAILED")
    delivered = ""
    destination = str(payload.get("delivery_root", "")).strip()
    if destination:
        delivery_root = Path(destination).expanduser().resolve()
        if not delivery_root.is_dir():
            return ExecutionResult.failure(
                "La carpeta de entrega no existe", "DELIVERY_PATH_INVALID")
        target = delivery_root / staging.root.name
        if target.exists():
            return ExecutionResult.failure(
                "La entrega Node no sobrescribe destinos", "DELIVERY_PATH_EXISTS")
        shutil.copytree(staging.root, target)
        delivered = str(target)
    return ExecutionResult.success(
        "Proyecto Node compilado y probado",
        technology=technology, staged_project=str(staging.root),
        changed_files=staging.changed_files, delivered_project=delivered,
        verified=True,
    )


def build_release_igris(runtime: Path | None = None):
    kernel = build_final_igris(runtime)
    if shutil.which("node") is not None:
        kernel.registry.register(
            CapabilitySpec(
                NODE_CAPABILITY,
                "Genera JavaScript/TypeScript y exige compilacion y node:test",
                ActionRisk.WRITE_WORKSPACE,
                True,
                timeout_seconds=300,
            ),
            _develop_node,
        )
    return kernel
