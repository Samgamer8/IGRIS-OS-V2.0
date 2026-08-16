from .core import register_core_capabilities
from .creation import register_creation_capabilities
from .git_capabilities import register_git_capabilities
from .system_health import register_system_health
from .voice_capabilities import register_voice_capabilities

__all__ = ["register_core_capabilities", "register_creation_capabilities",
           "register_git_capabilities", "register_voice_capabilities", "register_system_health"]
