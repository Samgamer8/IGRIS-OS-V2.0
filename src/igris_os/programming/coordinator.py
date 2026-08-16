from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from igris_os.programming.specialists import (
    SpecialistRegistry,
    SpecialistRole,
)
from igris_os.programming.workshop import PythonWorkshop, RepairResult
from igris_os.utils.json_parser import StrictJSONParser


@dataclass(frozen=True, slots=True)
class ArchitecturePlan:
    modules: tuple[str, ...] = ()
    interfaces: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()
    acceptance: tuple[str, ...] = ()
    plan: str = ""


@dataclass(frozen=True, slots=True)
class CodeProposal:
    source: str
    tests: str
    explanation: str = ""
    sha256: str = ""


@dataclass(frozen=True, slots=True)
class ReviewVerdict:
    approved: bool
    score: float
    issues: tuple[str, ...] = ()
    suggestions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AutonomousResult:
    ok: bool
    message: str
    proposal: CodeProposal | None = None
    review: ReviewVerdict | None = None
    plan: ArchitecturePlan | None = None
    diagnostics: tuple[str, ...] = field(default_factory=tuple)
    attempts: int = 0


class AutonomousProgrammingCoordinator:
    def __init__(self, client, workspace: Path,
                 default_model: str = "qwen2.5-coder:7b",
                 review_model: str = "qwen2.5-coder:14b") -> None:
        self.client = client
        self.workspace = workspace.resolve()
        self.default_model = default_model
        self.review_model = review_model
        self.registry = SpecialistRegistry(client)
        self.max_attempts = 3
        self._plan_cache = {}
    @classmethod
    def _extract_json(cls, text: str) -> dict:
        return StrictJSONParser.extract(text)


    def execute(self, objective: str, *,
                confirmed: bool = False,
                context: str = "",
                language: str = "python",
                on_progress: Callable[[int, str], None] | None = None
                ) -> AutonomousResult:
        if not confirmed:
            return AutonomousResult(False, "Se necesita confirmacion")
        if not objective.strip():
            return AutonomousResult(False, "Falta el objetivo")

        plan = self._plan_cache.get(hash(objective))
        if plan is None:
            if on_progress:
                on_progress(5, "Fase 1: Arquitectura")
            plan = self._architect(objective, context, language)
            if plan:
                self._plan_cache[hash(objective)] = plan
        if not plan:
            return AutonomousResult(False, "Fallo en fase de arquitectura",
                                    diagnostics=("architect_failed",))

        if on_progress:
            on_progress(20, "Fase 2: Implementacion")
        proposal = self._program(objective, plan, context, language)
        if proposal is None:
            return AutonomousResult(False, "Fallo en fase de implementacion",
                                    plan=plan,
                                    diagnostics=("programmer_failed",))

        if on_progress:
            on_progress(50, "Fase 3: Verificacion con reparacion")
        verified = self._verify_and_repair(proposal, on_progress)
        if verified is None:
            return AutonomousResult(False, "No supero verificacion",
                                    plan=plan, proposal=proposal,
                                    attempts=self.max_attempts,
                                    diagnostics=("verification_failed",))

        if on_progress:
            on_progress(80, "Fase 4: Revision independiente")
        review = self._review(verified, objective, plan, language)
        if review is None:
            return AutonomousResult(False, "Fallo en revision",
                                    plan=plan, proposal=verified,
                                    attempts=self.max_attempts,
                                    diagnostics=("review_failed",))

        if on_progress:
            on_progress(100, "Completado")
        return AutonomousResult(True, "Mision completada",
                                proposal=verified, review=review, plan=plan)

    def execute_react(self, objective: str, *,
                      confirmed: bool = False,
                      context: str = "",
                      language: str = "python",
                      on_progress: Callable[[int, str], None] | None = None
                      ) -> AutonomousResult:
        if not confirmed:
            return AutonomousResult(False, "Se necesita confirmacion")
        if not objective.strip():
            return AutonomousResult(False, "Falta el objetivo")
        plan = self._plan_cache.get(hash(objective))
        if plan is None:
            if on_progress:
                on_progress(5, "ReAct: Pensamiento inicial")
            plan = self._architect(objective, context, language)
            if plan:
                self._plan_cache[hash(objective)] = plan
        if not plan:
            return AutonomousResult(False, "Fallo en arquitectura",
                                    diagnostics=("architect_failed",))
        current = None
        for attempt in range(1, self.max_attempts + 1):
            if on_progress:
                on_progress(10 + int(70 * attempt / self.max_attempts),
                            f"ReAct: Accion {attempt}")
            proposal = self._program(objective, plan, context, language)
            if proposal is None:
                return AutonomousResult(False, "Fallo en implementacion",
                                        plan=plan,
                                        diagnostics=("programmer_failed",))
            if on_progress:
                on_progress(10 + int(70 * attempt / self.max_attempts) + 5,
                            f"ReAct: Observacion {attempt}")
            verified = self._verify_and_repair(proposal, on_progress)
            if verified is not None:
                if on_progress:
                    on_progress(90, "ReAct: Revision final")
                review = self._review(verified, objective, plan, language)
                if review is not None:
                    return AutonomousResult(True, "Mision completada",
                                            proposal=verified, review=review,
                                            plan=plan, attempts=attempt)
        return AutonomousResult(False, "No supero verificacion",
                                plan=plan, attempts=self.max_attempts,
                                diagnostics=("verification_failed",))

    def _architect(self, objective: str, context: str, language: str) -> ArchitecturePlan | None:
        prompt = (
            "OBJETIVO:\n" + objective +
            ("\nCONTEXTO:\n" + context if context else "") +
            f"\nLENGUAJE: {language}\n\nGenera plan arquitectonico JSON."
        )
        output = self.registry.execute(SpecialistRole.ARCHITECT, prompt)
        if not output.ok:
            return None
        try:
            data = StrictJSONParser.extract(output.text)
            return ArchitecturePlan(
                modules=self._as_text(data.get("modules", [])),
                interfaces=self._as_text(data.get("interfaces", [])),
                risks=self._as_text(data.get("risks", [])),
                acceptance=self._as_text(data.get("acceptance", [])),
                plan=str(data.get("plan", "")),
            )
        except (ValueError, TypeError, KeyError):
            return None

    @staticmethod
    def _as_text(items) -> tuple[str, ...]:
        out = []
        for item in items:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                for key in ("name", "description", "title", "criterion", "text"):
                    if key in item:
                        out.append(str(item[key]))
                        break
                else:
                    out.append(str(item))
            else:
                out.append(str(item))
        return tuple(out)

    def _program(self, objective: str, plan: ArchitecturePlan,
                 context: str, language: str) -> CodeProposal | None:
        acceptance = "\n".join("- " + item for item in plan.acceptance)
        prompt = (
            "OBJETIVO:\n" + objective +
            f"\nLENGUAJE: {language}\n" +
            "\nPLAN ARQUITECTONICO:\n" + plan.plan +
            "\nMODULOS:\n" + "\n".join("- " + m for m in plan.modules) +
            "\nCRITERIOS DE ACEPTACION:\n" + acceptance +
            ("\nCONTEXTO:\n" + context if context else "") +
            "\n\nImplementa SOLO el modulo principal como UN SOLO ARCHIVO autocontenido. "
            "NO uses imports externos mas alla de biblioteca estandar. "
            "Devuelve SOLO JSON SIN MARKDOWN. "
            "El JSON debe ser valido. Usa \\n para nuevas lineas dentro de source y tests. "
            "Los tests DEBEN usar `from solution import ...` porque el archivo se llamara solution.py. "
            "Incluye una funcion `main()` ejecutable si el objetivo implica interfaz de consola. "
            "NO uses sys.exit() en funciones que se van a testear; usa excepciones. "
            "NO uses input() en funciones que se van a testear; recibe parametros. "
            "NO incluyas imports dentro del mismo archivo (no hagas `from solution import ...` dentro de solution). "
            "NO incluyas triple comillas sin escapar. "
            "NO uses clases ni POO. Implementa todo como funciones modulares independientes. "
            "Las funciones deben estar en el nivel superior del modulo para poder importarlas con `from solution import nombre_funcion`. "
            "NO defina clases con `class` ni metodos `__init__`. "
            'Formato: {"source":"codigo","tests":"tests","explanation":"cambios"}. '
            "VERIFICA que el codigo sea sintacticamente correcto."
        )
        output = self.registry.execute(SpecialistRole.PROGRAMMER, prompt)
        if not output.ok:
            return None
        try:
            data = StrictJSONParser.extract(output.text)
            source = str(data.get("source", "")).strip()
            tests = str(data.get("tests", "")).strip()
            if not source or not tests:
                return None
            return CodeProposal(
                source=source,
                tests=tests,
                explanation=str(data.get("explanation", "")),
                sha256="",
            )
        except (ValueError, TypeError, KeyError):
            return None

    def _verify_and_repair(self, proposal: CodeProposal,
                           on_progress: Callable[[int, str], None] | None
                           ) -> CodeProposal | None:
        staging = self.workspace / ".staging" / "autonomous"
        staging.mkdir(parents=True, exist_ok=True)
        workshop = PythonWorkshop(staging, repair_model=self.default_model)
        result: RepairResult = workshop.verify_with_repair(
            proposal.source, proposal.tests, self.client,
            max_attempts=self.max_attempts,
            on_progress=on_progress,
        )
        if not result.ok:
            return None
        return CodeProposal(
            source=result.source,
            tests=proposal.tests,
            explanation=proposal.explanation + " (reparado)",
            sha256="",
        )

    def _review(self, proposal: CodeProposal, objective: str,
                plan: ArchitecturePlan, language: str) -> ReviewVerdict | None:
        acceptance = "\n".join("- " + item for item in plan.acceptance)
        prompt = (
            "OBJETIVO:\n" + objective +
            f"\nLENGUAJE: {language}\n" +
            "\nPLAN:\n" + plan.plan +
            "\nACEPTACION:\n" + acceptance +
            "\n\nCODIGO ENTREGADO:\n" + proposal.source[:8000] +
            "\n\nTESTS:\n" + proposal.tests[:4000] +
            "\n\nRevisa y puntua. JSON."
        )
        output = self.registry.execute(SpecialistRole.REVIEWER, prompt)
        if not output.ok:
            return None
        try:
            data = StrictJSONParser.extract(output.text)
            score = float(data.get("score", 0.0))
            return ReviewVerdict(
                approved=bool(data.get("approved", False)) and score >= 0.7,
                score=score,
                issues=tuple(data.get("issues", [])),
                suggestions=tuple(data.get("suggestions", [])),
            )
        except (ValueError, TypeError, KeyError):
            return None
