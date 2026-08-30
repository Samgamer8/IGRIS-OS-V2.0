"""Multi-agent coordination module."""
from igris_os.multi_agent.coordinator import MultiAgentCoordinator, AgentRole, AgentState, AgentConfig
from igris_os.multi_agent.hierarchy import (
    Candidate,
    ClarificationGate,
    Evidence,
    HierarchicalOrchestrator,
    IgrisDecision,
    IntentContract,
    Proposal,
    Specialist,
    WorkOrder,
)
from igris_os.multi_agent.factory import (
    Department,
    DepartmentResult,
    FactoryOrchestrator,
    FactoryResult,
)

__all__ = [
    "MultiAgentCoordinator",
    "AgentRole",
    "AgentState",
    "AgentConfig",
    "Candidate",
    "ClarificationGate",
    "Evidence",
    "Department",
    "DepartmentResult",
    "FactoryOrchestrator",
    "FactoryResult",
    "HierarchicalOrchestrator",
    "IgrisDecision",
    "IntentContract",
    "Proposal",
    "Specialist",
    "WorkOrder",
]
