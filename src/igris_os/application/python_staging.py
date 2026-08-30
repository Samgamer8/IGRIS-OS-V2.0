from __future__ import annotations

from pathlib import Path

from igris_os.application.project_development import StagedProject
from igris_os.application.project_planning import PlannedProjectMission
from igris_os.programming.multi_file_developer import PythonMultiFileDeveloper


class PythonMultiFileStagingAdapter:
    """Conecta el desarrollador Python real con el contrato de staging."""

    def __init__(self, client, workspace: Path, model: str, *,
                 developer=None) -> None:
        self.workspace = Path(workspace).resolve()
        self.developer = developer or PythonMultiFileDeveloper(
            client, self.workspace, model)

    def stage(self, mission: PlannedProjectMission) -> StagedProject:
        contract = mission.mission.contract
        if contract.technology != "python":
            raise ValueError(
                "El adaptador Python no admite: " + contract.technology)
        objective = self._objective(mission)
        result = self.developer.develop(
            objective, confirmed=True, componentized=True)
        if not result.ok or result.project is None:
            diagnostics = "; ".join(result.diagnostics)
            raise ValueError(
                "El desarrollo Python no produjo staging verificado" +
                (": " + diagnostics if diagnostics else ""))
        root = Path(result.project).resolve()
        if not (root / "VERIFICATION.json").is_file():
            raise ValueError("El staging Python no aporta VERIFICATION.json")
        files = tuple(dict.fromkeys(result.files))
        if not files:
            raise ValueError("El staging Python no registra archivos")
        return StagedProject(root, files)

    @staticmethod
    def _objective(mission: PlannedProjectMission) -> str:
        contract = mission.mission.contract
        phases = "\n".join(
            f"- {phase.name}: {phase.outcome} [{phase.acceptance_gate}]"
            for phase in mission.plan.phases)
        acceptance = "\n".join("- " + item for item in contract.acceptance)
        constraints = "\n".join("- " + item for item in contract.constraints)
        return (
            contract.objective +
            "\n\nCRITERIOS DE ACEPTACIÓN:\n" + acceptance +
            "\n\nPLAN APROBADO:\n" + phases +
            ("\n\nRESTRICCIONES:\n" + constraints if constraints else "")
        )
