from __future__ import annotations

import re

from igris_os.application.project_development import DevelopedProjectMission
from igris_os.application.project_testing import ProjectTestEvidence
from igris_os.programming.engineering_workflow import EngineeringWorkflow


class PythonPytestVerifierAdapter:
    """Ejecuta pytest aislado y produce evidencia para el ciclo de vida."""

    COMMAND = ("python", "-m", "pytest", "-q")

    def __init__(self, workflow: EngineeringWorkflow | None = None,
                 timeout: int = 60) -> None:
        self.workflow = workflow or EngineeringWorkflow()
        self.timeout = min(120, max(1, int(timeout)))

    def verify(self, mission: DevelopedProjectMission) -> ProjectTestEvidence:
        root = mission.staging.root.resolve()
        tests = tuple(root.rglob("test_*.py")) + tuple(root.rglob("*_test.py"))
        if not tests:
            return ProjectTestEvidence(
                False, False, (), "El staging no contiene pruebas Python")
        result = self.workflow.run(
            root, self.COMMAND, confirmed=True, timeout=self.timeout)
        if not result.executed or result.run is None:
            return ProjectTestEvidence(
                False, False, self.COMMAND,
                result.reason or "pytest no fue ejecutado")
        passed = result.run.returncode == 0 and not result.run.timed_out
        output = (result.run.stdout + "\n" + result.run.stderr).strip()
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        result_lines = [
            line for line in lines
            if re.search(r"\b(?:passed|failed|error|errors)\b", line,
                         flags=re.IGNORECASE)
        ]
        if result_lines:
            summary = result_lines[-1]
        elif passed:
            summary = "pytest finalizado correctamente: passed"
        else:
            summary = "pytest finalizado: failed"
        summary = re.sub(r"\bPASSED\b", "passed", summary, flags=re.IGNORECASE)
        summary = re.sub(r"\bFAILED\b", "failed", summary, flags=re.IGNORECASE)
        if result.run.timed_out:
            summary = "pytest agotó el tiempo permitido"
        return ProjectTestEvidence(True, passed, self.COMMAND, summary)
