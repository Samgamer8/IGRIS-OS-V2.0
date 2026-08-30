from igris_os.application.project_contract import ProjectIntake


def test_incomplete_project_request_produces_only_required_questions():
    contract = ProjectIntake().build(
        "Quiero un juego de ajedrez con piezas medievales y reglas completas")

    assert not contract.ready
    assert [question.key for question in contract.questions] == [
        "technology", "delivery", "destination", "acceptance"]


def test_complete_project_request_becomes_executable_contract(tmp_path):
    contract = ProjectIntake().build("Crea un gestor de tareas", {
        "name": "Gestor de tareas",
        "technology": "python",
        "delivery": "source",
        "destination": str(tmp_path),
        "acceptance": "crear tareas; listar tareas; pruebas pasan",
        "constraints": "sin red; sin dependencias externas",
    })

    assert contract.ready
    assert contract.project_name == "Gestor_de_tareas"
    assert contract.destination == tmp_path.resolve()
    assert contract.acceptance == (
        "crear tareas", "listar tareas", "pruebas pasan")