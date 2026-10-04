"""Tiny but Serious Inc. Multi-Agent Architecture."""

from igris_os.multi_agent.tbs.memory_hub import MemoryHub
from igris_os.multi_agent.tbs.scout_agent import ScoutAgent
from igris_os.multi_agent.tbs.builder_agent import BuilderAgent
from igris_os.multi_agent.tbs.reviewer_agent import ReviewerAgent
from igris_os.multi_agent.tbs.orchestrator import TinyButSeriousOrchestrator

__all__ = [
    "MemoryHub",
    "ScoutAgent",
    "BuilderAgent",
    "ReviewerAgent",
    "TinyButSeriousOrchestrator",
]
