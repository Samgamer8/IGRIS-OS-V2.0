from __future__ import annotations

import json
from urllib import error, request


class SamadminClient:
    """Cliente mínimo para que IGRIS solicite y consuma permisos externos."""

    def __init__(self, endpoint: str) -> None:
        if not endpoint.startswith("http://127.0.0.1"):
            raise ValueError("Samadmin debe usar loopback")
        self.endpoint = endpoint.rstrip("/")

    def request(self, objective: str, capability: str, stage: str) -> dict:
        return self._post("/v1/requests", {
            "objective": objective, "capability": capability, "stage": stage})

    def consume(self, request_id: str, objective: str,
                capability: str, stage: str) -> bool:
        response = self._post("/v1/authorizations/consume", {
            "request_id": request_id, "objective": objective,
            "capability": capability, "stage": stage})
        return response.get("approved") is True

    def decide(self, request_id: str, *, approved: bool,
               operator: str, admin_token: str) -> dict:
        if not admin_token:
            raise ValueError("Samadmin requiere token de administrador")
        decision = "approve" if approved else "reject"
        return self._post(
            f"/v1/requests/{request_id}/{decision}", {"operator": operator},
            headers={"X-Samadmin-Token": admin_token})

    def status(self, request_id: str) -> dict:
        with request.urlopen(self.endpoint + "/v1/requests/" + request_id,
                             timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))

    def pending(self) -> tuple[dict, ...]:
        with request.urlopen(self.endpoint + "/v1/requests", timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
        requests = data.get("requests", []) if isinstance(data, dict) else []
        return tuple(item for item in requests if isinstance(item, dict))

    def _post(self, path: str, payload: dict,
              headers: dict[str, str] | None = None) -> dict:
        data = json.dumps(payload).encode("utf-8")
        request_headers = {"Content-Type": "application/json"}
        request_headers.update(headers or {})
        req = request.Request(self.endpoint + path, data=data,
                              headers=request_headers, method="POST")
        try:
            with request.urlopen(req, timeout=5) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.URLError as exc:
            raise ConnectionError("Samadmin no disponible") from exc