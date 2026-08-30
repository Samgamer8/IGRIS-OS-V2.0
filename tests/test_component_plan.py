import pytest

from igris_os.programming.component_plan import PythonComponentPlanner


def test_component_plan_defines_dependencies_and_integration_test():
    plan = PythonComponentPlanner().plan("Crea un inventario local")

    assert [item.name for item in plan.components] == ["model", "service", "cli", "tests"]
    assert plan.components[1].depends_on == ("model",)
    assert "pytest" in plan.integration_test


def test_component_plan_requires_all_components():
    plan = PythonComponentPlanner().plan("Crea una aplicación")
    with pytest.raises(ValueError, match="Faltan componentes"):
        PythonComponentPlanner.validate_files(plan, {
            "model.py": "", "service.py": "", "main.py": "",
        })