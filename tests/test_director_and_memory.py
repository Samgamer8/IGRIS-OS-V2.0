from __future__ import annotations

import json
from pathlib import Path

import pytest

from igris_os.application.director import LLMMissionDirector
from igris_os.domain import Mission
from igris_os.memory.experience import ExperienceMemory


class FakeClient:
    def __init__(self, responses: dict[str, str]) -> None:
        self.responses = responses

    def generate(self, prompt: str, model: str):
        for key, text in self.responses.items():
            if key in prompt:
                return type("R", (), {"ok": True, "text": text, "error": ""})()
        return type("R", (), {"ok": False, "text": "", "error": "no"})()


def test_llm_director_returns_contract():
    client = FakeClient({
        "Genera contrato JSON.": json.dumps({
            "branch": "programming",
            "deliverables": ["codigo", "tests"],
            "constraints": ["sin red"],
            "acceptance_criteria": ["tests pasan"],
            "risks": ["complejidad"],
            "estimated_complexity": "complex",
            "needs_clarification": False,
            "clarification_questions": [],
        })
    })
    director = LLMMissionDirector(client)
    plan = director.plan(Mission("Crea un API REST en Python"))
    assert plan.branch.value == "programming"
    assert "codigo" in plan.deliverables


def test_llm_director_falls_back_when_llm_fails():
    client = FakeClient({})
    director = LLMMissionDirector(client)
    plan = director.plan(Mission("Hola"))
    assert plan.branch.value == "general"
    assert plan.needs_clarification


def test_experience_memory_records_and_retrieves(tmp_path: Path):
    memory = ExperienceMemory(tmp_path)
    memory.record_experience("python", "programming", "unittest", True, 0.9, 1)
    memory.record_experience("python", "programming", "pytest", True, 0.8, 2)
    memory.record_experience("rust", "programming", "cargo", False, 0.4, 3)
    sim = memory.find_similar_experiences("python", "programming")
    assert len(sim) == 3
    best = memory.best_strategy("python", "programming")
    assert best == "unittest"


def test_experience_memory_template(tmp_path: Path):
    memory = ExperienceMemory(tmp_path)
    memory.record_experience("programming", "python", "unittest", True, 0.95, 1)
    tpl = memory.find_template("python", "programming:python")
    assert tpl is not None
    assert tpl.success_rate >= 0.9
