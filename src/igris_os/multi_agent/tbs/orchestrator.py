"""Orchestrator: Coordinates Tiny but Serious Inc. agents with Memory Hub handoffs."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from igris_os.multi_agent.tbs.memory_hub import (
    MemoryHub,
    MemoryEntry,
    MemoryType,
    HandoffContext,
)
from igris_os.multi_agent.tbs.scout_agent import ScoutAgent, ScoutResult
from igris_os.multi_agent.tbs.builder_agent import BuilderAgent, BuilderResult
from igris_os.multi_agent.tbs.reviewer_agent import ReviewerAgent, ReviewerResult

logger = logging.getLogger(__name__)


class AgentType(str, Enum):
    """Types of agents in the Tiny but Serious Inc. system."""
    SCOUT = "scout"
    BUILDER = "builder"
    REVIEWER = "reviewer"
    USER = "user"


class WorkflowStage(str, Enum):
    """Stages in the Tiny but Serious Inc. workflow."""
    RESEARCH = "research"
    DEVELOPMENT = "development"
    TESTING = "testing"
    LAUNCH = "launch"
    COMPLETE = "complete"


@dataclass(frozen=True, slots=True)
class WorkflowState:
    """Current state of the workflow."""
    stage: WorkflowStage
    current_agent: AgentType
    objective: str
    context: dict[str, Any]
    iteration: int
    max_iterations: int


@dataclass(frozen=True, slots=True)
class WorkflowResult:
    """Result of the complete workflow."""
    success: bool
    final_stage: WorkflowStage
    objective: str
    scout_results: list[ScoutResult] = field(default_factory=list)
    builder_results: list[BuilderResult] = field(default_factory=list)
    reviewer_results: list[ReviewerResult] = field(default_factory=list)
    handoffs_performed: int = 0
    total_duration_seconds: float = 0.0
    error_message: str = ""


class TinyButSeriousOrchestrator:
    """Orchestrates Tiny but Serious Inc. agents with Memory Hub coordination."""

    def __init__(self, storage_path: Path) -> None:
        self.storage_path = storage_path.resolve()
        self.memory_hub = MemoryHub(storage_path)
        
        # Initialize agents
        self.scout = ScoutAgent(self.memory_hub)
        self.builder = BuilderAgent(self.memory_hub)
        self.reviewer = ReviewerAgent(self.memory_hub)
        
        logger.info(f"TinyButSeriousOrchestrator initialized with storage at {storage_path}")

    def execute_workflow(
        self,
        objective: str,
        max_iterations: int = 3,
        start_stage: WorkflowStage = WorkflowStage.RESEARCH,
    ) -> WorkflowResult:
        """Execute the complete Tiny but Serious Inc. workflow."""
        import time
        start_time = time.monotonic()
        
        logger.info(f"Starting workflow for objective: {objective[:50]}...")
        
        state = WorkflowState(
            stage=start_stage,
            current_agent=AgentType.USER,
            objective=objective,
            context={},
            iteration=0,
            max_iterations=max_iterations,
        )
        
        scout_results: list[ScoutResult] = []
        builder_results: list[BuilderResult] = []
        reviewer_results: list[ReviewerResult] = []
        handoffs_performed = 0
        
        try:
            # Stage 1: Research (Scout)
            if state.stage in (WorkflowStage.RESEARCH, WorkflowStage.DEVELOPMENT):
                state, scout_results = self._execute_research_stage(state)
                handoffs_performed += 1
            
            # Stage 2: Development (Builder)
            if state.stage in (WorkflowStage.DEVELOPMENT, WorkflowStage.TESTING):
                state, builder_results = self._execute_development_stage(state)
                handoffs_performed += 1
            
            # Stage 3: Testing (Reviewer)
            if state.stage in (WorkflowStage.TESTING, WorkflowStage.LAUNCH):
                state, reviewer_results = self._execute_testing_stage(state)
                handoffs_performed += 1
            
            # Stage 4: Launch (Reviewer with checklist) - always run if testing was run
            if state.stage == WorkflowStage.LAUNCH:
                state, launch_results = self._execute_launch_stage(state)
                reviewer_results.extend(launch_results)
                handoffs_performed += 1
            
            final_stage = WorkflowStage.COMPLETE
            success = self._evaluate_success(scout_results, builder_results, reviewer_results)
            
        except Exception as e:
            logger.error(f"Workflow failed: {e}")
            return WorkflowResult(
                success=False,
                final_stage=state.stage,
                objective=objective,
                scout_results=scout_results,
                builder_results=builder_results,
                reviewer_results=reviewer_results,
                handoffs_performed=handoffs_performed,
                total_duration_seconds=time.monotonic() - start_time,
                error_message=str(e),
            )
        
        return WorkflowResult(
            success=success,
            final_stage=final_stage,
            objective=objective,
            scout_results=scout_results,
            builder_results=builder_results,
            reviewer_results=reviewer_results,
            handoffs_performed=handoffs_performed,
            total_duration_seconds=time.monotonic() - start_time,
        )

    def _execute_research_stage(
        self, state: WorkflowState
    ) -> tuple[WorkflowState, list[ScoutResult]]:
        """Execute the research stage with Scout agent."""
        logger.info("Executing RESEARCH stage with Scout agent")
        
        # Get relevant context from Memory Hub
        context = self.scout.get_relevant_context(state.objective)
        
        # Perform research tasks
        results = []
        
        # Market research
        market_result = self.scout.perform_market_research(
            market_segment=self._extract_market_segment(state.objective),
            research_queries=self._generate_research_queries(state.objective),
        )
        results.append(market_result)
        
        # Competitive analysis
        competitive_result = self.scout.perform_competitive_analysis(
            competitors=self._identify_competitors(state.objective),
            analysis_dimensions=["features", "pricing", "ux", "performance"],
        )
        results.append(competitive_result)
        
        # Opportunity discovery
        opportunity_result = self.scout.discover_opportunities(
            domain=self._extract_domain(state.objective),
        )
        results.append(opportunity_result)
        
        # Handoff to Builder
        self._perform_handoff(
            from_agent=AgentType.SCOUT,
            to_agent=AgentType.BUILDER,
            objective=state.objective,
            current_state={"stage": "development", "research_complete": True},
            relevant_memories=[],  # Don't pass memories to avoid serialization issues
        )
        
        new_state = WorkflowState(
            stage=WorkflowStage.DEVELOPMENT,
            current_agent=AgentType.BUILDER,
            objective=state.objective,
            context={**state.context, "research_complete": True, "scout_tasks_completed": len(results)},
            iteration=state.iteration + 1,
            max_iterations=state.max_iterations,
        )
        
        return new_state, results

    def _execute_development_stage(
        self, state: WorkflowState
    ) -> tuple[WorkflowState, list[BuilderResult]]:
        """Execute the development stage with Builder agent."""
        logger.info("Executing DEVELOPMENT stage with Builder agent")
        
        # Get relevant context from Memory Hub
        context = self.builder.get_relevant_context(state.objective)
        
        # Perform development tasks
        results = []
        
        # Code implementation
        feature_spec = self._create_feature_spec(state.objective, state.context)
        code_result = self.builder.implement_code(
            feature_spec=feature_spec,
            codebase_context=context.get("codegraph", [{}])[0].content if context.get("codegraph") else {},
            implementation_plan=self._create_implementation_plan(feature_spec),
        )
        results.append(code_result)
        
        # Feature delivery
        if code_result.success:
            delivery_result = self.builder.deliver_feature(
                feature_name=feature_spec.get("name", "unknown"),
                feature_code=code_result.artifacts.get("implementation", ""),
                tests=self._generate_test_cases(feature_spec),
                deployment_config=self._create_deployment_config(),
            )
            results.append(delivery_result)
        
        # Update product wiki
        wiki_result = self.builder.update_product_wiki(
            product_name=feature_spec.get("name", "unknown"),
            updates={"status": "implemented", "version": "1.0.0"},
        )
        results.append(wiki_result)
        
        # Handoff to Reviewer
        self._perform_handoff(
            from_agent=AgentType.BUILDER,
            to_agent=AgentType.REVIEWER,
            objective=state.objective,
            current_state={"stage": "testing", "development_complete": True},
            relevant_memories=[],  # Don't pass memories to avoid serialization issues
        )
        
        new_state = WorkflowState(
            stage=WorkflowStage.TESTING,
            current_agent=AgentType.REVIEWER,
            objective=state.objective,
            context={**state.context, "development_results": results},
            iteration=state.iteration + 1,
            max_iterations=state.max_iterations,
        )
        
        return new_state, results

    def _execute_testing_stage(
        self, state: WorkflowState
    ) -> tuple[WorkflowState, list[ReviewerResult]]:
        """Execute the testing stage with Reviewer agent."""
        logger.info("Executing TESTING stage with Reviewer agent")
        
        # Get relevant context from Memory Hub
        context = self.reviewer.get_relevant_context(state.objective)
        
        # Perform testing tasks
        results = []
        
        # Get feature from development results
        dev_results = state.context.get("development_results", [])
        if dev_results:
            feature_name = dev_results[0].artifacts.get("feature_name", "unknown")
            
            # Testing
            test_result = self.reviewer.perform_testing(
                feature_name=feature_name,
                test_cases=self._generate_test_cases_for_testing(feature_name),
                code_artifacts=dev_results[0].artifacts,
            )
            results.append(test_result)
        
        # Always proceed to launch checklist after testing
        state = WorkflowState(
            stage=WorkflowStage.LAUNCH,
            current_agent=AgentType.REVIEWER,
            objective=state.objective,
            context=state.context,
            iteration=state.iteration,
            max_iterations=state.max_iterations,
        )
        
        return state, results

    def _execute_launch_stage(
        self, state: WorkflowState
    ) -> tuple[WorkflowState, list[ReviewerResult]]:
        """Execute the launch stage with Reviewer agent."""
        logger.info("Executing LAUNCH stage with Reviewer agent")
        
        results = []
        
        # Get feature name
        dev_results = state.context.get("development_results", [])
        feature_name = dev_results[0].artifacts.get("feature_name", "unknown") if dev_results else "unknown"
        
        # Run launch checklist
        checklist_result = self.reviewer.run_launch_checklist(
            product_name=feature_name,
            version="1.0.0",
            checklist_items=self._generate_launch_checklist_items(),
        )
        results.append(checklist_result)
        
        # Handoff back to User (complete)
        self._perform_handoff(
            from_agent=AgentType.REVIEWER,
            to_agent=AgentType.USER,
            objective=state.objective,
            current_state={"stage": "complete", "launch_status": checklist_result.approval_status},
            relevant_memories=[],  # Don't pass memories to avoid serialization issues
        )
        
        new_state = WorkflowState(
            stage=WorkflowStage.COMPLETE,
            current_agent=AgentType.USER,
            objective=state.objective,
            context=state.context,
            iteration=state.iteration + 1,
            max_iterations=state.max_iterations,
        )
        
        return new_state, results

    def _perform_handoff(
        self,
        from_agent: AgentType,
        to_agent: AgentType,
        objective: str,
        current_state: dict[str, Any],
        relevant_memories: list[MemoryEntry],
    ) -> None:
        """Perform agent handoff through Memory Hub."""
        # Convert MemoryEntry objects to serializable dicts
        serializable_memories = [
            {
                "memory_type": m.memory_type.value,
                "category": m.category,
                "content": m.content,
                "source_agent": m.source_agent,
                "created_at": m.created_at,
            }
            for m in relevant_memories
        ]
        
        # Convert current_state to serializable format
        serializable_state = {}
        for key, value in current_state.items():
            if isinstance(value, list):
                # Convert result objects to dicts
                serializable_state[key] = [
                    {
                        "task_type": str(getattr(item, "task_type", "unknown")),
                        "success": getattr(item, "success", False),
                    }
                    for item in value
                ]
            else:
                serializable_state[key] = str(value)
        
        handoff_context = HandoffContext(
            from_agent=from_agent.value,
            to_agent=to_agent.value,
            objective=objective,
            current_state=serializable_state,  # Use serializable version
            relevant_memories=serializable_memories,  # Use serializable version
        )
        self.memory_hub.record_handoff(handoff_context)
        logger.info(f"Handoff: {from_agent.value} -> {to_agent.value}")

    def _gather_relevant_memories(self, results: list) -> list[MemoryEntry]:
        """Gather relevant memories from agent results."""
        memories = []
        for result in results:
            if hasattr(result, "memories_stored"):
                memories.extend(result.memories_stored)
        return memories[:5]  # Limit to 5 memories to avoid serialization issues

    def _extract_market_segment(self, objective: str) -> str:
        """Extract market segment from objective."""
        return "software_development"  # Placeholder

    def _generate_research_queries(self, objective: str) -> list[str]:
        """Generate research queries from objective."""
        return [
            f"market analysis for {objective}",
            "user requirements",
            "technical feasibility",
        ]

    def _identify_competitors(self, objective: str) -> list[str]:
        """Identify competitors for the objective."""
        return ["Competitor A", "Competitor B", "Competitor C"]

    def _extract_domain(self, objective: str) -> str:
        """Extract domain from objective."""
        return "software"

    def _create_feature_spec(self, objective: str, context: dict) -> dict[str, Any]:
        """Create feature specification from objective and context."""
        return {
            "name": objective.split()[0] if objective else "feature",
            "description": objective,
            "dependencies": ["standard_library"],
            "requirements": context.get("research_results", []),
        }

    def _create_implementation_plan(self, spec: dict) -> str:
        """Create implementation plan from feature spec."""
        return f"Implementation plan for {spec.get('name', 'unknown')}"

    def _generate_test_cases(self, spec: dict) -> list[str]:
        """Generate test cases for feature."""
        return [
            f"Test case 1 for {spec.get('name', 'unknown')}",
            f"Test case 2 for {spec.get('name', 'unknown')}",
        ]

    def _create_deployment_config(self) -> dict[str, Any]:
        """Create deployment configuration."""
        return {
            "environment": "production",
            "strategy": "rolling",
            "health_checks": True,
        }

    def _generate_test_cases_for_testing(self, feature_name: str) -> list[dict[str, Any]]:
        """Generate test cases for testing stage."""
        return [
            {"name": f"test_{feature_name}_basic", "expected": "pass"},
            {"name": f"test_{feature_name}_edge", "expected": "pass"},
        ]

    def _generate_launch_checklist_items(self) -> list[str]:
        """Generate launch checklist items."""
        return [
            "All tests passing",
            "Documentation complete",
            "Security review passed",
            "Performance benchmarks met",
            "Deployment pipeline verified",
            "Monitoring configured",
            "Rollback plan ready",
        ]

    def _evaluate_success(
        self,
        scout_results: list[ScoutResult],
        builder_results: list[BuilderResult],
        reviewer_results: list[ReviewerResult],
    ) -> bool:
        """Evaluate overall workflow success."""
        # All stages should have at least one result
        if not scout_results or not builder_results or not reviewer_results:
            return False
        
        # Check if all results are successful
        all_scout_success = all(r.success for r in scout_results)
        all_builder_success = all(r.success for r in builder_results)
        all_reviewer_success = all(r.success for r in reviewer_results)
        
        return all_scout_success and all_builder_success and all_reviewer_success

    def get_workflow_summary(self) -> dict[str, Any]:
        """Get summary of workflow activity."""
        return {
            "handoffs": self.memory_hub.get_recent_handoffs(limit=20),
            "skills": {
                "competitive_analysis": self.memory_hub.get_skill("competitive_analysis"),
                "feature_delivery": self.memory_hub.get_skill("feature_delivery"),
                "launch_checklist": self.memory_hub.get_skill("launch_checklist"),
            },
            "memory_stats": {
                "chat_memory_count": len(self.memory_hub.retrieve_memories(MemoryType.CHAT_MEMORY, limit=1000)),
                "wiki_count": len(self.memory_hub.retrieve_memories(MemoryType.WIKI, limit=1000)),
                "codegraph_count": len(self.memory_hub.retrieve_memories(MemoryType.CODEGRAPH, limit=1000)),
                "incidents_count": len(self.memory_hub.retrieve_memories(MemoryType.INCIDENT, limit=1000)),
            },
        }
