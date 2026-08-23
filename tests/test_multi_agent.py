"""Test script for multi-agent coordination system."""
import sys
from pathlib import Path

import pytest

# El coordinador multi-agente se construye sobre LangGraph, que no forma
# parte de las dependencias del proyecto. Sin el, la demo no puede ni
# importarse, asi que la suite pytest la salta de forma limpia.
pytest.importorskip("langgraph", reason="multi-agent demo requiere langgraph")
pytest.importorskip("langchain_core", reason="multi-agent demo requiere langchain_core")

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from igris_os.multi_agent import MultiAgentCoordinator
from igris_os.ai.multi_provider import MultiProviderRouter


def test_workflow_stats():
    """Test workflow statistics."""
    print("=== Testing Multi-Agent Coordinator ===\n")
    
    router = MultiProviderRouter()
    coordinator = MultiAgentCoordinator(router)
    stats = coordinator.get_workflow_stats()
    
    print(f"Available Agents: {stats['agents']}")
    print(f"Total Agents: {stats['total_agents']}")
    print(f"AI Router Available: {stats['ai_router_available']}")
    print(f"Workflow Nodes: {stats['workflow_nodes']}")
    assert stats["total_agents"] == 3
    assert stats["ai_router_available"] is True
    assert len(stats["workflow_nodes"]) == 4


@pytest.mark.skip(reason="demo multi-agente: requiere LLM en vivo")
def test_simple_workflow(coordinator: MultiAgentCoordinator):
    """Test simple multi-agent workflow."""
    print("=== Testing Simple Multi-Agent Workflow ===\n")
    
    objective = "Create a simple Python function that calculates the factorial of a number"
    
    print(f"Objective: {objective}\n")
    print("Starting workflow...\n")
    
    result = coordinator.execute(objective, max_iterations=2)
    
    print(f"Success: {result['success']}")
    print(f"Iterations: {result['iterations']}")
    print(f"Approved: {result.get('approved', False)}")
    
    if result['success']:
        print("\n--- Architecture Plan ---")
        print(result['architecture_plan'][:500] + "..." if len(result['architecture_plan']) > 500 else result['architecture_plan'])
        
        print("\n--- Code Implementation ---")
        print(result['code_implementation'][:500] + "..." if len(result['code_implementation']) > 500 else result['code_implementation'])
        
        print("\n--- Review Result ---")
        print(result['review_result'][:500] + "..." if len(result['review_result']) > 500 else result['review_result'])
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
    
    print()


@pytest.mark.skip(reason="demo multi-agente: requiere LLM en vivo")
def test_api_workflow(coordinator: MultiAgentCoordinator):
    """Test workflow for API design."""
    print("=== Testing API Design Workflow ===\n")
    
    objective = "Design and implement a simple REST API for managing a todo list"
    
    print(f"Objective: {objective}\n")
    print("Starting workflow...\n")
    
    result = coordinator.execute(objective, max_iterations=2)
    
    print(f"Success: {result['success']}")
    print(f"Iterations: {result['iterations']}")
    print(f"Approved: {result.get('approved', False)}")
    
    if result['success']:
        print("\n--- Architecture Plan ---")
        print(result['architecture_plan'][:400] + "..." if len(result['architecture_plan']) > 400 else result['architecture_plan'])
        
        print("\n--- Code Implementation (first 300 chars) ---")
        print(result['code_implementation'][:300] + "..." if len(result['code_implementation']) > 300 else result['code_implementation'])
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
    
    print()


@pytest.mark.skip(reason="demo multi-agente: requiere LLM en vivo")
def test_iteration_logic(coordinator: MultiAgentCoordinator):
    """Test iteration logic with max iterations."""
    print("=== Testing Iteration Logic ===\n")
    
    objective = "Create a complex data processing pipeline"
    
    print(f"Objective: {objective}")
    print(f"Max iterations: 1 (to test iteration limit)\n")
    
    result = coordinator.execute(objective, max_iterations=1)
    
    print(f"Success: {result['success']}")
    print(f"Iterations completed: {result['iterations']}")
    print(f"Reached max iterations: {result['iterations'] >= 1}")
    
    print()


if __name__ == "__main__":
    test_workflow_stats()
    router = MultiProviderRouter()
    coordinator = MultiAgentCoordinator(router)
    
    # Run tests
    print("Running workflow tests...\n")
    test_simple_workflow(coordinator)
    test_api_workflow(coordinator)
    test_iteration_logic(coordinator)
    
    print("=== Multi-Agent Tests Complete ===")