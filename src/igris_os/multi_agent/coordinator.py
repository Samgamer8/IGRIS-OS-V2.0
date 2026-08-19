"""Multi-agent coordination system using LangGraph."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, TypedDict, Annotated

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from igris_os.ai.multi_provider import MultiProviderRouter, GenerationRequest, ProviderRank

logger = logging.getLogger(__name__)


class AgentRole(str, Enum):
    """Specialized agent roles."""
    ARCHITECT = "architect"
    PROGRAMMER = "programmer"
    REVIEWER = "reviewer"


class AgentState(TypedDict):
    """State shared between agents."""
    messages: Annotated[list, add_messages]
    objective: str
    architecture_plan: str
    code_implementation: str
    review_result: str
    current_agent: str
    iteration: int
    max_iterations: int
    agent_outputs: Dict[str, str]


@dataclass(frozen=True, slots=True)
class AgentConfig:
    """Configuration for a specialized agent."""
    role: AgentRole
    system_prompt: str
    temperature: float = 0.2
    max_tokens: int = 4096
    task_type: str = "general"


class MultiAgentCoordinator:
    """Coordinates multiple specialized agents using LangGraph."""
    
    AGENT_CONFIGS = {
        AgentRole.ARCHITECT: AgentConfig(
            role=AgentRole.ARCHITECT,
            system_prompt=(
                "You are a senior software architect. Analyze requirements, "
                "define system structure, select patterns, and create modular design. "
                "Focus on scalability, maintainability, and best practices. "
                "Provide clear architectural plans with component breakdown."
            ),
            temperature=0.1,
            max_tokens=2000,
            task_type="architecture"
        ),
        AgentRole.PROGRAMMER: AgentConfig(
            role=AgentRole.PROGRAMMER,
            system_prompt=(
                "You are a senior software engineer. Implement clean, tested, "
                "well-documented code following the architectural plan. "
                "Include error handling, type hints, and best practices. "
                "Focus on correctness and maintainability."
            ),
            temperature=0.2,
            max_tokens=4096,
            task_type="code"
        ),
        AgentRole.REVIEWER: AgentConfig(
            role=AgentRole.REVIEWER,
            system_prompt=(
                "You are a senior code reviewer. Evaluate code against requirements, "
                "check for bugs, security issues, performance problems, and style. "
                "Provide specific, actionable feedback with severity ratings. "
                "Be thorough but constructive."
            ),
            temperature=0.1,
            max_tokens=2000,
            task_type="review"
        ),
    }
    
    def __init__(self, ai_router: MultiProviderRouter | None = None) -> None:
        self.ai_router = ai_router or MultiProviderRouter()
        self.graph = self._build_graph()
        
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(AgentState)
        
        # Add nodes for each agent
        workflow.add_node("architect", self._architect_node)
        workflow.add_node("programmer", self._programmer_node)
        workflow.add_node("reviewer", self._reviewer_node)
        workflow.add_node("coordinator", self._coordinator_node)
        
        # Define the workflow edges
        workflow.set_entry_point("architect")
        workflow.add_edge("architect", "programmer")
        workflow.add_edge("programmer", "reviewer")
        workflow.add_edge("reviewer", "coordinator")
        
        # Conditional routing from coordinator
        workflow.add_conditional_edges(
            "coordinator",
            self._should_continue,
            {
                "continue": "programmer",  # Re-implement based on feedback
                "end": END
            }
        )
        
        return workflow.compile()
    
    def _architect_node(self, state: AgentState) -> AgentState:
        """Architect agent: analyzes requirements and creates plan."""
        logger.info(f"Architect agent processing: {state['objective'][:50]}...")
        
        config = self.AGENT_CONFIGS[AgentRole.ARCHITECT]
        prompt = (
            f"OBJECTIVE: {state['objective']}\n\n"
            "Create a detailed architectural plan including:\n"
            "- System components and their responsibilities\n"
            "- Data flow between components\n"
            "- Key patterns and technologies to use\n"
            "- Potential risks and mitigation strategies\n\n"
            "Provide the plan in a clear, structured format."
        )
        
        request = GenerationRequest(
            prompt=prompt,
            system_prompt=config.system_prompt,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            budget=0.20,
            task_type=config.task_type
        )
        
        response = self.ai_router.generate(request)
        
        state["architecture_plan"] = response.text if response.success else "Architecture generation failed"
        state["current_agent"] = "architect"
        state["agent_outputs"]["architect"] = state["architecture_plan"]
        state["messages"].append(AIMessage(content=f"Architecture: {state['architecture_plan'][:200]}..."))
        
        return state
    
    def _programmer_node(self, state: AgentState) -> AgentState:
        """Programmer agent: implements code based on architecture."""
        logger.info("Programmer agent implementing code...")
        
        config = self.AGENT_CONFIGS[AgentRole.PROGRAMMER]
        
        # Include review feedback if available
        feedback_context = ""
        if state.get("review_result") and "needs improvement" in state["review_result"].lower():
            feedback_context = f"\n\nREVIEW FEEDBACK TO ADDRESS:\n{state['review_result']}"
        
        prompt = (
            f"OBJECTIVE: {state['objective']}\n\n"
            f"ARCHITECTURAL PLAN:\n{state['architecture_plan']}\n"
            f"{feedback_context}\n\n"
            "Implement the solution following the architectural plan. "
            "Provide complete, working code with proper structure."
        )
        
        request = GenerationRequest(
            prompt=prompt,
            system_prompt=config.system_prompt,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            budget=0.30,
            task_type=config.task_type
        )
        
        response = self.ai_router.generate(request)
        
        state["code_implementation"] = response.text if response.success else "Code generation failed"
        state["current_agent"] = "programmer"
        state["agent_outputs"]["programmer"] = state["code_implementation"]
        state["messages"].append(AIMessage(content=f"Code: {state['code_implementation'][:200]}..."))
        
        return state
    
    def _reviewer_node(self, state: AgentState) -> AgentState:
        """Reviewer agent: evaluates implementation."""
        logger.info("Reviewer agent evaluating implementation...")
        
        config = self.AGENT_CONFIGS[AgentRole.REVIEWER]
        
        prompt = (
            f"OBJECTIVE: {state['objective']}\n\n"
            f"ARCHITECTURAL PLAN:\n{state['architecture_plan']}\n\n"
            f"CODE IMPLEMENTATION:\n{state['code_implementation']}\n\n"
            "Review the implementation thoroughly. Assess:\n"
            "- Correctness and completeness\n"
            "- Code quality and style\n"
            "- Security considerations\n"
            "- Performance implications\n"
            "- Alignment with architectural plan\n\n"
            "Provide specific feedback. If issues are found, clearly state what needs to be fixed. "
            "If the implementation is satisfactory, state 'APPROVED'."
        )
        
        request = GenerationRequest(
            prompt=prompt,
            system_prompt=config.system_prompt,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            budget=0.20,
            task_type=config.task_type
        )
        
        response = self.ai_router.generate(request)
        
        state["review_result"] = response.text if response.success else "Review generation failed"
        state["current_agent"] = "reviewer"
        state["agent_outputs"]["reviewer"] = state["review_result"]
        state["messages"].append(AIMessage(content=f"Review: {state['review_result'][:200]}..."))
        
        return state
    
    def _coordinator_node(self, state: AgentState) -> AgentState:
        """Coordinator: decides whether to continue or end."""
        logger.info("Coordinator evaluating results...")
        
        state["current_agent"] = "coordinator"
        state["iteration"] = state.get("iteration", 0) + 1
        
        # Add coordinator message
        decision = "continue" if self._should_continue(state) == "continue" else "end"
        state["messages"].append(AIMessage(content=f"Coordinator decision: {decision}"))
        
        return state
    
    def _should_continue(self, state: AgentState) -> str:
        """Decide whether to continue iteration or end."""
        # Check if review indicates approval
        review_text = state.get("review_result", "").lower()
        
        if "approved" in review_text or "no issues" in review_text:
            logger.info("Implementation approved - ending workflow")
            return "end"
        
        # Check iteration limit
        if state.get("iteration", 0) >= state.get("max_iterations", 3):
            logger.info("Max iterations reached - ending workflow")
            return "end"
        
        # Continue for another iteration
        logger.info(f"Continuing iteration {state.get('iteration', 0) + 1}")
        return "continue"
    
    def execute(self, objective: str, max_iterations: int = 3) -> Dict[str, Any]:
        """Execute the multi-agent workflow."""
        logger.info(f"Starting multi-agent workflow for: {objective[:50]}...")
        
        initial_state: AgentState = {
            "messages": [HumanMessage(content=objective)],
            "objective": objective,
            "architecture_plan": "",
            "code_implementation": "",
            "review_result": "",
            "current_agent": "",
            "iteration": 0,
            "max_iterations": max_iterations,
            "agent_outputs": {}
        }
        
        try:
            final_state = self.graph.invoke(initial_state)
            
            return {
                "success": True,
                "objective": objective,
                "architecture_plan": final_state["architecture_plan"],
                "code_implementation": final_state["code_implementation"],
                "review_result": final_state["review_result"],
                "iterations": final_state["iteration"],
                "messages": final_state["messages"],
                "approved": "approved" in final_state["review_result"].lower()
            }
        except Exception as e:
            logger.error(f"Multi-agent workflow failed: {str(e)}")
            return {
                "success": False,
                "objective": objective,
                "error": str(e),
                "iterations": initial_state["iteration"]
            }
    
    def get_workflow_stats(self) -> Dict[str, Any]:
        """Get statistics about the workflow."""
        return {
            "agents": list(self.AGENT_CONFIGS.keys()),
            "total_agents": len(self.AGENT_CONFIGS),
            "ai_router_available": self.ai_router is not None,
            "workflow_nodes": ["architect", "programmer", "reviewer", "coordinator"]
        }