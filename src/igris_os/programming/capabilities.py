from __future__ import annotations

from typing import Any, Callable

from igris_os.domain.models import ActionRisk, CapabilityHandler, CapabilitySpec, ExecutionResult
from igris_os.programming.coordinator import AutonomousProgrammingCoordinator
from igris_os.programming.multilang import Language, MultiLanguageCoordinator
from igris_os.storage.workspace import MissionWorkspace


def register_core_capabilities(registry, *, client, workspace: MissionWorkspace,
                                default_model: str = "qwen2.5-coder:7b") -> None:
    def capability(name: str, risk: ActionRisk, requires_confirmation: bool = False,
                   timeout: int = 300, tags: tuple[str, ...] = ()):
        def decorator(handler: CapabilityHandler):
            spec = CapabilitySpec(
                name=name, description=name, risk=risk,
                requires_confirmation=requires_confirmation,
                timeout_seconds=timeout, tags=tags,
            )
            registry.register(spec, handler)
            return handler
        return decorator

    @capability("programming.autonomous.develop", ActionRisk.EXTERNAL, True, 600, ("programming",))
    def programming_autonomous_develop(request: dict[str, Any]) -> ExecutionResult:
        objective = str(request.get("objective", ""))
        language = str(request.get("language", "python"))
        root = workspace.create(request.get("mission_id", "default"))
        coordinator = AutonomousProgrammingCoordinator(
            client, root, default_model=default_model)
        result = coordinator.execute(
            objective, confirmed=True,
            on_progress=request.get("on_progress"),
        )
        if result.ok:
            return ExecutionResult.success(
                result.message,
                proposal=result.proposal.source if result.proposal else "",
                review_score=result.review.score if result.review else 0.0,
            )
        return ExecutionResult.failure(result.message, "AUTONOMOUS_FAILED")

    @capability("programming.multilang.develop", ActionRisk.EXTERNAL, True, 600, ("programming",))
    def programming_multilang_develop(request: dict[str, Any]) -> ExecutionResult:
        objective = str(request.get("objective", ""))
        language = str(request.get("language", "python"))
        root = workspace.create(request.get("mission_id", "default"))
        coordinator = MultiLanguageCoordinator(
            client, root, default_model=default_model)
        result = coordinator.develop(
            objective, language=language, confirmed=True,
            on_progress=request.get("on_progress"),
        )
        if result.ok:
            return ExecutionResult.success(
                result.message,
                language=result.language,
                artifacts=result.artifacts,
            )
        return ExecutionResult.failure(result.message, "MULTILANG_FAILED")
