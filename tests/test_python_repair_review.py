from pathlib import Path

from igris_os.application.project_development import StagedProject
from igris_os.application.project_testing import ProjectTestEvidence
from igris_os.application.python_repair_review import PythonRepairReviewAdapter


class FakeVerifier:
    def __init__(self, evidence: ProjectTestEvidence):
        self.evidence = evidence

    def verify(self, mission):
        return self.evidence


def _tested(root: Path, files=("app.py", "test_app.py")):
    developed = type("Developed", (), {
        "staging": StagedProject(root, files),
    })()
    return type("Tested", (), {"mission": developed})()


def test_repair_review_retests_without_claiming_code_changes(tmp_path):
    root = tmp_path / "staging"
    root.mkdir()
    for name in ("app.py", "test_app.py"):
        (root / name).write_text("pass\n", encoding="utf-8")
    verifier = FakeVerifier(ProjectTestEvidence(
        True, True, ("pytest", "-q"), "2 passed"))

    evidence = PythonRepairReviewAdapter(verifier).repair(_tested(root))

    assert evidence.attempted
    assert evidence.successful
    assert evidence.tests_passed
    assert evidence.changed_files == ("app.py", "test_app.py")
    assert "sin cambios" in evidence.summary


def test_repair_review_rejects_failed_retest(tmp_path):
    root = tmp_path / "staging"
    root.mkdir()
    for name in ("app.py", "test_app.py"):
        (root / name).write_text("pass\n", encoding="utf-8")
    verifier = FakeVerifier(ProjectTestEvidence(
        True, False, ("pytest", "-q"), "1 failed"))

    evidence = PythonRepairReviewAdapter(verifier).repair(_tested(root))

    assert not evidence.successful
    assert not evidence.tests_passed
    assert not evidence.changed_files


def test_repair_review_detects_missing_staged_artifact(tmp_path):
    root = tmp_path / "staging"
    root.mkdir()
    (root / "app.py").write_text("pass\n", encoding="utf-8")
    verifier = FakeVerifier(ProjectTestEvidence(
        True, True, ("pytest", "-q"), "1 passed"))

    evidence = PythonRepairReviewAdapter(verifier).repair(_tested(root))

    assert not evidence.successful
    assert "test_app.py" in evidence.summary
