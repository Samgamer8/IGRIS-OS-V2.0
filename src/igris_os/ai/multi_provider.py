"""Multi-provider AI router with intelligent fallback system."""
from __future__ import annotations

import logging
import copy
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

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
    
    def __init__(self, fallback_enabled: bool = True, local_client: Any | None = None) -> None:
        self.fallback_enabled = fallback_enabled
        self._local_client = local_client
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
        if provider != ProviderRank.OLLAMA:
            return False
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
            
        if self._local_client is None:
            from igris_os.ai import OllamaClient
            self._local_client = OllamaClient()
        available = bool(self._local_models())
        self._availability_cache[provider] = available
        return available

    def _local_models(self) -> tuple[str, ...]:
        return tuple(model for model in self._local_client.models()
                     if ':cloud' not in model.lower()
                     and not model.lower().startswith(('cloud/', 'moonshot/')))
    
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
        if provider != ProviderRank.OLLAMA:
            return GenerationResponse(
                text='', provider=provider, model='', success=False,
                error='Proveedor bloqueado: IGRIS solo permite inferencia local sin suscripciones')
        try:
            from igris_os.ai import OllamaClient
            from igris_os.ai.model_selection import select_installed_model

            if self._local_client is None:
                self._local_client = OllamaClient()
            model = select_installed_model(self._local_models())
            if not model:
                raise RuntimeError('No hay modelos locales disponibles')
            client = copy.copy(self._local_client)
            client.output_token_limit = min(8192, max(256, request.max_tokens))
            prompt = ((request.system_prompt + '\n\n') if request.system_prompt else '') + request.prompt
            reply = client.generate(prompt, model)
            return GenerationResponse(
                text=reply.text, provider=provider, model=reply.model,
                cost_usd=0.0, success=reply.ok, error=reply.error)
        except Exception as exc:
            return GenerationResponse('', provider, '', success=False, error=str(exc))
    
    def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Generate response with automatic fallback."""
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