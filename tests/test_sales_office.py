from igris_os.application.sales_office import SalesOffice


def test_sales_office_asks_for_missing_market_facts():
    plan = SalesOffice().build({"product": "IGRIS"})
    assert not plan.ready
    assert {question.key for question in plan.questions} >= {
        "audience", "channel", "price", "variable_cost", "fixed_cost"}


def test_sales_office_calculates_break_even_without_claiming_revenue():
    plan = SalesOffice().build({
        "product": "IGRIS", "audience": "pequeños equipos de desarrollo",
        "channel": "demostraciones directas", "price": "50",
        "variable_cost": "10", "fixed_cost": "400", "acquisition_budget": "80",
    })
    assert plan.ready
    assert plan.contribution_margin == 40
    assert plan.break_even_sales == 12
    assert "no es una previsión" in plan.assumptions[0]