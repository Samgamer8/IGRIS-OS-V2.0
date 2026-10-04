from __future__ import annotations

from igris_os.application.project_repair import ProjectRepairEvidence
from igris_os.application.project_testing import TestedProjectMission
from igris_os.application.python_testing import PythonPytestVerifierAdapter


class PythonRepairReviewAdapter:
    """Revalida el staging; no afirma modificaciones que no ha realizado."""

    def __init__(self, verifier: PythonPytestVerifierAdapter | None = None) -> None:
        self.verifier = verifier or PythonPytestVerifierAdapter()

    def repair(self, mission: TestedProjectMission) -> ProjectRepairEvidence:
        staging = mission.mission.staging
        root = staging.root.resolve()
        missing = tuple(
            relative for relative in staging.changed_files
            if not (root / relative).resolve().is_file()
        )
        if missing:
            return ProjectRepairEvidence(
                root, True, False, False, (),
                "Faltan artefactos del staging: " + ", ".join(missing))
        retest = self.verifier.verify(mission.mission)
        successful = retest.executed and retest.passed
        summary = (
            "Revisión sin cambios; retest aprobado: " + retest.summary
            if successful else "Revisión fallida: " + retest.summary
        )
        return ProjectRepairEvidence(
            root, True, successful, retest.passed,
            (), summary, staging.changed_files if successful else ())
