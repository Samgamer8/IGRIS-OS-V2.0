from __future__ import annotations

import json
from pathlib import Path

import pytest

from igris_os.programming.coordinator import (
    ArchitecturePlan,
    AutonomousProgrammingCoordinator,
    CodeProposal,
    ReviewVerdict,
)
from igris_os.programming.specialists import (
    SpecialistOutput,
    SpecialistRegistry,
    SpecialistRole,
)


class FakeClient:
    def __init__(self, responses: dict[str, str]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def models(self):
        return tuple(self.responses.keys())

    def generate(self, prompt: str, model: str):
        self.calls.append((prompt, model))
        if model in self.responses:
            text = self.responses[model]
            return type("R", (), {"ok": True, "text": text, "error": ""})()
        if "Genera plan arquitectonico JSON." in prompt:
            return type("R", (), {"ok": True, "text": ARCHITECT_JSON, "error": ""})()
        if "Implementa SOLO el modulo principal con tests. JSON." in prompt:
            return type("R", (), {"ok": True, "text": PROGRAMMER_JSON, "error": ""})()
        if "Revisa y puntua. JSON." in prompt:
            return type("R", (), {"ok": True, "text": REVIEWER_JSON, "error": ""})()
        return type("R", (), {"ok": False, "text": "", "error": "no response"})()


ARCHITECT_JSON = json.dumps({
    "plan": "Modulo principal con interfaz CLI",
    "modules": ["main", "service"],
    "interfaces": ["ICalculator"],
    "risks": ["entrada negativa"],
    "acceptance": ["tests pasan", "type hints"],
})


PROGRAMMER_JSON = json.dumps({
    "source": "def add(a: int, b: int) -> int:\n    return a + b\n",
    "tests": "import unittest\nfrom solution import add\nclass T(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(1,2),3)\n",
    "explanation": "Suma simple",
})


REVIEWER_JSON = json.dumps({
    "approved": True,
    "score": 0.95,
    "issues": [],
    "suggestions": ["Anadir docstring"],
})


def test_autonomous_coordinator_completes_mission(tmp_path: Path):
    client = FakeClient({
        "qwen2.5-coder:7b": PROGRAMMER_JSON,
        "qwen2.5-coder:14b": REVIEWER_JSON,
        "default": ARCHITECT_JSON,
    })
    coordinator = AutonomousProgrammingCoordinator(
        client, tmp_path, default_model="qwen2.5-coder:7b",
        review_model="qwen2.5-coder:14b")
    result = coordinator.execute("Crea una calculadora simple", confirmed=True)
    assert result.ok
    assert result.plan is not None
    assert result.proposal is not None
    assert result.review is not None
    assert result.review.approved
    assert "add" in result.proposal.source


def test_autonomous_coordinator_rejects_without_confirmation(tmp_path: Path):
    client = FakeClient({})
    coordinator = AutonomousProgrammingCoordinator(
        client, tmp_path)
    result = coordinator.execute("Crea algo", confirmed=False)
    assert not result.ok
    assert "confirmacion" in result.message.lower()


def test_autonomous_coordinator_handles_architect_failure(tmp_path: Path):
    client = FakeClient({
        "qwen2.5-coder:7b": "no json here",
    })
    coordinator = AutonomousProgrammingCoordinator(
        client, tmp_path)
    result = coordinator.execute("Crea algo", confirmed=True)
    assert not result.ok
    assert "arquitectura" in result.message.lower()


def test_specialist_registry_executes(tmp_path: Path):
    client = FakeClient({
        "default": '{"ok": true, "text": "hecho"}',
    })
    registry = SpecialistRegistry(client)
    output = registry.execute(SpecialistRole.ARCHITECT, "plan")
    assert output.ok
    assert output.role == SpecialistRole.ARCHITECT


def test_specialist_registry_fallback_model(tmp_path: Path):
    client = FakeClient({
        "llama3.1:8b": '{"ok": true, "text": "hecho"}',
    })
    registry = SpecialistRegistry(client)
    output = registry.execute(SpecialistRole.PROGRAMMER, "code")
    assert output.ok
    assert output.model == "llama3.1:8b"


def test_extract_json_from_fenced():
    text = "```json\n{\"key\": \"value\"}\n```"
    data = AutonomousProgrammingCoordinator._extract_json(text)
    assert data["key"] == "value"


def test_extract_json_plain():
    text = '{"score": 0.9, "approved": true}'
    data = AutonomousProgrammingCoordinator._extract_json(text)
    assert data["score"] == 0.9
    assert data["approved"] is True
