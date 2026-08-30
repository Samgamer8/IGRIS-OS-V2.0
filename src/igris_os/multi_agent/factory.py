"""Factory-style orchestration between IGRIS input and final approval."""

from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from igris_os.application.approval import ApprovalAuthority
from igris_os.multi_agent.hierarchy import (
    Candidate,
    Evidence,
    HierarchicalOrchestrator,
    IgrisDecision,
    IntentContract,
    Proposal,
    Specialist,
    WorkOrder,
)


@dataclass(frozen=True, slots=True)
class Department:
    name: str
    specialists: tuple[Specialist, ...]
    evaluator: Callable[[WorkOrder, Proposal], Evidence]
    dependencies: tuple[str, ...] = ()
    parallelism: int = 2


@dataclass(frozen=True, slots=True)
class DepartmentResult:
    name: str
    decision: IgrisDecision


@dataclass(frozen=True, slots=True)
class FactoryResult:
    approved: bool
    assembled: str
    departments: tuple[DepartmentResult, ...]
    reason: str
    approval_binding: str = ""
    approval_token: str = ""


Assembler = Callable[[IntentContract, Mapping[str, Candidate]], str]
AssemblyEvaluator = Callable[[IntentContract, str], Evidence]


class FactoryOrchestrator:
    """Run dependency-aware departments; only IGRIS approves assembly."""

    def __init__(
            self, departments: Sequence[Department],
            assembler: Assembler,
            assembly_evaluator: AssemblyEvaluator,
            approval_authority: ApprovalAuthority | None = None,
            *, max_active_departments: int = 2) -> None:
        if not 1 <= max_active_departments <= 5:
            raise ValueError("max_active_departments debe estar entre 1 y 5")
        if not departments:
            raise ValueError("la fabrica necesita departamentos")
        names = [item.name for item in departments]
        if len(names) != len(set(names)):
            raise ValueError("los departamentos deben tener nombres unicos")
        known = set(names)
        for department in departments:
            if not 2 <= len(department.specialists) <= 5:
                raise ValueError(
                    department.name + " necesita entre 2 y 5 especialistas")
            unknown = set(department.dependencies) - known
            if unknown:
                raise ValueError(
                    department.name + " depende de departamentos desconocidos")
        self.departments = tuple(departments)
        self.assembler = assembler
        self.assembly_evaluator = assembly_evaluator
        self.approval_authority = approval_authority or ApprovalAuthority()
        self.max_active_departments = max_active_departments
        self._validate_acyclic()

    def execute(self, contract: IntentContract) -> FactoryResult:
        if not contract.confirmed or contract.clarification_questions:
            return FactoryResult(
                False, "", (), "IGRIS no libero la orden inicial")
        pending = {item.name: item for item in self.departments}
        completed: dict[str, DepartmentResult] = {}
        winners: dict[str, Candidate] = {}
        while pending:
            ready = [
                item for item in pending.values()
                if set(item.dependencies) <= set(completed)]
            if not ready:
                return FactoryResult(
                    False, "", tuple(completed.values()),
                    "la fabrica no puede resolver sus dependencias")
            wave = ready[:self.max_active_departments]
            with ThreadPoolExecutor(
                    max_workers=len(wave),
                    thread_name_prefix="igris-department") as pool:
                futures = {
                    pool.submit(
                        self._run_department, item, contract, winners): item
                    for item in wave
                }
                for future in as_completed(futures):
                    result = future.result()
                    completed[result.name] = result
                    pending.pop(result.name)
                    if (not result.decision.approved
                            or result.decision.winner is None):
                        return FactoryResult(
                            False, "", tuple(completed.values()),
                            "departamento rechazado: " + result.name)
                    winners[result.name] = result.decision.winner
        try:
            assembled = self.assembler(contract, winners)
            evidence = self.assembly_evaluator(contract, assembled)
        except Exception as exc:
            return FactoryResult(
                False, "", tuple(completed.values()),
                "fallo de ensamblaje: " + str(exc))
        if not evidence.passed:
            return FactoryResult(
                False, assembled, tuple(completed.values()),
                "IGRIS rechazo el ensamblaje final")
        binding = self._binding(contract, winners, assembled, evidence)
        token = self.approval_authority.issue(
            binding, "deliver_factory_result")
        return FactoryResult(
            True, assembled, tuple(completed.values()),
            "IGRIS aprobo y firmo el producto ensamblado",
            binding, token)

    @staticmethod
    def _run_department(
            department: Department, contract: IntentContract,
            winners: Mapping[str, Candidate]) -> DepartmentResult:
        dependency_context = "\n".join(
            name + ": " + winners[name].proposal.content
            for name in department.dependencies)
        order = WorkOrder(
            objective=contract.objective + "\nDEPARTMENT: " + department.name,
            acceptance_criteria=contract.acceptance_criteria,
            constraints=contract.constraints,
            context=(
                "INTENT_DIGEST: " + contract.digest +
                ("\nAPPROVED INPUTS:\n" + dependency_context
                 if dependency_context else "")))
        decision = HierarchicalOrchestrator(
            department.specialists,
            department.evaluator,
            parallelism=department.parallelism,
        ).execute(order)
        return DepartmentResult(department.name, decision)

    def _validate_acyclic(self) -> None:
        pending = {
            item.name: set(item.dependencies)
            for item in self.departments}
        resolved: set[str] = set()
        while pending:
            ready = [
                name for name, dependencies in pending.items()
                if dependencies <= resolved]
            if not ready:
                raise ValueError("dependencias ciclicas entre departamentos")
            for name in ready:
                resolved.add(name)
                pending.pop(name)

    @staticmethod
    def _binding(
            contract: IntentContract, winners: Mapping[str, Candidate],
            assembled: str, evidence: Evidence) -> str:
        payload = {
            "intent_digest": contract.digest,
            "departments": {
                name: {
                    "specialist": candidate.proposal.specialist,
                    "content": candidate.proposal.content,
                    "checks": candidate.evidence.checks,
                    "score": candidate.evidence.score,
                }
                for name, candidate in sorted(winners.items())
            },
            "assembled": assembled,
            "assembly_checks": evidence.checks,
            "assembly_score": evidence.score,
        }
        return hashlib.sha256(json.dumps(
            payload, ensure_ascii=False, sort_keys=True,
            separators=(",", ":")).encode("utf-8")).hexdigest()

