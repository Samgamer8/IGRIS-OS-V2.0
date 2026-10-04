"""Reviewer Agent: Testing, quality assurance, and launch validation."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from igris_os.multi_agent.tbs.memory_hub import MemoryHub, MemoryEntry, MemoryType, Skill

logger = logging.getLogger(__name__)


class ReviewerTask(str, Enum):
    """Types of tasks the Reviewer agent can perform."""
    TESTING = "testing"
    BUG_REPORTING = "bug_reporting"
    LAUNCH_CHECKLIST = "launch_checklist"
    INCIDENT_ANALYSIS = "incident_analysis"


@dataclass(frozen=True, slots=True)
class ReviewerResult:
    """Result from a Reviewer agent task."""
    task_type: ReviewerTask
    success: bool
    findings: dict[str, Any]
    issues_found: list[str]
    approval_status: str
    confidence: float
    memories_stored: list[MemoryEntry] = field(default_factory=list)


class ReviewerAgent:
    """Reviewer agent: Tests code, finds problems, and validates launch readiness."""

    def __init__(self, memory_hub: MemoryHub) -> None:
        self.memory_hub = memory_hub
        self.agent_name = "reviewer"
        
        # Initialize launch checklist skill
        self._initialize_launch_checklist_skill()

    def perform_testing(
        self,
        feature_name: str,
        test_cases: list[dict[str, Any]],
        code_artifacts: dict[str, Any],
    ) -> ReviewerResult:
        """Perform testing on feature implementation."""
        logger.info(f"Reviewer testing feature: {feature_name}")
        
        findings = {
            "feature_name": feature_name,
            "test_cases_executed": len(test_cases),
            "test_results": self._execute_tests(test_cases, code_artifacts),
            "coverage": self._calculate_coverage(test_cases, code_artifacts),
        }
        
        issues_found = self._identify_test_issues(findings)
        approval_status = "approved" if not issues_found else "needs_fixes"
        
        # Store incidents if issues found
        memories_stored = []
        if issues_found:
            for issue in issues_found:
                incident_entry = MemoryEntry(
                    memory_type=MemoryType.INCIDENT,
                    category=f"testing:{feature_name}",
                    content={
                        "issue": issue,
                        "feature": feature_name,
                        "severity": self._assess_severity(issue),
                    },
                    source_agent=self.agent_name,
                    verified=True,
                )
                self.memory_hub.store_memory(incident_entry)
                memories_stored.append(incident_entry)
        
        return ReviewerResult(
            task_type=ReviewerTask.TESTING,
            success=True,
            findings=findings,
            issues_found=issues_found,
            approval_status=approval_status,
            confidence=0.9,
            memories_stored=memories_stored,
        )

    def report_bug(
        self,
        bug_description: str,
        reproduction_steps: list[str],
        severity: str,
        context: dict[str, Any],
    ) -> ReviewerResult:
        """Report a bug with full details."""
        logger.info(f"Reviewer reporting bug: {bug_description[:50]}...")
        
        findings = {
            "bug_description": bug_description,
            "reproduction_steps": reproduction_steps,
            "severity": severity,
            "context": context,
            "timestamp": self._get_timestamp(),
        }
        
        issues_found = [bug_description]
        
        # Store in incident memory
        memory_entry = MemoryEntry(
            memory_type=MemoryType.INCIDENT,
            category="bug_report",
            content=findings,
            source_agent=self.agent_name,
            verified=True,
        )
        self.memory_hub.store_memory(memory_entry)
        
        return ReviewerResult(
            task_type=ReviewerTask.BUG_REPORTING,
            success=True,
            findings=findings,
            issues_found=issues_found,
            approval_status="bug_reported",
            confidence=1.0,
            memories_stored=[memory_entry],
        )

    def run_launch_checklist(
        self,
        product_name: str,
        version: str,
        checklist_items: list[str],
    ) -> ReviewerResult:
        """Run launch checklist using the launch checklist skill."""
        logger.info(f"Reviewer running launch checklist for {product_name} v{version}")
        
        skill = self.memory_hub.get_skill("launch_checklist")
        if not skill:
            return self._fallback_launch_checklist(product_name, version, checklist_items)
        
        findings = {
            "product_name": product_name,
            "version": version,
            "checklist_items": checklist_items,
            "checklist_results": self._execute_checklist(checklist_items),
            "overall_status": self._calculate_overall_status(checklist_items),
        }
        
        issues_found = self._identify_checklist_failures(findings)
        approval_status = findings["overall_status"]
        
        # Store in incident memory if issues found
        memories_stored = []
        if issues_found:
            for issue in issues_found:
                incident_entry = MemoryEntry(
                    memory_type=MemoryType.INCIDENT,
                    category=f"launch_checklist:{product_name}",
                    content={
                        "issue": issue,
                        "product": product_name,
                        "version": version,
                    },
                    source_agent=self.agent_name,
                    verified=True,
                )
                self.memory_hub.store_memory(incident_entry)
                memories_stored.append(incident_entry)
        
        # Update skill usage
        self.memory_hub.update_skill_usage("launch_checklist", approval_status == "ready")
        
        return ReviewerResult(
            task_type=ReviewerTask.LAUNCH_CHECKLIST,
            success=True,
            findings=findings,
            issues_found=issues_found,
            approval_status=approval_status,
            confidence=0.95,
            memories_stored=memories_stored,
        )

    def analyze_incident(
        self,
        incident_id: str,
        incident_data: dict[str, Any],
    ) -> ReviewerResult:
        """Analyze a historical incident for patterns and learnings."""
        logger.info(f"Reviewer analyzing incident: {incident_id}")
        
        findings = {
            "incident_id": incident_id,
            "incident_data": incident_data,
            "root_cause": self._identify_root_cause(incident_data),
            "prevention_measures": self._suggest_prevention(incident_data),
            "similar_incidents": self._find_similar_incidents(incident_data),
        }
        
        issues_found = [findings["root_cause"]]
        
        # Store analysis in incident memory
        memory_entry = MemoryEntry(
            memory_type=MemoryType.INCIDENT,
            category=f"incident_analysis:{incident_id}",
            content=findings,
            source_agent=self.agent_name,
            verified=True,
        )
        self.memory_hub.store_memory(memory_entry)
        
        return ReviewerResult(
            task_type=ReviewerTask.INCIDENT_ANALYSIS,
            success=True,
            findings=findings,
            issues_found=issues_found,
            approval_status="analyzed",
            confidence=0.85,
            memories_stored=[memory_entry],
        )

    def get_relevant_context(self, objective: str) -> dict[str, Any]:
        """Retrieve relevant context from memory for review."""
        context = {
            "recent_incidents": self.memory_hub.retrieve_memories(
                MemoryType.INCIDENT, limit=10
            ),
            "codegraph": self.memory_hub.retrieve_memories(
                MemoryType.CODEGRAPH, limit=5
            ),
            "launch_checklist_skill": self.memory_hub.get_skill("launch_checklist"),
        }
        return context

    def _initialize_launch_checklist_skill(self) -> None:
        """Initialize the launch checklist skill in Memory Hub."""
        skill_entry = MemoryEntry(
            memory_type=MemoryType.SKILL,
            category="validation",
            content={
                "name": "launch_checklist",
                "description": "Run comprehensive launch checklist to validate product readiness",
                "parameters": {
                    "product_name": "name of the product",
                    "version": "version to launch",
                    "checklist_items": "list of checklist items to verify",
                },
                "success_rate": 0.95,
                "usage_count": 0,
            },
            source_agent=self.agent_name,
            verified=True,
        )
        self.memory_hub.store_memory(skill_entry)

    def _execute_tests(self, test_cases: list[dict], artifacts: dict) -> list[dict]:
        """Execute test cases and return results."""
        results = []
        for test in test_cases:
            results.append({
                "test_name": test.get("name", "unknown"),
                "status": "passed" if self._simulate_test_pass(test) else "failed",
                "duration_ms": test.get("duration", 100),
            })
        return results

    def _simulate_test_pass(self, test: dict) -> bool:
        """Simulate test execution (placeholder for actual test runner)."""
        return test.get("expected", "pass") == "pass"

    def _calculate_coverage(self, test_cases: list, artifacts: dict) -> float:
        """Calculate test coverage."""
        # Placeholder: actual implementation would analyze code coverage
        return min(1.0, len(test_cases) / 10.0)

    def _identify_test_issues(self, findings: dict) -> list[str]:
        """Identify issues from test results."""
        issues = []
        for result in findings["test_results"]:
            if result["status"] == "failed":
                issues.append(f"Test failed: {result['test_name']}")
        if findings["coverage"] < 0.8:
            issues.append(f"Low test coverage: {findings['coverage']*100:.1f}%")
        return issues

    def _assess_severity(self, issue: str) -> str:
        """Assess severity of an issue."""
        if "critical" in issue.lower() or "crash" in issue.lower():
            return "critical"
        elif "error" in issue.lower():
            return "high"
        elif "warning" in issue.lower():
            return "medium"
        return "low"

    def _execute_checklist(self, items: list[str]) -> list[dict]:
        """Execute checklist items and return results."""
        results = []
        for item in items:
            results.append({
                "item": item,
                "status": "passed" if self._simulate_check_pass(item) else "failed",
                "notes": f"Verification for {item}",
            })
        return results

    def _simulate_check_pass(self, item: str) -> bool:
        """Simulate checklist item verification (placeholder)."""
        return "critical" not in item.lower()

    def _calculate_overall_status(self, checklist_items: list) -> str:
        """Calculate overall launch status."""
        # Placeholder: actual implementation would evaluate all items
        return "ready" if len(checklist_items) > 5 else "needs_review"

    def _identify_checklist_failures(self, findings: dict) -> list[str]:
        """Identify failed checklist items."""
        failures = []
        for result in findings["checklist_results"]:
            if result["status"] == "failed":
                failures.append(f"Checklist item failed: {result['item']}")
        return failures

    def _identify_root_cause(self, incident_data: dict) -> str:
        """Identify root cause of incident."""
        return incident_data.get("root_cause", "Root cause analysis pending")

    def _suggest_prevention(self, incident_data: dict) -> list[str]:
        """Suggest prevention measures based on incident."""
        return [
            "Add additional monitoring",
            "Implement automated testing",
            "Improve error handling",
        ]

    def _find_similar_incidents(self, incident_data: dict) -> list[str]:
        """Find similar historical incidents."""
        similar = self.memory_hub.retrieve_memories(
            MemoryType.INCIDENT, source_agent="reviewer", limit=5
        )
        return [f"Similar incident: {mem.content.get('bug_description', 'unknown')}" for mem in similar]

    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    def _fallback_launch_checklist(
        self, product_name: str, version: str, checklist_items: list[str]
    ) -> ReviewerResult:
        """Fallback launch checklist when skill is not available."""
        return ReviewerResult(
            task_type=ReviewerTask.LAUNCH_CHECKLIST,
            success=True,
            findings={
                "product_name": product_name,
                "version": version,
                "checklist_items": checklist_items,
                "note": "Fallback checklist - launch checklist skill not found",
            },
            issues_found=["Initialize launch checklist skill for better results"],
            approval_status="needs_review",
            confidence=0.5,
            memories_stored=[],
        )
