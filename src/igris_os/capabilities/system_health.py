import platform
import sys
from collections.abc import Mapping
from typing import Any

from igris_os.application import CapabilityRegistry
from igris_os.domain import ActionRisk, CapabilitySpec, ExecutionResult


def health(_: Mapping[str, Any]) -> ExecutionResult:
    return ExecutionResult.success(
        "Nucleo operativo",
        python=sys.version.split()[0],
        platform=platform.platform(),
    )


def register_system_health(registry: CapabilityRegistry) -> None:
    registry.register(
        CapabilitySpec("system.health", "Diagnostico local de solo lectura", ActionRisk.READ_ONLY),
        health,
    )

