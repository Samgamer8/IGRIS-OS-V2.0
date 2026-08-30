"""Progressive workflow-skill catalog for IGRIS.

The design adapts process-oriented, evidence-gated and progressive-disclosure
patterns described by https://github.com/addyosmani/agent-skills (MIT). The
implementation and contracts here are original to IGRIS OS.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Mapping, Sequence


class SkillPhase(str, Enum):
    DEFINE = "define"
    PLAN = "plan"
    BUILD = "build"
    VERIFY = "verify"
    REVIEW = "review"
    SHIP = "ship"


@dataclass(frozen=True, slots=True)
class SkillSummary:
    name: str
    description: str
    phase: SkillPhase
    triggers: tuple[str, ...]
    exclusions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SkillDefinition:
    summary: SkillSummary
    steps: tuple[str, ...]
    required_evidence: tuple[str, ...]
    red_flags: tuple[str, ...] = ()
    anti_rationalizations: tuple[tuple[str, str], ...] = ()
    references: tuple[str, ...] = ()

    def compact_instructions(self) -> str:
        steps = " | ".join(
            f"{index}. {step}"
            for index, step in enumerate(self.steps, start=1))
        evidence = ", ".join(self.required_evidence)
        return (
            f"SKILL {self.summary.name} [{self.summary.phase.value}]: "
            f"{steps}. REQUIRED EVIDENCE: {evidence}.")


@dataclass(frozen=True, slots=True)
class SkillGateResult:
    passed: bool
    missing_steps: tuple[str, ...] = ()
    missing_evidence: tuple[str, ...] = ()
    red_flags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RoutingEvalResult:
    passed: bool
    total: int
    correct: int
    failures: tuple[str, ...] = ()

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 1.0


SkillLoader = Callable[[], SkillDefinition]


class SkillCatalog:
    """Discover from small summaries and load only the selected workflows."""

    def __init__(
            self, summaries: Sequence[SkillSummary],
            loaders: Mapping[str, SkillLoader]) -> None:
        names = [item.name for item in summaries]
        if len(names) != len(set(names)):
            raise ValueError("skill names must be unique")
        if set(names) != set(loaders):
            raise ValueError("every skill summary needs exactly one loader")
        self._summaries = tuple(summaries)
        self._loaders = dict(loaders)
        self._loaded: dict[str, SkillDefinition] = {}

        for summary in self._summaries:
            if not summary.name.strip() or not summary.description.strip():
                raise ValueError("skill name and description are required")
            if not summary.triggers:
                raise ValueError(f"skill {summary.name!r} needs triggers")
            if any(not item.strip() for item in summary.triggers):
                raise ValueError(f"skill {summary.name!r} has an empty trigger")

    def discover(
            self, objective: str,
            phase: SkillPhase | None = None) -> tuple[SkillSummary, ...]:
        text = objective.casefold()
        ranked: list[tuple[int, str, SkillSummary]] = []
        for summary in self._summaries:
            if phase is not None and summary.phase != phase:
                continue
            if any(self._contains(text, item)
                   for item in summary.exclusions):
                continue
            score = sum(
                1 for item in summary.triggers
                if self._contains(text, item))
            if score:
                ranked.append((-score, summary.name, summary))
        return tuple(item[2] for item in sorted(ranked))

    def load(self, name: str) -> SkillDefinition:
        if name not in self._loaders:
            raise KeyError(name)
        if name not in self._loaded:
            definition = self._loaders[name]()
            if definition.summary.name != name:
                raise ValueError("loader returned the wrong skill")
            if definition.summary != next(
                    item for item in self._summaries if item.name == name):
                raise ValueError("loader changed registered skill metadata")
            if not definition.steps or not definition.required_evidence:
                raise ValueError("skill needs steps and required evidence")
            self._loaded[name] = definition
        return self._loaded[name]

    def evaluate_routing(
            self, cases: Sequence[tuple[str, str]],
            *, minimum_accuracy: float = 0.8) -> RoutingEvalResult:
        """Deterministically check that realistic prompts select their owner."""
        if not 0.0 <= minimum_accuracy <= 1.0:
            raise ValueError("minimum_accuracy must be between zero and one")
        failures: list[str] = []
        correct = 0
        for prompt, expected in cases:
            if expected not in self._loaders:
                raise ValueError(f"unknown expected skill: {expected}")
            ranked = self.discover(prompt)
            actual = ranked[0].name if ranked else "<none>"
            if actual == expected:
                correct += 1
            else:
                failures.append(
                    f"{prompt!r}: expected {expected!r}, got {actual!r}")
        total = len(cases)
        accuracy = correct / total if total else 1.0
        return RoutingEvalResult(
            accuracy >= minimum_accuracy, total, correct, tuple(failures))

    @property
    def loaded_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._loaded))

    @staticmethod
    def verify(
            skill: SkillDefinition,
            completed_steps: Sequence[str],
            evidence: Mapping[str, str],
            observations: Sequence[str] = ()) -> SkillGateResult:
        done = {item.casefold().strip() for item in completed_steps}
        missing_steps = tuple(
            step for step in skill.steps
            if step.casefold().strip() not in done)
        missing_evidence = tuple(
            item for item in skill.required_evidence
            if not str(evidence.get(item, "")).strip())
        observed = "\n".join(observations).casefold()
        red_flags = tuple(
            flag for flag in skill.red_flags
            if flag.casefold() in observed)
        return SkillGateResult(
            not missing_steps and not missing_evidence and not red_flags,
            missing_steps, missing_evidence, red_flags)

    @staticmethod
    def _contains(text: str, trigger: str) -> bool:
        return bool(re.search(
            r"(?<!\w)" + re.escape(trigger.casefold()) + r"(?!\w)",
            text))


class OrchestrationMode(str, Enum):
    DIRECT = "direct"
    PARALLEL_FAN_OUT = "parallel_fan_out"
    SEQUENTIAL_PIPELINE = "sequential_pipeline"
    RESEARCH_ISOLATION = "research_isolation"


class OrchestrationAdvisor:
    """Choose the cheapest safe pattern from task topology."""

    @staticmethod
    def choose(
            *, independent_tasks: int = 1,
            has_ordered_dependencies: bool = False,
            shared_mutable_state: bool = False,
            research_input_size: int = 0,
            expected_digest_size: int = 0) -> OrchestrationMode:
        if (research_input_size >= 20
                and 0 <= expected_digest_size < research_input_size):
            return OrchestrationMode.RESEARCH_ISOLATION
        if has_ordered_dependencies:
            return OrchestrationMode.SEQUENTIAL_PIPELINE
        if independent_tasks >= 2 and not shared_mutable_state:
            return OrchestrationMode.PARALLEL_FAN_OUT
        return OrchestrationMode.DIRECT


def build_engineering_catalog() -> SkillCatalog:
    summaries = (
        SkillSummary(
            "clarify-contract",
            "Clarifies an ambiguous order once and freezes acceptance.",
            SkillPhase.DEFINE,
            ("ambiguous", "clarify", "requirements", "question")),
        SkillSummary(
            "component-build",
            "Builds one isolated component against an explicit contract.",
            SkillPhase.BUILD,
            ("build", "implement", "component", "generate")),
        SkillSummary(
            "evidence-debug",
            "Repairs a reproduced failure from exact diagnostic evidence.",
            SkillPhase.VERIFY,
            ("error", "failed", "repair", "debug", "compile")),
        SkillSummary(
            "final-quality-gate",
            "Reviews assembled work and fails closed without evidence.",
            SkillPhase.REVIEW,
            ("review", "approve", "quality", "audit")),
    )

    def definition(
            summary: SkillSummary, steps: tuple[str, ...],
            evidence: tuple[str, ...],
            red_flags: tuple[str, ...]) -> SkillLoader:
        return lambda: SkillDefinition(
            summary, steps, evidence, red_flags,
            (
                ("It looks correct", "Run the required check."),
                ("Tests can come later", "No evidence means no approval."),
            ))

    by_name = {item.name: item for item in summaries}
    loaders = {
        "clarify-contract": definition(
            by_name["clarify-contract"],
            ("identify ambiguities", "ask one bounded round",
             "freeze acceptance contract"),
            ("intent_digest",), ("unanswered question",)),
        "component-build": definition(
            by_name["component-build"],
            ("load component contract", "build isolated candidate",
             "run component verifier"),
            ("candidate_digest", "verifier_output"),
            ("shared writable workspace", "placeholder")),
        "evidence-debug": definition(
            by_name["evidence-debug"],
            ("reproduce failure", "localize component",
             "repair smallest scope", "add regression guard"),
            ("reproduction", "diagnostic", "regression_test"),
            ("guessing", "unbounded retry")),
        "final-quality-gate": definition(
            by_name["final-quality-gate"],
            ("verify all department gates", "test assembled product",
             "compare original acceptance", "sign exact artifact"),
            ("department_evidence", "assembly_test", "artifact_digest"),
            ("self approval", "missing evidence")),
    }
    return SkillCatalog(summaries, loaders)
