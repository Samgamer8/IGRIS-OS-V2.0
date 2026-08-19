import os
import sys
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
import litellm
from litellm import completion

def _sanitize_environment() -> None:
    bad_value = "org-c81c031a5edc4ed3994d966d702c40b9/"
    env_vars_to_check = [
        "OPENAI_API_BASE", 
        "LITELLM_API_BASE", 
        "OPENAI_BASE_URL", 
        "ANYSCALE_API_BASE",
        "HELICONE_API_BASE"
    ]
    for key, value in list(os.environ.items()):
        if bad_value in value or (("org-" in value) and ("http" not in value.lower())):
            os.environ.pop(key, None)

_sanitize_environment()

class AIProviderRouter:
    def __init__(self, fallback_strategy: Optional[List[str]] = None) -> None:
        self.providers: List[str] = fallback_strategy or ["ollama", "anthropic", "openai", "deepseek"]
        self._setup_credentials()
        litellm.num_retries = 2

    def _setup_credentials(self) -> None:
        litellm.vertex_project = os.getenv("VERTEX_PROJECT")
        litellm.api_key = os.getenv("UNIVERSAL_AI_KEY")

    def _map_model_string(self, provider: str) -> str:
        mapping: Dict[str, str] = {
            "ollama": "ollama/llama3",
            "anthropic": "claude-3-5-sonnet-20240620",
            "openai": "gpt-4o",
            "deepseek": "deepseek/deepseek-chat"
        }
        return mapping.get(provider, "ollama/llama3")

    def execute_completion(self, messages: List[Dict[str, str]], **kwargs: Any) -> Dict[str, Any]:
        last_exception: Optional[Exception] = None
        
        for provider in self.providers:
            try:
                model_string = self._map_model_string(provider)
                response = completion(
                    model=model_string,
                    messages=messages,
                    timeout=30,
                    **kwargs
                )
                return response # type: ignore
            except Exception as e:
                last_exception = e
                continue
                
        raise RuntimeWarning(f"All AI providers failed. Last error: {str(last_exception)}")
