"""Builder Agent: Code implementation, product development, and feature delivery."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from igris_os.multi_agent.tbs.memory_hub import MemoryHub, MemoryEntry, MemoryType, Skill

logger = logging.getLogger(__name__)


class BuilderTask(str, Enum):
    """Types of tasks the Builder agent can perform."""
    CODE_IMPLEMENTATION = "code_implementation"
    FEATURE_DELIVERY = "feature_delivery"
    PRODUCT_WIKI_UPDATE = "product_wiki_update"
    CODEGRAPH_UPDATE = "codegraph_update"


@dataclass(frozen=True, slots=True)
class BuilderResult:
    """Result from a Builder agent task."""
    task_type: BuilderTask
    success: bool
    artifacts: dict[str, Any]
    code_changes: list[str]
    documentation: str
    confidence: float
    memories_stored: list[MemoryEntry] = field(default_factory=list)


class BuilderAgent:
    """Builder/Constructor agent: Writes code, creates products, and delivers features."""

    def __init__(self, memory_hub: MemoryHub) -> None:
        self.memory_hub = memory_hub
        self.agent_name = "builder"
        
        # Initialize feature delivery skill
        self._initialize_feature_delivery_skill()

    def implement_code(
        self,
        feature_spec: dict[str, Any],
        codebase_context: dict[str, Any],
        implementation_plan: str,
    ) -> BuilderResult:
        """Implement code based on feature specification and plan."""
        logger.info(f"Builder implementing feature: {feature_spec.get('name', 'unknown')}")
        
        artifacts = {
            "feature_name": feature_spec.get("name", ""),
            "implementation": self._generate_implementation(feature_spec, implementation_plan),
            "files_created": self._identify_files_to_create(feature_spec),
            "dependencies": self._identify_dependencies(feature_spec),
        }
        
        code_changes = [
            f"Created {artifacts['files_created']}",
            f"Added dependencies: {artifacts['dependencies']}",
        ]
        
        documentation = self._generate_documentation(feature_spec, artifacts)
        
        # Update CodeGraph
        self._update_codegraph(artifacts)
        
        # Store in Product Wiki
        memory_entry = MemoryEntry(
            memory_type=MemoryType.WIKI,
            category=f"product:{feature_spec.get('name', 'unknown')}",
            content={
                "feature_spec": feature_spec,
                "artifacts": artifacts,
                "documentation": documentation,
            },
            source_agent=self.agent_name,
            verified=True,
        )
        self.memory_hub.store_memory(memory_entry)
        
        return BuilderResult(
            task_type=BuilderTask.CODE_IMPLEMENTATION,
            success=True,
            artifacts=artifacts,
            code_changes=code_changes,
            documentation=documentation,
            confidence=0.9,
            memories_stored=[memory_entry],
        )

    def deliver_feature(
        self,
        feature_name: str,
        feature_code: str,
        tests: list[str],
        deployment_config: dict[str, Any],
    ) -> BuilderResult:
        """Deliver a complete feature with tests and deployment config."""
        logger.info(f"Builder delivering feature: {feature_name}")
        
        skill = self.memory_hub.get_skill("feature_delivery")
        if not skill:
            return self._fallback_feature_delivery(feature_name, feature_code)
        
        artifacts = {
            "feature_name": feature_name,
            "feature_code": feature_code,
            "tests": tests,
            "deployment_config": deployment_config,
            "delivery_status": "ready",
        }
        
        code_changes = [
            f"Feature {feature_name} implemented",
            f"Tests added: {len(tests)} test cases",
            "Deployment configuration prepared",
        ]
        
        documentation = self._generate_feature_documentation(feature_name, artifacts)
        
        # Update skill usage
        self.memory_hub.update_skill_usage("feature_delivery", True)
        
        # Store in Product Wiki
        memory_entry = MemoryEntry(
            memory_type=MemoryType.WIKI,
            category=f"feature:{feature_name}",
            content=artifacts,
            source_agent=self.agent_name,
            verified=True,
        )
        self.memory_hub.store_memory(memory_entry)
        
        return BuilderResult(
            task_type=BuilderTask.FEATURE_DELIVERY,
            success=True,
            artifacts=artifacts,
            code_changes=code_changes,
            documentation=documentation,
            confidence=0.95,
            memories_stored=[memory_entry],
        )

    def update_product_wiki(
        self,
        product_name: str,
        updates: dict[str, Any],
        section: str = "general",
    ) -> BuilderResult:
        """Update the Product Wiki with new information."""
        logger.info(f"Builder updating product wiki for {product_name}")
        
        artifacts = {
            "product_name": product_name,
            "section": section,
            "updates": updates,
            "timestamp": self._get_timestamp(),
        }
        
        code_changes = [f"Updated {section} section of {product_name} wiki"]
        
        documentation = f"Wiki update for {product_name} - {section}"
        
        # Store in Wiki
        memory_entry = MemoryEntry(
            memory_type=MemoryType.WIKI,
            category=f"product_wiki:{product_name}",
            content=artifacts,
            source_agent=self.agent_name,
            verified=True,
        )
        self.memory_hub.store_memory(memory_entry)
        
        return BuilderResult(
            task_type=BuilderTask.PRODUCT_WIKI_UPDATE,
            success=True,
            artifacts=artifacts,
            code_changes=code_changes,
            documentation=documentation,
            confidence=1.0,
            memories_stored=[memory_entry],
        )

    def update_codegraph(
        self,
        codebase_path: Path,
        structure_updates: dict[str, Any],
    ) -> BuilderResult:
        """Update the CodeGraph with current codebase structure."""
        logger.info(f"Builder updating CodeGraph for {codebase_path}")
        
        artifacts = {
            "codebase_path": str(codebase_path),
            "structure_updates": structure_updates,
            "timestamp": self._get_timestamp(),
        }
        
        code_changes = [f"Updated CodeGraph for {codebase_path}"]
        
        documentation = f"CodeGraph update for {codebase_path}"
        
        # Store in CodeGraph
        memory_entry = MemoryEntry(
            memory_type=MemoryType.CODEGRAPH,
            category="code_structure",
            content=structure_updates,
            source_agent=self.agent_name,
            verified=True,
        )
        self.memory_hub.store_memory(memory_entry)
        
        return BuilderResult(
            task_type=BuilderTask.CODEGRAPH_UPDATE,
            success=True,
            artifacts=artifacts,
            code_changes=code_changes,
            documentation=documentation,
            confidence=1.0,
            memories_stored=[memory_entry],
        )

    def get_relevant_context(self, objective: str) -> dict[str, Any]:
        """Retrieve relevant context from memory for building."""
        context = {
            "product_wiki": self.memory_hub.retrieve_memories(
                MemoryType.WIKI, category=lambda x: x.startswith("product:"), limit=10
            ),
            "codegraph": self.memory_hub.retrieve_memories(
                MemoryType.CODEGRAPH, limit=5
            ),
            "feature_delivery_skill": self.memory_hub.get_skill("feature_delivery"),
        }
        return context

    def _initialize_feature_delivery_skill(self) -> None:
        """Initialize the feature delivery skill in Memory Hub."""
        skill_entry = MemoryEntry(
            memory_type=MemoryType.SKILL,
            category="delivery",
            content={
                "name": "feature_delivery",
                "description": "Deliver complete features with code, tests, and deployment configuration",
                "parameters": {
                    "feature_name": "name of the feature to deliver",
                    "feature_code": "implementation code",
                    "tests": "list of test cases",
                    "deployment_config": "deployment configuration",
                },
                "success_rate": 0.95,
                "usage_count": 0,
            },
            source_agent=self.agent_name,
            verified=True,
        )
        self.memory_hub.store_memory(skill_entry)

    def _generate_implementation(self, spec: dict, plan: str) -> str:
        """Generate implementation code from spec and plan."""
        return f"# Implementation for {spec.get('name', 'unknown')}\n# Plan: {plan}\n# Code would be generated here based on spec"

    def _identify_files_to_create(self, spec: dict) -> list[str]:
        """Identify files that need to be created for the feature."""
        feature_name = spec.get("name", "unknown")
        return [
            f"src/{feature_name}.py",
            f"tests/test_{feature_name}.py",
            f"docs/{feature_name}.md",
        ]

    def _identify_dependencies(self, spec: dict) -> list[str]:
        """Identify dependencies for the feature."""
        return spec.get("dependencies", ["standard_library"])

    def _generate_documentation(self, spec: dict, artifacts: dict) -> str:
        """Generate documentation for the implementation."""
        return f"""
# {spec.get('name', 'Unknown Feature')}

## Description
{spec.get('description', 'No description provided')}

## Implementation Details
- Files: {artifacts['files_created']}
- Dependencies: {artifacts['dependencies']}

## Usage
[Usage instructions would be generated here]
"""

    def _update_codegraph(self, artifacts: dict) -> None:
        """Update the CodeGraph with new code structure."""
        codegraph_entry = MemoryEntry(
            memory_type=MemoryType.CODEGRAPH,
            category="code_structure",
            content={
                "files_added": artifacts["files_created"],
                "dependencies_added": artifacts["dependencies"],
            },
            source_agent=self.agent_name,
            verified=True,
        )
        self.memory_hub.store_memory(codegraph_entry)

    def _generate_feature_documentation(self, feature_name: str, artifacts: dict) -> str:
        """Generate documentation for a delivered feature."""
        return f"""
# {feature_name}

## Overview
Feature delivered with complete implementation and tests.

## Components
- Feature Code: {len(artifacts['feature_code'])} characters
- Tests: {len(artifacts['tests'])} test cases
- Deployment: Configuration prepared

## Status
{artifacts['delivery_status']}
"""

    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    def _fallback_feature_delivery(self, feature_name: str, feature_code: str) -> BuilderResult:
        """Fallback feature delivery when skill is not available."""
        return BuilderResult(
            task_type=BuilderTask.FEATURE_DELIVERY,
            success=True,
            artifacts={
                "feature_name": feature_name,
                "feature_code": feature_code,
                "note": "Fallback delivery - feature delivery skill not found",
            },
            code_changes=[f"Feature {feature_name} implemented (fallback mode)"],
            documentation=f"Documentation for {feature_name} (fallback mode)",
            confidence=0.7,
            memories_stored=[],
        )
