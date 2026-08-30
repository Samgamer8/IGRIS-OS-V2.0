import json

from igris_os.evaluation import MultiFileApplicationQualifier, approved_models_for
from igris_os.programming import MultiFileDevelopmentResult


class PassingMultiFileDeveloper:
    def __init__(self, client, workspace, model):
        self.workspace = workspace

    def develop(self, objective, *, confirmed, attempts, componentized=False):
        project = self.workspace / ".staging" / "candidate"
        project.mkdir(parents=True)
        for name in ("app.py", "service.py", "test_service.py", "VERIFICATION.json"):
            (project / name).write_text("", encoding="utf-8")
        return MultiFileDevelopmentResult(True, "Verificado", project,
                                          ("app.py", "service.py", "test_service.py"))


def test_multifile_qualification_persists_specialty_approval(tmp_path):
    qualifier = MultiFileApplicationQualifier(
        None, "candidate", developer_factory=PassingMultiFileDeveloper)
    result = qualifier.write_report(tmp_path / "model_qualification_candidate_multifile.json")

    assert result.approved
    assert approved_models_for(tmp_path, "python_multifile_application") == ("candidate",)
    report = json.loads((tmp_path / "model_qualification_candidate_multifile.json").read_text())
    assert report["kind"] == "python_multifile_application"


def test_qualification_ignores_pytest_and_bytecode_artifacts(tmp_path):
    class CachedDeveloper(PassingMultiFileDeveloper):
        def develop(self, objective, *, confirmed, attempts, componentized=False):
            result = super().develop(objective, confirmed=confirmed, attempts=attempts,
                                     componentized=componentized)
            (result.project / ".pytest_cache").mkdir()
            (result.project / ".pytest_cache" / "nodeids").write_text("[]")
            (result.project / "__pycache__").mkdir()
            (result.project / "__pycache__" / "app.pyc").write_bytes(b"x")
            return result

    result = MultiFileApplicationQualifier(
        None, "candidate", developer_factory=CachedDeveloper).run()
    assert all(".pytest_cache" not in item.project_files for item in result.results)
    assert all("__pycache__" not in item.project_files for item in result.results)