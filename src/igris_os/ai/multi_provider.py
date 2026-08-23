"""Multi-provider AI router with intelligent fallback system."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    from litellm import completion, acompletion
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False

if load_dotenv is not None:
    load_dotenv()

logger = logging.getLogger(__name__)


class ProviderRank(str, Enum):
    """Provider priority ranking from lowest to highest cost."""
    OLLAMA = "ollama"           # Free, local, less powerful
    DEEPSEEK = "deepseek"       # Cheap, good for code
    GROQ = "groq"               # Ultra-fast, low cost
    TOGETHER = "together"       # Cheap, good performance
    ANTHROPIC = "anthropic"     # Expensive, excellent reasoning
    OPENAI = "openai"           # Most expensive, best generation


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    """Configuration for a specific AI provider."""
    name: ProviderRank
    model: str
    api_key_env: str
    base_url_env: str = ""
    cost_per_1k_tokens: float = 0.001
    available: bool = True


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    """Request for AI generation."""
    prompt: str
    system_prompt: str = ""
    temperature: float = 0.2
    max_tokens: int = 4096
    budget: float = 0.10
    task_type: str = "general"  # general, code, architecture, review


@dataclass(frozen=True, slots=True)
class GenerationResponse:
    """Response from AI provider."""
    text: str
    provider: ProviderRank
    model: str
    tokens_used: int = 0
    cost_usd: float = 0.0
    success: bool = True
    error: str = ""


class MultiProviderRouter:
    """Intelligent router for multi-provider AI with automatic fallback."""
    
    PROVIDER_CONFIGS = {
        ProviderRank.OLLAMA: ProviderConfig(
            name=ProviderRank.OLLAMA,
            model=f"ollama/{os.getenv('OLLAMA_MODEL', 'qwen2.5-coder:7b')}",
            api_key_env="",
            base_url_env="OLLAMA_BASE_URL",
            cost_per_1k_tokens=0.0,
            available=True
        ),
        ProviderRank.DEEPSEEK: ProviderConfig(
            name=ProviderRank.DEEPSEEK,
            model="deepseek/deepseek-coder",
            api_key_env="DEEPSEEK_API_KEY",
            cost_per_1k_tokens=0.00014,
            available=bool(os.getenv("DEEPSEEK_API_KEY"))
        ),
        ProviderRank.GROQ: ProviderConfig(
            name=ProviderRank.GROQ,
            model="groq/llama3-70b-8192",
            api_key_env="GROQ_API_KEY",
            cost_per_1k_tokens=0.00059,
            available=bool(os.getenv("GROQ_API_KEY"))
        ),
        ProviderRank.TOGETHER: ProviderConfig(
            name=ProviderRank.TOGETHER,
            model="together_ai/meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
            api_key_env="TOGETHER_API_KEY",
            cost_per_1k_tokens=0.0009,
            available=bool(os.getenv("TOGETHER_API_KEY"))
        ),
        ProviderRank.ANTHROPIC: ProviderConfig(
            name=ProviderRank.ANTHROPIC,
            model="anthropic/claude-3-5-sonnet-20240620",
            api_key_env="ANTHROPIC_API_KEY",
            cost_per_1k_tokens=0.003,
            available=bool(os.getenv("ANTHROPIC_API_KEY"))
        ),
        ProviderRank.OPENAI: ProviderConfig(
            name=ProviderRank.OPENAI,
            model="openai/gpt-4o",
            api_key_env="OPENAI_API_KEY",
            cost_per_1k_tokens=0.005,
            available=bool(os.getenv("OPENAI_API_KEY"))
        ),
    }
    
    TASK_TYPE_PRIORITIES = {
        "architecture": [ProviderRank.ANTHROPIC, ProviderRank.OPENAI, ProviderRank.DEEPSEEK, ProviderRank.OLLAMA],
        "code": [ProviderRank.DEEPSEEK, ProviderRank.GROQ, ProviderRank.ANTHROPIC, ProviderRank.OLLAMA],
        "review": [ProviderRank.ANTHROPIC, ProviderRank.OPENAI, ProviderRank.DEEPSEEK, ProviderRank.OLLAMA],
        "general": [ProviderRank.OLLAMA, ProviderRank.DEEPSEEK, ProviderRank.GROQ, ProviderRank.ANTHROPIC, ProviderRank.OPENAI],
    }
    
    def __init__(self, fallback_enabled: bool = True) -> None:
        self.fallback_enabled = fallback_enabled
        self.custom_priority = self._parse_custom_priority()
        self._availability_cache = {}
        
    def _parse_custom_priority(self) -> list[ProviderRank]:
        """Parse custom priority from environment variable."""
        priority_str = os.getenv("PROVIDER_PRIORITY", "")
        if not priority_str:
            return None
            
        try:
            custom_order = []
            for name in priority_str.split(","):
                name = name.strip().lower()
                for rank in ProviderRank:
                    if rank.value == name:
                        custom_order.append(rank)
                        break
            return custom_order if custom_order else None
        except Exception:
            return None
    
    def _get_provider_priority(self, task_type: str) -> list[ProviderRank]:
        """Get provider priority based on task type."""
        if self.custom_priority:
            return self.custom_priority
            
        return self.TASK_TYPE_PRIORITIES.get(task_type, self.TASK_TYPE_PRIORITIES["general"])
    
    def _is_provider_available(self, provider: ProviderRank) -> bool:
        """Check if provider is available with valid credentials."""
        if provider in self._availability_cache:
            return self._availability_cache[provider]
            
        config = self.PROVIDER_CONFIGS.get(provider)
        if not config:
            self._availability_cache[provider] = False
            return False
            
        # Check API key
        if config.api_key_env and not os.getenv(config.api_key_env):
            self._availability_cache[provider] = False
            return False
            
        # For Ollama, check if litellm is available
        if provider == ProviderRank.OLLAMA and not LITELLM_AVAILABLE:
            self._availability_cache[provider] = False
            return False
            
        self._availability_cache[provider] = config.available
        return config.available
    
    def _estimate_cost(self, provider: ProviderRank, max_tokens: int) -> float:
        """Estimate cost for generation request."""
        config = self.PROVIDER_CONFIGS.get(provider)
        if not config:
            return float('inf')
        return (max_tokens / 1000) * config.cost_per_1k_tokens
    
    def _select_provider(self, request: GenerationRequest) -> ProviderRank:
        """Select best provider based on budget, task type, and availability."""
        priority = self._get_provider_priority(request.task_type)
        max_budget = float(os.getenv("MAX_BUDGET_PER_REQUEST", "0.50"))
        
        for provider in priority:
            if not self._is_provider_available(provider):
                continue
                
            estimated_cost = self._estimate_cost(provider, request.max_tokens)
            if estimated_cost > max_budget:
                continue
                
            if estimated_cost <= request.budget:
                return provider
                
        # Fallback to any available provider within max budget
        for provider in ProviderRank:
            if self._is_provider_available(provider):
                estimated_cost = self._estimate_cost(provider, request.max_tokens)
                if estimated_cost <= max_budget:
                    return provider
                    
        raise RuntimeError("No available provider within budget constraints")
    
    def _execute_with_provider(self, provider: ProviderRank, request: GenerationRequest) -> GenerationResponse:
        """Execute generation request with specific provider."""
        if not LITELLM_AVAILABLE:
            return GenerationResponse(
                text="", provider=provider, model="", success=False,
                error="litellm not available"
            )
            
        config = self.PROVIDER_CONFIGS[provider]
        
        try:
            # Prepare litellm parameters
            litellm_params = {
                "model": config.model,
                "messages": [],
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
            }
            
            if request.system_prompt:
                litellm_params["messages"].append({"role": "system", "content": request.system_prompt})
            litellm_params["messages"].append({"role": "user", "content": request.prompt})
            
            # Add API key if needed (litellm handles this automatically with env vars)
            if config.api_key_env:
                api_key = os.getenv(config.api_key_env)
                if api_key:
                    litellm_params["api_key"] = api_key
                
            # Add base URL for Ollama
            if config.base_url_env:
                base_url = os.getenv(config.base_url_env)
                if base_url:
                    litellm_params["api_base"] = base_url
            
            # Execute request
            response = completion(**litellm_params)
            
            # Extract response
            text = response.choices[0].message.content if response.choices else ""
            tokens_used = response.usage.total_tokens if response.usage else 0
            cost = self._estimate_cost(provider, tokens_used)
            
            return GenerationResponse(
                text=text,
                provider=provider,
                model=config.model,
                tokens_used=tokens_used,
                cost_usd=cost,
                success=True
            )
            
        except Exception as e:
            logger.error(f"Provider {provider.value} failed: {str(e)}")
            return GenerationResponse(
                text="", provider=provider, model=config.model,
                success=False, error=str(e)
            )
    
    def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Generate response with automatic fallback."""
        if not LITELLM_AVAILABLE:
            raise RuntimeError("litellm is required for multi-provider routing")
            
        selected_provider = self._select_provider(request)
        response = self._execute_with_provider(selected_provider, request)
        
        if response.success or not self.fallback_enabled:
            return response
            
        # Fallback to next available provider
        priority = self._get_provider_priority(request.task_type)
        provider_index = priority.index(selected_provider) if selected_provider in priority else -1
        
        for provider in priority[provider_index + 1:]:
            if not self._is_provider_available(provider):
                continue
                
            logger.info(f"Fallback: {selected_provider.value} -> {provider.value}")
            response = self._execute_with_provider(provider, request)
            
            if response.success:
                return response
                
        # All providers failed
        return GenerationResponse(
            text="", provider=selected_provider, model="",
            success=False, error="All providers failed"
        )
    
    def get_available_providers(self) -> list[ProviderRank]:
        """Get list of currently available providers."""
        return [p for p in ProviderRank if self._is_provider_available(p)]
    
    def get_provider_stats(self) -> dict[str, Any]:
        """Get statistics about available providers."""
        return {
            "available": [p.value for p in self.get_available_providers()],
            "total": len(ProviderRank),
            "custom_priority": [p.value for p in self.custom_priority] if self.custom_priority else None,
            "litellm_available": LITELLM_AVAILABLE
        }