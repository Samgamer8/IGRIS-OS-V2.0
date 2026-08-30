from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from igris_os.application.project_contract import ProjectContract, ProjectIntake
from igris_os.application.project_workspace import ProjectWorkspace
from igris_os.programming import PythonProjectDeveloper


@dataclass(frozen=True, slots=True)
class ProjectLeadResult:
    ok: bool
    message: str
    contract: ProjectContract
    project: Path | None = None
    staged_project: Path | None = None


class ProjectLead:
    """Coordina encargos de proyecto sin declarar una entrega sin evidencia."""

    def __init__(self, client, workspace: Path, model: str,
                 developer_factory: Callable = PythonProjectDeveloper) -> None:
        self.client = client
        self.workspace = workspace.resolve()
        self.model = model
        self.intake = ProjectIntake()
        self.project_workspace = ProjectWorkspace(self.workspace)
        self.developer_factory = developer_factory

    def prepare(self, objective: str,
                answers: Mapping[str, object] | None = None) -> ProjectContract:
        return self.intake.build(objective, answers)

    def execute(self, objective: str, answers: Mapping[str, object]) -> ProjectLeadResult:
        staged = self.stage(objective, answers)
        if not staged.ok or staged.staged_project is None:
            return staged
        return self.deliver(objective, answers, staged.staged_project)

    def stage(self, objective: str,
              answers: Mapping[str, object]) -> ProjectLeadResult:
        contract = self.prepare(objective, answers)
        if not contract.ready:
            return ProjectLeadResult(
                False, "Faltan decisiones de proyecto", contract)
        if contract.technology != "python":
            return ProjectLeadResult(
                False, "Tecnología sin ejecutor verificado: " + contract.technology,
                contract)
        developer = self.developer_factory(self.client, self.workspace, self.model)
        result = developer.develop(
            self._objective_with_contract(contract), confirmed=True)
        if not result.ok or not result.project:
            return ProjectLeadResult(False, result.message, contract)
        staged = Path(result.project).resolve()
        if not staged.is_relative_to(self.workspace):
            return ProjectLeadResult(
                False, "El staging quedó fuera del workspace", contract)
        if not (staged / "VERIFICATION.json").is_file():
            return ProjectLeadResult(
                False, "El desarrollador no aportó verificación", contract)
        self.project_workspace.create_project(
            contract.project_name,
            ("Implementar: " + item for item in contract.acceptance),
        )
        return ProjectLeadResult(
            True, "Proyecto preparado y verificado en staging", contract,
            staged_project=staged)

    def deliver(self, objective: str, answers: Mapping[str, object],
                staged_project: Path) -> ProjectLeadResult:
        contract = self.prepare(objective, answers)
        staged = Path(staged_project).resolve()
        if not contract.ready:
            return ProjectLeadResult(False, "Faltan decisiones de proyecto", contract)
        if not staged.is_dir() or not staged.is_relative_to(self.workspace):
            return ProjectLeadResult(
                False, "Staging no válido para entrega", contract)
        if not (staged / "VERIFICATION.json").is_file():
            return ProjectLeadResult(
                False, "El staging no aporta verificación", contract)
        delivered = self._deliver(staged, contract)
        if delivered is None:
            return ProjectLeadResult(
                False, "No se pudo entregar el proyecto sin sobrescribir archivos", contract)
        return ProjectLeadResult(
            True, "Proyecto entregado tras autorización", contract,
            project=delivered, staged_project=staged)

    @staticmethod
    def _objective_with_contract(contract: ProjectContract) -> str:
        acceptance = "\n".join("- " + item for item in contract.acceptance)
        constraints = "\n".join("- " + item for item in contract.constraints)
        return (
            contract.objective + "\n\nCRITERIOS DE ACEPTACION:\n" + acceptance +
            ("\nRESTRICCIONES:\n" + constraints if constraints else ""))

    @staticmethod
    def _deliver(staged: Path, contract: ProjectContract) -> Path | None:
        if contract.destination is None or not staged.is_dir():
            return None
        target = contract.destination / contract.project_name
        if target.exists():
            return None
        shutil.copytree(staged, target)
        return target