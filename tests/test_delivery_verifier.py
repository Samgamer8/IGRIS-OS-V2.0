from pathlib import Path

from igris_os.application import ApprovalAuthority
from igris_os.delivery import DeliveryVerifier
from igris_os.delivery.verifier import EXECUTE_CAPABILITY
from igris_os.security.sandbox import SandboxRun


class SuccessfulSandbox:
    def run(self, command, **kwargs):
        return SandboxRun(0, "1 passed", "", sandboxed=True)


def complete_python_project(root: Path) -> None:
    (root / "tests").mkdir(parents=True)
    (root / "README.md").write_text("# Real app", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        "[project]\nname='real-app'\nversion='1.0.0'\n", encoding="utf-8")
    (root / "tests" / "test_app.py").write_text(
        "def test_real(): assert True\n", encoding="utf-8")


def test_verification_requires_permission(tmp_path):
    complete_python_project(tmp_path)
    report = DeliveryVerifier(
        ApprovalAuthority(), SuccessfulSandbox()).verify_python(tmp_path, None)
    assert not report.ok
    assert "Permiso denegado" in report.message


def test_complete_software_is_executed_and_hashed(tmp_path):
    complete_python_project(tmp_path)
    authority = ApprovalAuthority()
    token = authority.issue(str(tmp_path.resolve()), EXECUTE_CAPABILITY)
    report = DeliveryVerifier(
        authority, SuccessfulSandbox()).verify_python(tmp_path, token)
    assert report.ok
    assert report.sandboxed
    assert "README.md" in report.files
    assert report.command[-2:] == ("pytest", "-q")


def test_incomplete_software_is_rejected_after_permission(tmp_path):
    authority = ApprovalAuthority()
    token = authority.issue(str(tmp_path.resolve()), EXECUTE_CAPABILITY)
    report = DeliveryVerifier(
        authority, SuccessfulSandbox()).verify_python(tmp_path, token)
    assert not report.ok
    assert "faltan" in report.message


def test_approval_is_not_reusable(tmp_path):
    complete_python_project(tmp_path)
    authority = ApprovalAuthority()
    token = authority.issue(str(tmp_path.resolve()), EXECUTE_CAPABILITY)
    verifier = DeliveryVerifier(authority, SuccessfulSandbox())
    assert verifier.verify_python(tmp_path, token).ok
    assert not verifier.verify_python(tmp_path, token).ok
