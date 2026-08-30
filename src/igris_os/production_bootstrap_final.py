from __future__ import annotations

import shutil
from pathlib import Path

from igris_os.domain import ActionRisk, CapabilitySpec, ExecutionResult
from igris_os.games.export import GodotExporter
from igris_os.games.verified_3d import VerifiedGodot3DFactory
from igris_os.games.verifier import GameVerifier
from igris_os.production_bootstrap import build_production_igris


CAPABILITY = "games.godot.3d.build"


def _build_verified_3d(payload):
    workspace = Path(payload["workspace"])
    try:
        project = VerifiedGodot3DFactory(workspace).create(
            str(payload.get("name", "IGRIS 3D")), confirmed=True)
    except (ValueError, PermissionError, OSError) as exc:
        return ExecutionResult.failure(str(exc), "GAME_3D_CREATE_FAILED")
    playtest = GameVerifier().playtest(
        project, workspace, frames=min(120, max(10, int(payload.get("frames", 20)))))
    if not playtest.ok:
        return ExecutionResult(
            ok=False, code="GAME_3D_PLAYTEST_FAILED", message=playtest.message,
            data={"project": str(project), "capture": playtest.capture_path})
    executable = ""
    if bool(payload.get("export", False)):
        exported = GodotExporter().export(
            project, workspace / "build" / "igris_3d.exe",
            confirmed=True, launch_check=bool(payload.get("launch_check", True)))
        if not exported.ok:
            return ExecutionResult(
                ok=False, code="GAME_3D_EXPORT_FAILED", message=exported.message,
                data={"project": str(project), "verification": exported.verification})
        executable = exported.executable
    return ExecutionResult.success(
        "Juego 3D verificado",
        project=str(project), capture=playtest.capture_path,
        godot_version=playtest.version, executable=executable,
        boot_ok=playtest.boot_ok, visual_ok=playtest.visual_ok,
    )


def build_final_igris(runtime: Path | None = None):
    kernel = build_production_igris(runtime)
    if shutil.which("godot") is not None:
        kernel.registry.register(
            CapabilitySpec(
                CAPABILITY,
                "Genera, renderiza y opcionalmente exporta un juego Godot 3D",
                ActionRisk.WRITE_WORKSPACE,
                True,
                timeout_seconds=180,
            ),
            _build_verified_3d,
        )
    return kernel
