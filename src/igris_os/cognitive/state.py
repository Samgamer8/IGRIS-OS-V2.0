"""Estado contextual compacto y persistente para conversaciones y misiones."""
from __future__ import annotations

import json
import os
from pathlib import Path
from threading import RLock
from typing import Any

from .models import IntentFrame


class CognitiveStateStore:
    """Persiste sólo estado útil; no acumula una transcripción infinita."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = RLock()
        self._state = self._load()

    def _empty(self) -> dict[str, Any]:
        return {
            "schema": 1,
            "active_domain": "",
            "active_intent": "",
            "active_goal": "",
            "active_target": "",
            "active_mode": "",
            "last_capability": "",
            "constraints": [],
            "pending_domain": "",
            "pending_intent": "",
            "pending_goal": "",
            "pending_mode": "",
            "pending_question": "",
            "pending_constraints": [],
            "recent": [],
        }

    def _load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return self._empty()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return self._empty()
        if not isinstance(data, dict) or data.get("schema") != 1:
            return self._empty()
        return self._normalize(data)

    def _normalize(self, data: dict[str, Any]) -> dict[str, Any]:
        """Sanea estado persistido para que datos viejos/corruptos no rompan la UI."""
        state = self._empty()
        for key in (
            "active_domain", "active_intent", "active_goal", "active_target",
            "active_mode", "last_capability",
            "pending_domain", "pending_intent", "pending_goal",
            "pending_mode", "pending_question",
        ):
            value = data.get(key, "")
            state[key] = value if isinstance(value, str) else str(value or "")

        constraints = data.get("constraints", [])
        if isinstance(constraints, list):
            state["constraints"] = [str(item)[:500] for item in constraints[:12]]

        pending_constraints = data.get("pending_constraints", [])
        if isinstance(pending_constraints, list):
            state["pending_constraints"] = [str(item)[:500] for item in pending_constraints[:12]]

        recent = data.get("recent", [])
        if isinstance(recent, list):
            state["recent"] = [item for item in recent[-12:] if isinstance(item, dict)]
        return state

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return json.loads(json.dumps(self._state, ensure_ascii=False))

    def context(self) -> dict[str, Any]:
        state = self.snapshot()
        return {
            "active_domain": state.get("active_domain", ""),
            "active_intent": state.get("active_intent", ""),
            "active_goal": state.get("active_goal", ""),
            "active_target": state.get("active_target", ""),
            "active_mode": state.get("active_mode", ""),
            "last_capability": state.get("last_capability", ""),
            "constraints": list(state.get("constraints", ()))[:12],
            "pending_domain": state.get("pending_domain", ""),
            "pending_intent": state.get("pending_intent", ""),
            "pending_goal": state.get("pending_goal", ""),
            "pending_mode": state.get("pending_mode", ""),
            "pending_question": state.get("pending_question", ""),
            "pending_constraints": list(state.get("pending_constraints", ()))[:12],
            "recent_decisions": list(state.get("recent", ())) [-6:],
        }

    def record(self, message: str, frame: IntentFrame, capability: str = "") -> None:
        with self._lock:
            if frame.operational and frame.needs_clarification:
                self._state.update(
                    pending_domain=frame.domain,
                    pending_intent=frame.intent,
                    pending_goal=frame.goal,
                    pending_mode=frame.mode,
                    pending_question=frame.clarification_question,
                    pending_constraints=list(frame.constraints),
                )
            elif frame.operational:
                self._state.update(
                    active_domain=frame.domain,
                    active_intent=frame.intent,
                    active_goal=frame.goal,
                    active_target=frame.target,
                    active_mode=frame.mode,
                    constraints=list(frame.constraints),
                    pending_domain="", pending_intent="", pending_goal="",
                    pending_mode="", pending_question="", pending_constraints=[],
                )
            if capability:
                self._state["last_capability"] = capability
            recent = list(self._state.get("recent", ()))
            recent.append({
                "message": str(message)[:600],
                "domain": frame.domain,
                "intent": frame.intent,
                "mode": frame.mode,
                "goal": frame.goal[:500],
                "target": frame.target[:300],
                "continuation": frame.continuation,
                "confidence": frame.confidence,
                "capability": capability,
            })
            self._state["recent"] = recent[-12:]
            self._save_locked()

    def clear_active(self) -> None:
        with self._lock:
            for key in ("active_domain", "active_intent", "active_goal", "active_target",
                        "active_mode", "last_capability", "pending_domain", "pending_intent",
                        "pending_goal", "pending_mode", "pending_question"):
                self._state[key] = ""
            self._state["constraints"] = []
            self._state["pending_constraints"] = []
            self._save_locked()

    def _save_locked(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(self._state, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, self.path)
