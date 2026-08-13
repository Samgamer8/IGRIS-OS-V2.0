from dataclasses import dataclass
from enum import Enum


class ProviderKind(str, Enum):
    LOCAL = "local"
    REMOTE = "remote"


@dataclass(frozen=True, slots=True)
class ModelProvider:
    name: str
    kind: ProviderKind
    endpoint: str
    enabled: bool = True


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, ModelProvider] = {}

    def register(self, provider: ModelProvider) -> None:
        if not provider.name or provider.name in self._providers:
            raise ValueError("Proveedor duplicado o invalido")
        if provider.kind is ProviderKind.REMOTE and not provider.endpoint.startswith("https://"):
            raise ValueError("Proveedor remoto sin HTTPS")
        if provider.kind is ProviderKind.LOCAL and not provider.endpoint.startswith(
                ("http://127.0.0.1", "http://localhost")):
            raise ValueError("Proveedor local fuera de loopback")
        self._providers[provider.name] = provider

    def available(self, *, allow_remote: bool = False) -> tuple[ModelProvider, ...]:
        return tuple(p for p in self._providers.values()
                     if p.enabled and (allow_remote or p.kind is ProviderKind.LOCAL))


def default_providers() -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register(ModelProvider("ollama", ProviderKind.LOCAL,
                                    "http://127.0.0.1:11434"))
    return registry
