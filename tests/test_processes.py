import pytest

from igris_os.application.processes import ProcessOrchestrator
from igris_os.application.project_contract import ProjectIntake


def test_process_orchestrator_builds_mission_pipeline(tmp_path):
    contract = ProjectIntake().build(
        "Crea una calculadora CLI en Python",
        {
            "technology": "python",
            "delivery": "source",
            "destination": str(tmp_path),
            "acceptance": "La app responde a operaciones básicas; hay pruebas automatizadas",
        },
    )

    process = ProcessOrchestrator().build("Crea una calculadora CLI en Python", contract)

    assert process.status == "planned"
    assert [stage.name for stage in process.stages] == [
        "Alcance",
        "Implementación",
        "Verificación",
        "Entrega",
    ]
    assert process.ooda["observe"].startswith("Se observa")
    assert "OODA" not in process.ooda["decide"]


def test_process_orchestrator_requires_objective():
    with pytest.raises(ValueError, match="vacío"):
        ProcessOrchestrator().build("   ")


def test_process_orchestrator_run_reports_progress(tmp_path):
    contract = ProjectIntake().build(
        "Crea un script de análisis",
        {
            "technology": "python",
            "delivery": "source",
            "destination": str(tmp_path),
            "acceptance": "Genera salida JSON y maneja errores",
        },
    )

    events = []
    process = ProcessOrchestrator().run(
        "Crea un script de análisis",
        contract,
        on_progress=lambda percent, message: events.append((percent, message)),
    )

    assert process.status == "ready"
    assert events
    assert any("Verificación" in message for _, message in events)
