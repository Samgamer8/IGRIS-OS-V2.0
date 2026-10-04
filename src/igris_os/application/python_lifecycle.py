from __future__ import annotations

from pathlib import Path

from igris_os.application.project_lifecycle import ProjectLifecycle
from igris_os.application.python_repair_review import PythonRepairReviewAdapter
from igris_os.application.python_staging import PythonMultiFileStagingAdapter
from igris_os.application.python_testing import PythonPytestVerifierAdapter, PythonRepairingVerifierAdapter


def build_python_project_lifecycle(client, workspace: Path, model: str, *,
                                   developer=None,
                                   verifier=None,
                                   repairer=None) -> ProjectLifecycle:
    """Compone el ciclo Python real con dependencias sustituibles en pruebas."""

    final_verifier = verifier or PythonPytestVerifierAdapter()
    testing = final_verifier
    if client is not None:
        testing = PythonRepairingVerifierAdapter(client, workspace, model, testing)
    staging = PythonMultiFileStagingAdapter(
        client, workspace, model, developer=developer)
    review = repairer or PythonRepairReviewAdapter(final_verifier)
    return ProjectLifecycle(workspace, staging, testing, review)
