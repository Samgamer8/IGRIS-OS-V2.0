from __future__ import annotations

import shutil
from pathlib import Path

from igris_os.application import IgrisKernel
from igris_os.bootstrap import build_igris
from igris_os.domain import ActionRisk, CapabilitySpec, ExecutionResult
from igris_os.programming import MultiLanguageVerifier


# IGRIS OS V5: autonomous programming is a production capability.
# Runtime safety remains governed by capability risk, permissions,
# confirmations, workspace containment and verification gates.
PRODUCTION_BLOCKED_CAPABILITIES = frozenset()


def _production_languages(_payload):
    detections = MultiLanguageVerifier(Path.cwd()).detect_project(Path.cwd())
    detected = {item.language.value: item for item in detections}
    profiles = MultiLanguageVerifier.PROFILES.values()
    languages = []
    executable_by_language = {
        "python": "python", "rust": "cargo", "cpp": "cmake",
        "java": "mvn", "gdscript": "godot", "typescript": "npx",
        "javascript": "node",
    }
    for profile in profiles:
        name = profile.language.value
        executable = shutil.which(executable_by_language[name])
        languages.append({
            "name": name,
            "extensions": profile.extensions,
            "available": executable is not None,
            "executable": executable or "",
            "detected_in_project": name in detected,
            "requires_network": profile.requires_network,
        })
    return ExecutionResult.success(
        "Toolchains locales inspeccionadas", languages=languages)


def build_production_igris(runtime: Path | None = None) -> IgrisKernel:
    """Construye el kernel de producción conservando autonomía verificada."""

    kernel = build_igris(runtime)
    disabled = set(PRODUCTION_BLOCKED_CAPABILITIES)

    if shutil.which("godot") is None:
        disabled.update({"games.godot.playtest", "games.godot.export"})

    if shutil.which("git") is None:
        disabled.update(
            name for name in kernel.registry._items
            if name.startswith("git.")
        )

    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        disabled.update({
            "multimedia.extract_audio",
            "multimedia.thumbnail",
            "multimedia.transcode",
            "multimedia.pipeline",
        })

    for name in disabled:
        kernel.registry._items.pop(name, None)

    kernel.registry._items.pop("programming.languages", None)
    kernel.registry.register(
        CapabilitySpec(
            "programming.languages",
            "Disponibilidad real de toolchains locales",
            ActionRisk.READ_ONLY,
        ),
        _production_languages,
    )

    return kernel
