from pathlib import Path

from igris_os.application.project_lead import ProjectLead
from igris_os.programming import DevelopmentResult


class FakeDeveloper:
    def __init__(self, client, workspace, model):
        self.workspace = workspace

    def develop(self, objective, *, confirmed):
        project = self.workspace / "projects" / "generated"
        project.mkdir(parents=True)
        (project / "main.py").write_text("print('ok')\n", encoding="utf-8")
        (project / "VERIFICATION.json").write_text("{}\n", encoding="utf-8")
        return DevelopmentResult(True, "Verificado", str(project), 1)


def test_project_lead_returns_questions_before_any_development(tmp_path):
    lead = ProjectLead(None, tmp_path / "workspace", "fake", FakeDeveloper)

    result = lead.execute("Crea una aplicacion de tareas", {})

    assert not result.ok
    assert result.project is None
    assert result.contract.questions


def test_project_lead_delivers_only_verified_python_project(tmp_path):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "delivery"
    destination.mkdir()
    lead = ProjectLead(None, workspace, "fake", FakeDeveloper)

    result = lead.execute("Crea una aplicacion de tareas", {
        "technology": "python",
        "delivery": "source",
        "destination": str(destination),
        "acceptance": "crear tareas; listar tareas; pruebas pasan",
    })

    assert result.ok
    assert result.project == destination / "Crea_una_aplicacion_de_tareas"
    assert (result.project / "VERIFICATION.json").is_file()


def test_project_lead_keeps_verified_project_in_staging_until_delivery(tmp_path):
    workspace = tmp_path / "workspace"
    destination = tmp_path / "delivery"
    destination.mkdir()
    lead = ProjectLead(None, workspace, "fake", FakeDeveloper)
    answers = {
        "technology": "python", "delivery": "source",
        "destination": str(destination), "acceptance": "pruebas pasan",
    }

    staged = lead.stage("Crea una aplicacion de tareas", answers)

    assert staged.ok
    assert staged.staged_project is not None
    assert not (destination / "Crea_una_aplicacion_de_tareas").exists()

    delivered = lead.deliver("Crea una aplicacion de tareas", answers,
                             staged.staged_project)
    assert delivered.ok
    assert delivered.project == destination / "Crea_una_aplicacion_de_tareas"


def test_project_lead_rejects_unsupported_technology(tmp_path):
    destination = tmp_path / "delivery"
    destination.mkdir()
    lead = ProjectLead(None, tmp_path / "workspace", "fake", FakeDeveloper)

    result = lead.execute("Crea un juego", {
        "technology": "godot",
        "delivery": "source",
        "destination": str(destination),
        "acceptance": "abre sin errores",
    })

    assert not result.ok
    assert "sin ejecutor verificado" in result.message