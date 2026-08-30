import pytest

from igris_os.application.project_contract import ProjectIntake
from igris_os.application.project_office import ProjectOffice


def test_project_office_requires_complete_contract(tmp_path):
    contract = ProjectIntake().build("Crea una app")
    with pytest.raises(ValueError, match="preguntas"):
        ProjectOffice().plan(contract)


def test_project_office_produces_verifiable_phases(tmp_path):
    contract = ProjectIntake().build("Crea una app", {
        "technology": "python", "delivery": "source",
        "destination": str(tmp_path), "acceptance": "pruebas pasan",
    })
    plan = ProjectOffice().plan(contract)
    assert [phase.name for phase in plan.phases] == [
        "Alcance", "Implementación", "Verificación", "Entrega"]
    assert "VERIFICATION.json" in plan.phases[-1].acceptance_gate