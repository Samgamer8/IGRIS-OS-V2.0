"""Sequential local Director -> Programmer -> Validator workflow.

The roles share one Ollama server and run sequentially, so a small GPU does not
need to keep both models resident. Validation is an independent sandbox run.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from igris_os.ai import ModelReply, OllamaClient
from igris_os.delegation.claude_specialist import clean_env
from igris_os.delegation.contract import DelegatedResult, DelegatedTask
from igris_os.delegation.ollama_specialist import OllamaSpecialist
from igris_os.security.sandbox import JobObjectSandbox, SandboxRun


_PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "steps": {"type": "array", "items": {"type": "string"}},
        "acceptance": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "string"}},
        "needs_clarification": {"type": "boolean"},
    },
    "required": ["steps", "acceptance", "risks", "needs_clarification"],
    "additionalProperties": False,
}


@dataclass(frozen=True, slots=True)
class ProgrammingTeamResult:
    success: bool
    plan: dict[str, object]
    programmer: DelegatedResult | None
    validation: SandboxRun | None
    message: str


class LocalProgrammingTeam:
    """Runs planning, code generation and objective verification in order."""

    def __init__(
        self,
        client: OllamaClient | None = None,
        *,
        director_model: str = "deepseek-r1:8b",
        programmer_model: str = "qwen2.5-coder:7b",
        validator: JobObjectSandbox | None = None,
    ) -> None:
        self.client = client or OllamaClient()
        self.director_model = director_model
        self.programmer_model = programmer_model
        self.validator = validator or JobObjectSandbox(memory_limit_mb=1024)

    def run(self, task: DelegatedTask, *, max_attempts: int = 3) -> ProgrammingTeamResult:
        workspace = task.workspace.resolve()
        if not workspace.is_dir():
            return ProgrammingTeamResult(False, {}, None, None,
                                         "Workspace inexistente")
        if not task.verify_command:
            return ProgrammingTeamResult(False, {}, None, None,
                                         "El equipo exige un comando de verificación")

        prompt = (
            "Eres el Director de programación. Analiza el objetivo y devuelve "
            "un plan breve, criterios verificables, riesgos y si faltan datos. "
            "No inventes hechos del repositorio; limita el plan al encargo.\n"
            f"OBJETIVO: {task.objective}\n"
            f"CRITERIOS DEL USUARIO: {json.dumps(task.acceptance, ensure_ascii=False)}\n"
            f"RESTRICCIONES: {json.dumps(task.constraints, ensure_ascii=False)}"
        )
        reply: ModelReply = self.client.generate_json(
            prompt, self.director_model, _PLAN_SCHEMA)
        if not reply.ok:
            return ProgrammingTeamResult(False, {}, None, None,
                                         "Director no disponible: " + reply.error)
        try:
            plan = json.loads(reply.text)
            if (not isinstance(plan, dict)
                    or not isinstance(plan.get("steps"), list)
                    or not isinstance(plan.get("acceptance"), list)
                    or not isinstance(plan.get("risks"), list)
                    or not isinstance(plan.get("needs_clarification"), bool)
                    or not all(isinstance(x, str) and x.strip()
                               for key in ("steps", "acceptance", "risks")
                               for x in plan[key])
                    or not plan["steps"]
                    or not (plan["acceptance"] or task.acceptance)
                    or len(plan["steps"]) > 12
                    or len(plan["acceptance"]) > 12
                    or len(plan["risks"]) > 12):
                raise ValueError("Plan fuera del contrato")
        except (ValueError, TypeError, json.JSONDecodeError):
            return ProgrammingTeamResult(False, {}, None, None,
                                         "Director devolvió un plan inválido")
        if plan["needs_clarification"]:
            return ProgrammingTeamResult(False, plan, None, None,
                                         "El objetivo requiere aclaraciones")

        developer_task = DelegatedTask(
            objective=(task.objective + "\nPLAN APROBADO:\n- "
                       + "\n- ".join(plan["steps"])),
            workspace=workspace,
            acceptance=tuple(task.acceptance) + tuple(plan["acceptance"]),
            constraints=tuple(task.constraints) + (
                "Sigue el plan del Director; no amplíes el alcance.",),
            max_turns=task.max_turns,
            timeout_seconds=task.timeout_seconds,
            model=self.programmer_model,
            allowed_tools=task.allowed_tools,
            target_files=task.target_files,
            verify_command=task.verify_command,
            canaries=task.canaries,
        )
        programmer = OllamaSpecialist(
            model=self.programmer_model, client=self.client).run(
                developer_task, max_attempts=max_attempts)
        if not programmer.ok or programmer.verified is not True:
            return ProgrammingTeamResult(False, plan, programmer, None,
                                         "Programador no entregó cambios verificados")
        if programmer.containment_violations:
            return ProgrammingTeamResult(False, plan, programmer, None,
                                         "Se detectó una violación de contención")

        validation = self.validator.run(
            list(task.verify_command), timeout=task.timeout_seconds,
            cwd=str(workspace), env=clean_env())
        success = validation.returncode == 0 and not validation.timed_out
        return ProgrammingTeamResult(
            success, plan, programmer, validation,
            "Validador independiente aprobó" if success
            else "Validador independiente rechazó la entrega",
        )
