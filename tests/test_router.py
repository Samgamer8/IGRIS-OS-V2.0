from igris_os.ai import Budget, Difficulty, ModelRouter, RoutingMode


class FakeClient:
    def __init__(self, models):
        self._models = models

    def models(self):
        return self._models


def test_routes_code_by_difficulty():
    models = ("qwen2.5-coder:1.5b", "qwen2.5-coder:7b", "qwen2.5-coder:14b")
    router = ModelRouter(FakeClient(models))
    assert router.route(Difficulty.SIMPLE, code=True).model == "qwen2.5-coder:1.5b"
    assert router.route(Difficulty.NORMAL, code=True).model == "qwen2.5-coder:7b"
    assert router.route(Difficulty.COMPLEX, code=True).model == "qwen2.5-coder:14b"


def test_routes_general_by_difficulty():
    models = ("llama3.2:latest", "llama3.1:8b")
    router = ModelRouter(FakeClient(models))
    assert router.route(Difficulty.SIMPLE).model == "llama3.1:8b"
    assert router.route(Difficulty.NORMAL).model == "llama3.1:8b"


def test_general_simple_falls_back_when_big_model_missing():
    router = ModelRouter(FakeClient(("llama3.2:latest",)))
    assert router.route(Difficulty.SIMPLE).model == "llama3.2:latest"


def test_falls_back_to_family_when_tier_missing():
    models = ("qwen2.5-coder:7b",)
    router = ModelRouter(FakeClient(models))
    route = router.route(Difficulty.SIMPLE, code=True)
    assert route.model == "qwen2.5-coder:7b"


def test_no_models_yields_empty_route():
    router = ModelRouter(FakeClient(()))
    assert router.route(Difficulty.NORMAL).model == ""


def test_infer_difficulty_heuristics():
    assert ModelRouter.infer_difficulty("hola") is Difficulty.SIMPLE
    assert ModelRouter.infer_difficulty(
        "migra la arquitectura del sistema a produccion con seguridad") is Difficulty.COMPLEX
    assert ModelRouter.infer_difficulty(
        "crea un script que lea un archivo y produzca un informe con estadisticas basicas"
    ) is Difficulty.NORMAL


def test_max_savings_forces_small_model():
    models = ("qwen2.5-coder:1.5b", "qwen2.5-coder:7b", "qwen2.5-coder:14b")
    router = ModelRouter(FakeClient(models))
    route = router.route(Difficulty.COMPLEX, code=True,
                         mode=RoutingMode.MAX_SAVINGS)
    assert route.model == "qwen2.5-coder:1.5b"


def test_max_quality_forces_big_model():
    models = ("qwen2.5-coder:1.5b", "qwen2.5-coder:14b")
    router = ModelRouter(FakeClient(models))
    route = router.route(Difficulty.SIMPLE, code=True,
                         mode=RoutingMode.MAX_QUALITY)
    assert route.model == "qwen2.5-coder:14b"


def test_budget_prefers_smallest_model_that_fits():
    models = ("qwen2.5-coder:1.5b", "qwen2.5-coder:7b", "qwen2.5-coder:14b")
    router = ModelRouter(FakeClient(models))
    # El presupuesto baja al modelo mas barato que quepa en su ventana.
    route = router.route(Difficulty.NORMAL, code=True,
                         budget=Budget(max_tokens=2048))
    assert route.model == "qwen2.5-coder:1.5b"
    assert route.estimated_tokens > 0


def test_budget_upgrades_when_context_needs_more():
    # Sin qwen, llama3:latest tiene ventana 8192; con un presupuesto grande
    # debe elegir el modelo de mayor ventana disponible.
    router = ModelRouter(FakeClient(("llama3:latest", "llama3.1:8b")))
    route = router.route(Difficulty.COMPLEX, code=False,
                         budget=Budget(max_tokens=200000))
    assert route.model == "llama3.1:8b"


def test_budget_rejects_negative_tokens():
    import pytest
    with pytest.raises(ValueError):
        Budget(max_tokens=-1)
