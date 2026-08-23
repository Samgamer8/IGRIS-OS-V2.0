from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass
from typing import Sequence

from igris_os.ai import ModelReply, OllamaClient
from igris_os.domain import Mission, MissionBranch, MissionPlan
from igris_os.utils.json_parser import StrictJSONParser


@dataclass(frozen=True, slots=True)
class ContractualPlan:
    mission_id: str
    branch: MissionBranch
    objective: str
    deliverables: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    acceptance_criteria: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()
    estimated_complexity: str = "normal"
    needs_clarification: bool = False
    clarification_questions: tuple[str, ...] = ()


class LLMMissionDirector:
    SYSTEM_PROMPT = (
        "Eres director de misiones. Convierte objetivos en contratos verificables. "
        "Devuelve SOLO JSON con: branch, deliverables, constraints, acceptance_criteria, "
        "risks, estimated_complexity, needs_clarification, clarification_questions. "
        "Branches: general, games, video, audio, visual_design, artificial_intelligence, "
        "programming, documents, systems. Sin markdown."
    )

    BRANCH_KEYWORDS: dict[MissionBranch, tuple[str, ...]] = {
        MissionBranch.GAMES: ("videojuego", "juego", "godot", "unity", "unreal", "pygame"),
        MissionBranch.VIDEO: ("video", "ffmpeg", "montaje", "render"),
        MissionBranch.AUDIO: ("audio", "sonido", "voz", "musica", "transcribir"),
        MissionBranch.IMAGE: ("imagen", "foto", "icono", "diseño", "sprite"),
        MissionBranch.ARTIFICIAL_INTELLIGENCE: ("inteligencia artificial", "modelo", "ia", "rag", "entrenar"),
        MissionBranch.PROGRAMMING: ("programa", "codigo", "python", "typescript", "javascript", "rust", "c++", "java"),
        MissionBranch.DOCUMENTS: ("documento", "pdf", "excel", "archivo", "carpeta"),
        MissionBranch.SYSTEMS: ("windows", "ordenador", "cpu", "ram", "sistema"),
    }

    _BRANCH_PATTERNS: dict[MissionBranch, list[re.Pattern]] = {
        branch: [re.compile(rf"(?<!\w){re.escape(kw)}(?!\w)") for kw in keywords]
        for branch, keywords in BRANCH_KEYWORDS.items()
    }

    def __init__(self, client: OllamaClient | None = None,
                 fallback_model: str = "qwen2.5-coder:7b") -> None:
        self.client = client or OllamaClient()
        self.fallback_model = fallback_model

    def plan(self, mission: Mission) -> ContractualPlan:
        branch = self._classify_branch(mission.objective)
        contract = self._generate_contract(mission, branch)
        if contract is None:
            return self._fallback_plan(mission, branch)
        if len(mission.objective.split()) < 5:
            contract = dataclasses.replace(
                contract,
                needs_clarification=True,
                clarification_questions=(
                    "Puedes dar mas detalles del objetivo?",)
                if not contract.clarification_questions else
                contract.clarification_questions,
            )
        return contract

    def _classify_branch(self, objective: str) -> MissionBranch:
        text = re.sub(r"\s+", " ", objective.casefold()).strip()
        for branch, patterns in self._BRANCH_PATTERNS.items():
            if any(pat.search(text) for pat in patterns):
                return branch
        return MissionBranch.GENERAL

    def _generate_contract(self, mission: Mission, branch: MissionBranch) -> ContractualPlan | None:
        prompt = (
            self.SYSTEM_PROMPT +
            "\n\nOBJETIVO:\n" + mission.objective +
            "\n\nGenera contrato JSON."
        )
        reply: ModelReply = self.client.generate(prompt, self.fallback_model)
        if not reply.ok:
            return None
        try:
            data = StrictJSONParser.extract(reply.text)
            deliverables = tuple(
                item["name"] if isinstance(item, dict) else str(item)
                for item in data.get("deliverables", [])
            )
            constraints = tuple(
                item["name"] if isinstance(item, dict) else str(item)
                for item in data.get("constraints", [])
            )
            acceptance_criteria = tuple(
                item["name"] if isinstance(item, dict) else str(item)
                for item in data.get("acceptance_criteria", [])
            )
            risks = tuple(
                item["name"] if isinstance(item, dict) else str(item)
                for item in data.get("risks", [])
            )
            clarification_questions = tuple(
                item["question"] if isinstance(item, dict) else str(item)
                for item in data.get("clarification_questions", [])
            )
            return ContractualPlan(
                mission_id=mission.id,
                branch=branch,
                objective=mission.objective,
                deliverables=deliverables,
                constraints=constraints,
                acceptance_criteria=acceptance_criteria,
                risks=risks,
                estimated_complexity=str(data.get("estimated_complexity", "normal")),
                needs_clarification=bool(data.get("needs_clarification", False)),
                clarification_questions=clarification_questions,
            )
        except (ValueError, TypeError, KeyError):
            return None

    def _fallback_plan(self, mission: Mission, branch: MissionBranch) -> ContractualPlan:
        return ContractualPlan(
            mission_id=mission.id,
            branch=branch,
            objective=mission.objective,
            deliverables=("entregable_principal",),
            acceptance_criteria=("cumple el objetivo", "sin errores criticos"),
            risks=("ambiguedad en requerimientos",),
            needs_clarification=len(mission.objective.split()) < 5,
            clarification_questions=("Puedes dar mas detalles?",) if len(mission.objective.split()) < 5 else (),
        )


MissionDirector = LLMMissionDirector
