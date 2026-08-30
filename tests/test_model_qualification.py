import json

from igris_os.evaluation.model_qualification import (
    ProgrammingModelQualifier, approved_models, is_model_approved,
)
from igris_os.programming import DevelopmentResult


class PassingDeveloper:
    def __init__(self, client, workspace, model):
        self.workspace = workspace

    def develop(self, objective, *, confirmed, attempts):
        project = self.workspace / "projects" / "candidate"
        project.mkdir(parents=True)
        (project / "main.py").write_text("value = 1\n", encoding="utf-8")
        (project / "test_main.py").write_text("def test_ok(): pass\n", encoding="utf-8")
        (project / "VERIFICATION.json").write_text("{}\n", encoding="utf-8")
        return DevelopmentResult(True, "Proyecto verificado", str(project), 1)


class FailingDeveloper:
    def __init__(self, client, workspace, model):
        pass

    def develop(self, objective, *, confirmed, attempts):
        return DevelopmentResult(False, "Sintaxis inválida")


def test_qualifier_approves_only_projects_with_verification(tmp_path):
    qualifier = ProgrammingModelQualifier(
        None, "candidate", developer_factory=PassingDeveloper)
    result = qualifier.write_report(tmp_path / "qualification.json")

    assert result.approved
    assert all(item.passed for item in result.results)
    report = json.loads((tmp_path / "qualification.json").read_text(encoding="utf-8"))
    assert report["approved"] is True


def test_qualifier_rejects_model_when_a_case_fails():
    qualifier = ProgrammingModelQualifier(
        None, "candidate", developer_factory=FailingDeveloper)
    result = qualifier.run()

    assert not result.approved
    assert not any(item.passed for item in result.results)


def test_model_approval_requires_persisted_approved_report(tmp_path):
    rejected = tmp_path / "model_qualification_rejected.json"
    rejected.write_text(json.dumps({"model": "candidate", "approved": False}), encoding="utf-8")
    assert not is_model_approved(tmp_path, "candidate")

    approved = tmp_path / "model_qualification_approved.json"
    approved.write_text(json.dumps({"model": "candidate", "approved": True}), encoding="utf-8")
    assert is_model_approved(tmp_path, "candidate")
    assert approved_models(tmp_path) == ("candidate",)