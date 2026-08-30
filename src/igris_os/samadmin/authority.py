from __future__ import annotations

from .client import SamadminClient


class SamadminApprovalAuthority:
    """Adaptador para que el kernel delegue permisos en Samadmin externo."""

    _PLAN_CAPABILITIES = frozenset({
        "project.plan", "programming.assess", "programming.propose",
    })
    _DELIVER_CAPABILITIES = frozenset({
        "delivery.verify", "games.godot.export", "project.deliver",
    })

    def __init__(self, client: SamadminClient) -> None:
        self.client = client

    def issue(self, binding: str, capability: str) -> str:
        request = self.client.request(binding, capability, self.stage_for(capability))
        return str(request["request_id"])

    def verify(self, token: str | None, binding: str, capability: str) -> bool:
        if not token:
            return False
        return self.client.consume(token, binding, capability, self.stage_for(capability))

    @classmethod
    def stage_for(cls, capability: str) -> str:
        if capability in cls._PLAN_CAPABILITIES:
            return "plan"
        if capability in cls._DELIVER_CAPABILITIES:
            return "deliver"
        return "write"