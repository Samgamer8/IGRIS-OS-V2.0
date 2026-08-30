from igris_os.capabilities.creation import _project_lead, _sales_plan


def test_sales_capability_returns_auditable_plan_without_model():
    result = _sales_plan({"answers": {
        "product": "IGRIS OS",
        "audience": "equipos de desarrollo locales",
        "channel": "demostraciones directas",
        "price": "50",
        "variable_cost": "10",
        "fixed_cost": "400",
        "acquisition_budget": "80",
    }})

    assert result.ok
    plan = result.data["sales_plan"]
    assert plan["contribution_margin"] == 40
    assert plan["break_even_sales"] == 12
    assert plan["actions"]


def test_sales_capability_returns_questions_for_missing_facts():
    result = _sales_plan({"answers": {"product": "IGRIS"}})

    assert result.ok
    assert result.data["questions"]


def test_project_lead_blocks_unqualified_model_before_generation(tmp_path):
    workspace = tmp_path / "runtime" / "missions" / "mission"
    workspace.mkdir(parents=True)
    destination = tmp_path / "delivery"
    destination.mkdir()

    result = _project_lead({
        "workspace": str(workspace),
        "model": "qwen2.5-coder:7b",
        "objective": "Crea una aplicación de tareas",
        "answers": {
            "technology": "python", "delivery": "source",
            "destination": str(destination), "acceptance": "pruebas pasan",
        },
    })

    assert not result.ok
    assert result.code == "PROJECT_MODEL_NOT_QUALIFIED"