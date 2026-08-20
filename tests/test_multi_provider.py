"""Test script for multi-provider AI router."""
import sys
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from igris_os.ai.multi_provider import MultiProviderRouter, GenerationRequest, ProviderRank


@pytest.fixture
def router():
    return MultiProviderRouter()


def test_provider_stats():
    """Test provider availability and statistics."""
    print("=== Testing Multi-Provider Router ===\n")
    
    router = MultiProviderRouter()
    stats = router.get_provider_stats()
    
    print(f"LiteLLM Available: {stats['litellm_available']}")
    print(f"Available Providers: {stats['available']}")
    print(f"Total Providers: {stats['total']}")
    print(f"Custom Priority: {stats['custom_priority']}")
    assert "available" in stats
    assert "total" in stats
    assert stats["total"] >= 1


def test_ollama_fallback(router: MultiProviderRouter):
    """Test with Ollama (should work without API keys)."""
    print("=== Testing Ollama Fallback ===\n")
    
    request = GenerationRequest(
        prompt="Write a simple Python function that adds two numbers.",
        system_prompt="You are a Python expert.",
        temperature=0.2,
        max_tokens=500,
        budget=0.10,
        task_type="code"
    )
    
    try:
        response = router.generate(request)
        
        print(f"Provider: {response.provider.value}")
        print(f"Model: {response.model}")
        print(f"Success: {response.success}")
        print(f"Tokens Used: {response.tokens_used}")
        print(f"Cost: ${response.cost_usd:.6f}")
        
        if response.success:
            print(f"\nGenerated Code:\n{response.text[:500]}...")
        else:
            print(f"Error: {response.error}")
            
    except Exception as e:
        print(f"Test failed: {str(e)}")
    
    print()


def test_architecture_task(router: MultiProviderRouter):
    """Test architecture task routing."""
    print("=== Testing Architecture Task Routing ===\n")
    
    request = GenerationRequest(
        prompt="Design a simple web API architecture.",
        system_prompt="You are a software architect.",
        temperature=0.1,
        max_tokens=300,
        budget=0.50,
        task_type="architecture"
    )
    
    try:
        response = router.generate(request)
        
        print(f"Provider: {response.provider.value}")
        print(f"Success: {response.success}")
        
        if response.success:
            print(f"Generated:\n{response.text[:300]}...")
        else:
            print(f"Error: {response.error}")
            
    except Exception as e:
        print(f"Test failed: {str(e)}")
    
    print()


def test_budget_constraints(router: MultiProviderRouter):
    """Test budget-based provider selection."""
    print("=== Testing Budget Constraints ===\n")
    
    # Test with very low budget (should use Ollama)
    low_budget_request = GenerationRequest(
        prompt="Say hello",
        system_prompt="Be brief.",
        temperature=0.0,
        max_tokens=50,
        budget=0.001,  # Very low budget
        task_type="general"
    )
    
    try:
        response = router.generate(low_budget_request)
        print(f"Low Budget Test - Provider: {response.provider.value}")
        print(f"Cost: ${response.cost_usd:.6f}")
    except Exception as e:
        print(f"Low budget test failed: {str(e)}")
    
    print()


if __name__ == "__main__":
    test_provider_stats()
    router = MultiProviderRouter()
    
    # Only run Ollama tests if it's available
    if ProviderRank.OLLAMA.value in router.get_provider_stats()["available"]:
        print("Ollama is available - running tests...\n")
        test_ollama_fallback(router)
        test_architecture_task(router)
        test_budget_constraints(router)
    else:
        print("Ollama not available. Add API keys to .env for other providers.")
        print("To test with other providers, configure credentials in .env file.")
    
    print("\n=== Test Complete ===")