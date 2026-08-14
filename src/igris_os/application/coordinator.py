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
class CoordinationResult:
    objective: str
    branch: str
    findings: tuple[SpecialistFinding, ...]
    review: SpecialistFinding
    complete: bool
    evidence_path: str = ""


class SpecialistCoordinator:
    """Consulta especialistas y exige una revisión independiente documentada."""

    ROLES = {
        MissionBranch.PROGRAMMING: ("arquitecto", "implementador", "ingeniero_de_pruebas"),
        MissionBranch.GAMES: ("diseñador_de_juego", "programador", "ingeniero_de_pruebas"),
        MissionBranch.ARTIFICIAL_INTELLIGENCE: ("investigador_ia", "ingeniero_ml", "evaluador"),
        MissionBranch.VIDEO: ("editor", "ingeniero_multimedia", "control_de_calidad"),
        MissionBranch.AUDIO: ("diseñador_sonoro", "ingeniero_audio", "control_de_calidad"),
        MissionBranch.IMAGE: ("director_visual", "especialista_imagen", "control_de_calidad"),
    }

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
        roles = self.ROLES.get(branch, ("analista", "ejecutor", "verificador"))
        findings = []
        for position, role in enumerate(roles, 1):
            if on_progress:
                on_progress(int(70 * position / (len(roles) + 1)),
                            f"Consultando especialista {position}/{len(roles)}")
            prompt = (
                f"Actua como {role}. Analiza esta mision sin inventar ejecuciones. "
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
            objective, branch.value, tuple(findings), review, complete)
        if self.evidence_root:
            path = self._record(result)
            result = CoordinationResult(
                objective, branch.value, tuple(findings), review, complete, str(path))
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
