from igris_os.domain.models import CapabilityHandler, CapabilitySpec


class CapabilityRegistry:
    def __init__(self) -> None:
        self._items: dict[str, tuple[CapabilitySpec, CapabilityHandler]] = {}

    def register(self, spec: CapabilitySpec, handler: CapabilityHandler) -> None:
        if not spec.name or spec.name in self._items:
            raise ValueError(f"Capacidad duplicada o invalida: {spec.name}")
        self._items[spec.name] = (spec, handler)

    def get(self, name: str):
        return self._items.get(name)

    def specs(self) -> tuple[CapabilitySpec, ...]:
        return tuple(spec for spec, _ in self._items.values())

