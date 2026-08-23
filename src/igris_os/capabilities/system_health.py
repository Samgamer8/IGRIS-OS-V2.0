import platform
import sys
from collections.abc import Mapping
from typing import Any

from igris_os.application import CapabilityRegistry
from igris_os.domain import ActionRisk, CapabilitySpec, ExecutionResult


def health(_: Mapping[str, Any]) -> ExecutionResult:
    try:
        import psutil
        cpu_percent = round(psutil.cpu_percent(interval=None), 1)
        memory_percent = round(psutil.virtual_memory().percent, 1)
        available_memory = int(psutil.virtual_memory().available)
    except ImportError:
        cpu_percent = memory_percent = None
        available_memory = None
    return ExecutionResult.success(
        "Nucleo operativo",
        python=sys.version.split()[0],
        platform=platform.platform(),
        cpu_percent=cpu_percent,
        memory_percent=memory_percent,
        available_memory=available_memory,
    )


def register_system_health(registry: CapabilityRegistry) -> None:
    registry.register(
        CapabilitySpec("system.health", "Diagnostico local de solo lectura", ActionRisk.READ_ONLY),
        health,
    )
