import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from igris_os.ai import OllamaClient
from igris_os.domain import Mission, MissionBranch

from .director import MissionDirector


@dataclass(frozen=True, slots=True)
class SpecialistFinding:
    role: str
    model: str
    ok: bool
    text: str


@dataclass(frozen=True, slots=True)
class AgentExecutionStep:
    role: str
    phase: str
    purpose: str
    gate: str
    deliverable: str


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    objective: str
    branch: str
    steps: tuple[AgentExecutionStep, ...]
    controls: tuple[str, ...]
    risks: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CoordinationResult:
    objective: str
    branch: str
    findings: tuple[SpecialistFinding, ...]
    review: SpecialistFinding
    complete: bool
    evidence_path: str = ""
    execution_plan: ExecutionPlan | None = None


@dataclass(frozen=True, slots=True)
class SpecialistTeam:
    objective: str
    branch: str
    roles: tuple[str, ...]
    controls: tuple[str, ...]


class SpecialistCoordinator:
    """Consulta especialistas y exige una revisión independiente documentada."""

    ROLES = {
        MissionBranch.PROGRAMMING: (
            "mission_commander",
            "arquitecto",
            "implementador_senior",
            "ingeniero_de_pruebas",
            "seguridad_y_robustez",
            "revisor_critico",
        ),
        MissionBranch.GAMES: (
            "diseñador_de_juego",
            "programador",
            "ingeniero_de_pruebas",
        ),
        MissionBranch.ARTIFICIAL_INTELLIGENCE: (
            "investigador_ia",
            "ingeniero_ml",
            "evaluador",
        ),
        MissionBranch.VIDEO: ("editor", "ingeniero_multimedia", "control_de_calidad"),
        MissionBranch.AUDIO: ("diseñador_sonoro", "ingeniero_audio", "control_de_calidad"),
        MissionBranch.IMAGE: ("director_visual", "especialista_imagen", "control_de_calidad"),
    }

    PROGRAMMING_CONTROLS = (
        "alcance_confirmado",
        "arquitectura_validada",
        "codigo_verificado",
        "seguridad_revisada",
        "entrega_con_evidencia",
    )

    @classmethod
    def build_team(cls, objective: str, branch: MissionBranch | str | None = None) -> SpecialistTeam:
        normalized = MissionBranch.PROGRAMMING if branch is None else (
            MissionBranch(branch) if isinstance(branch, str) else branch)
        selected = cls.ROLES.get(normalized, ("analista", "ejecutor", "verificador"))
        controls = cls.PROGRAMMING_CONTROLS if normalized == MissionBranch.PROGRAMMING else (
            "revisión_independiente",
            "evidencia_documentada",
        )
        return SpecialistTeam(
            objective=objective.strip(),
            branch=normalized.value if hasattr(normalized, "value") else str(normalized),
            roles=tuple(selected),
            controls=tuple(controls),
        )

    @classmethod
    def build_execution_plan(cls, objective: str, branch: MissionBranch | str | None = None) -> ExecutionPlan:
        team = cls.build_team(objective, branch)
        steps = []
        for index, role in enumerate(team.roles, 1):
            if role == "mission_commander":
                phase = "Alcance"
                purpose = "Confirmar requisitos, riesgos y objetivos medibles."
                gate = "alcance_confirmado"
                deliverable = "contrato de misión con alcance y criterios"
            elif role == "arquitecto":
                phase = "Arquitectura"
                purpose = "Diseñar estructura, módulos y dependencias."
                gate = "arquitectura_validada"
                deliverable = "plan de arquitectura modular"
            elif role == "implementador_senior":
                phase = "Implementación"
                purpose = "Generar código y pruebas dentro del marco elegido."
                gate = "codigo_verificado"
                deliverable = "código y pruebas con evidencia de ejecución"
            elif role == "ingeniero_de_pruebas":
                phase = "Verificación"
                purpose = "Validar casos límite, regresiones y resultados esperados."
                gate = "codigo_verificado"
                deliverable = "matriz de pruebas ejecutadas"
            elif role == "seguridad_y_robustez":
                phase = "Seguridad"
                purpose = "Revisar entradas, permisos, fallos y riesgos operativos."
                gate = "seguridad_revisada"
                deliverable = "revisión de seguridad y robustez"
            elif role == "revisor_critico":
                phase = "Revisión"
                purpose = "Comprobar que la solución cumple el objetivo y la evidencia."
                gate = "entrega_con_evidencia"
                deliverable = "veredicto final con riesgos y mejoras"
            else:
                phase = "Ejecución"
                purpose = "Ejecutar la tarea específica del rol dentro del equipo."
                gate = "revisión_independiente"
                deliverable = "resultado del especialista"
            steps.append(AgentExecutionStep(
                role=role,
                phase=phase,
                purpose=purpose,
                gate=gate,
                deliverable=deliverable,
            ))
        risks = (
            "El alcance puede cambiar si no se validan los criterios de aceptación.",
            "Una solución que no pasa pruebas debe corregirse antes de entregarse.",
        )
        return ExecutionPlan(
            objective=objective.strip(),
            branch=team.branch,
            steps=tuple(steps),
            controls=tuple(team.controls),
            risks=risks,
        )

    def __init__(self, client: OllamaClient | None = None,
                 evidence_root: Path | None = None) -> None:
        self.client = client or OllamaClient()
        self.evidence_root = evidence_root
        self.director = MissionDirector()

    def coordinate(self, objective: str, model: str,
                   on_progress: Callable[[int, str], None] | None = None) -> CoordinationResult:
        if not objective.strip() or not model:
            raise ValueError("Objetivo y modelo son obligatorios")
        branch = self.director.plan(Mission(objective)).branch
        team = self.build_team(objective, branch)
        execution_plan = self.build_execution_plan(objective, branch)
        roles = team.roles
        findings = []
        for position, role in enumerate(roles, 1):
            if on_progress:
                on_progress(int(70 * position / (len(roles) + 1)),
                           f"Consultando especialista {position}/{len(roles)}")
            prompt = (
                f"Actua como {role}. Analiza esta mision sin inventar ejecuciones. "
                f"Controla estos gates: {', '.join(team.controls)}. "
                "Entrega decisiones, riesgos y pruebas necesarias. MISION: " + objective)
            reply = self.client.generate(prompt, model)
            findings.append(SpecialistFinding(
                role, model, reply.ok, reply.text if reply.ok else reply.error))
        transcript = "\n\n".join(
            f"{item.role}: {item.text}" for item in findings)
        if on_progress:
            on_progress(85, "Revisión cruzada independiente")
        review_prompt = (
            "Eres revisor independiente. Detecta contradicciones, carencias y "
            "afirmaciones sin evidencia. Da un veredicto condicionado a pruebas.\n" +
            transcript)
        reviewed = self.client.generate(review_prompt, model)
        review = SpecialistFinding(
            "revisor_independiente", model, reviewed.ok,
            reviewed.text if reviewed.ok else reviewed.error)
        complete = all(item.ok for item in findings) and review.ok
        if on_progress:
            on_progress(96, "Registrando evidencia")
        result = CoordinationResult(
            objective, branch.value, tuple(findings), review, complete,
            execution_plan=execution_plan)
        if self.evidence_root:
            path = self._record(result)
            result = CoordinationResult(
                objective, branch.value, tuple(findings), review, complete,
                str(path), execution_plan=execution_plan)
        return result

    def _record(self, result: CoordinationResult) -> Path:
        self.evidence_root.mkdir(parents=True, exist_ok=True)
        target = self.evidence_root / "specialist_coordination.json"
        payload = asdict(result)
        payload["evidence_path"] = str(target)
        temporary = target.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(target)
        return target
