"""Jerarquia local: especialistas proponen, IGRIS ordena y aprueba."""

from __future__ import annotations

import hashlib
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, Sequence

from igris_os.application.approval import ApprovalAuthority


@dataclass(frozen=True, slots=True)
class WorkOrder:
    objective: str
    acceptance_criteria: tuple[str, ...]
    constraints: tuple[str, ...] = ()
    context: str = ""


@dataclass(frozen=True, slots=True)
class IntentContract:
    """Immutable result of IGRIS's single clarification round."""

    original_request: str
    objective: str
    acceptance_criteria: tuple[str, ...]
    constraints: tuple[str, ...] = ()
    clarification_questions: tuple[str, ...] = ()
    confirmed: bool = False

    @property
    def digest(self) -> str:
        payload = {
            "original_request": self.original_request,
            "objective": self.objective,
            "acceptance_criteria": self.acceptance_criteria,
            "constraints": self.constraints,
        }
        return hashlib.sha256(json.dumps(
            payload, ensure_ascii=False, sort_keys=True,
            separators=(",", ":")).encode("utf-8")).hexdigest()

    def to_work_order(self, *, context: str = "") -> WorkOrder:
        if not self.confirmed or self.clarification_questions:
            raise ValueError("la idea inicial aun no esta confirmada")
        return WorkOrder(
            self.objective,
            self.acceptance_criteria,
            self.constraints,
            context + "\nINTENT_DIGEST: " + self.digest)


class ClarificationGate:
    """Question once, without loops, before work enters production."""

    def __init__(self, max_questions: int = 3) -> None:
        if not 1 <= max_questions <= 5:
            raise ValueError("max_questions debe estar entre 1 y 5")
        self.max_questions = max_questions

    def prepare(
            self, original_request: str, objective: str,
            acceptance_criteria: Sequence[str],
            constraints: Sequence[str] = (),
            question_sets: Sequence[Sequence[str]] = ()) -> IntentContract:
        unique: list[str] = []
        seen: set[str] = set()
        for questions in question_sets:
            for question in questions:
                cleaned = " ".join(str(question).split()).strip()
                key = cleaned.casefold()
                if cleaned and key not in seen:
                    seen.add(key)
                    unique.append(cleaned)
                if len(unique) >= self.max_questions:
                    break
            if len(unique) >= self.max_questions:
                break
        return IntentContract(
            original_request.strip(),
            objective.strip(),
            tuple(str(item).strip() for item in acceptance_criteria
                  if str(item).strip()),
            tuple(str(item).strip() for item in constraints
                  if str(item).strip()),
            tuple(unique),
            not unique,
        )

    @staticmethod
    def confirm(
            contract: IntentContract,
            answers: Sequence[str]) -> IntentContract:
        if len(answers) != len(contract.clarification_questions):
            raise ValueError("faltan respuestas de la ronda de aclaracion")
        if any(not str(answer).strip() for answer in answers):
            raise ValueError("las respuestas no pueden estar vacias")
        answered_context = tuple(
            f"{question} => {' '.join(str(answer).split())}"
            for question, answer in zip(
                contract.clarification_questions, answers))
        return IntentContract(
            contract.original_request,
            contract.objective,
            contract.acceptance_criteria,
            contract.constraints + answered_context,
            (),
            True,
        )


@dataclass(frozen=True, slots=True)
class Specialist:
    name: str
    role: str
    execute: Callable[["WorkOrder"], str]


@dataclass(frozen=True, slots=True)
class Proposal:
    specialist: str
    role: str
    content: str
    ok: bool
    elapsed_seconds: float
    error: str = ""


@dataclass(frozen=True, slots=True)
class Evidence:
    passed: bool
    score: float
    checks: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Candidate:
    proposal: Proposal
    evidence: Evidence


@dataclass(frozen=True, slots=True)
class IgrisDecision:
    approved: bool
    winner: Candidate | None
    candidates: tuple[Candidate, ...]
    reason: str
    approval_binding: str = ""
    approval_token: str = ""


EvidenceEvaluator = Callable[[WorkOrder, Proposal], Evidence]
FinalApprover = Callable[[WorkOrder, Sequence[Candidate]], str | None]


class HierarchicalOrchestrator:
    """Run 2-5 specialists while reserving final approval for IGRIS."""

    def __init__(
            self, specialists: Sequence[Specialist],
            evaluator: EvidenceEvaluator,
            approver: FinalApprover | None = None,
            approval_authority: ApprovalAuthority | None = None,
            *, parallelism: int = 2) -> None:
        if not 2 <= parallelism <= 5:
            raise ValueError("parallelism debe estar entre 2 y 5")
        if not 2 <= len(specialists) <= 5:
            raise ValueError("se necesitan entre dos y cinco especialistas")
        names = [item.name for item in specialists]
        if len(names) != len(set(names)):
            raise ValueError("los nombres de especialistas deben ser unicos")
        self.specialists = tuple(specialists)
        self.evaluator = evaluator
        self.approver = approver or self._evidence_director
        self.approval_authority = approval_authority or ApprovalAuthority()
        self.parallelism = min(parallelism, len(self.specialists))

    def execute(self, order: WorkOrder) -> IgrisDecision:
        proposals = self._collect(order)
        candidates = tuple(
            Candidate(proposal, self._evaluate(order, proposal))
            for proposal in proposals)
        passing = tuple(item for item in candidates if item.evidence.passed)
        if not passing:
            return IgrisDecision(
                False, None, candidates,
                "IGRIS rechazo la ronda: ninguna propuesta supero las pruebas")
        winner_name = self.approver(order, passing)
        winner = next(
            (item for item in passing
             if item.proposal.specialist == winner_name), None)
        if winner is None:
            return IgrisDecision(
                False, None, candidates,
                "IGRIS rechazo la ronda o se eligio una propuesta sin evidencia")
        binding = self._approval_binding(order, winner)
        token = self.approval_authority.issue(
            binding, "apply_hierarchical_result")
        return IgrisDecision(
            True, winner, candidates,
            "IGRIS aprobo la propuesta con mejor evidencia verificable",
            binding, token)

    def _collect(self, order: WorkOrder) -> tuple[Proposal, ...]:
        results: list[Proposal] = []
        with ThreadPoolExecutor(
                max_workers=self.parallelism,
                thread_name_prefix="igris-specialist") as pool:
            futures = [
                pool.submit(self._run_specialist, item, order)
                for item in self.specialists
            ]
            for future in as_completed(futures):
                results.append(future.result())
        return tuple(sorted(results, key=lambda item: item.specialist))

    @staticmethod
    def _run_specialist(
            specialist: Specialist, order: WorkOrder) -> Proposal:
        started = time.monotonic()
        try:
            content = specialist.execute(order)
            if not isinstance(content, str) or not content.strip():
                raise ValueError("salida vacia")
            return Proposal(
                specialist.name, specialist.role, content.strip(), True,
                time.monotonic() - started)
        except Exception as exc:
            return Proposal(
                specialist.name, specialist.role, "", False,
                time.monotonic() - started, str(exc))

    def _evaluate(self, order: WorkOrder, proposal: Proposal) -> Evidence:
        if not proposal.ok:
            return Evidence(
                False, 0.0, diagnostics=(proposal.error or "fallo del agente",))
        try:
            evidence = self.evaluator(order, proposal)
        except Exception as exc:
            return Evidence(False, 0.0, diagnostics=(str(exc),))
        raw_score = float(evidence.score)
        if not math.isfinite(raw_score):
            return Evidence(
                False, 0.0, tuple(evidence.checks),
                tuple(evidence.diagnostics) + ("puntuacion no finita",))
        score = max(0.0, min(1.0, raw_score))
        return Evidence(
            bool(evidence.passed), score,
            tuple(evidence.checks), tuple(evidence.diagnostics))

    @staticmethod
    def _evidence_director(
            order: WorkOrder, candidates: Sequence[Candidate]) -> str | None:
        del order
        ranked = sorted(
            candidates,
            key=lambda item: (
                -item.evidence.score,
                item.proposal.elapsed_seconds,
                item.proposal.specialist,
            ))
        return ranked[0].proposal.specialist if ranked else None

    @staticmethod
    def _approval_binding(order: WorkOrder, winner: Candidate) -> str:
        payload = {
            "objective": order.objective,
            "acceptance_criteria": order.acceptance_criteria,
            "constraints": order.constraints,
            "specialist": winner.proposal.specialist,
            "content": winner.proposal.content,
            "passed": winner.evidence.passed,
            "score": winner.evidence.score,
            "checks": winner.evidence.checks,
            "diagnostics": winner.evidence.diagnostics,
        }
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True,
            separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
