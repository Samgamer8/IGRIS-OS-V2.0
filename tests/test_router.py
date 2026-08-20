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


def test_general_chat_prefers_small_model_over_26b():
    # Regresion: el fallback alfabetico elegia gemma4:26b (18 GB) para chat
    # general porque los modelos generales preferidos no estaban instalados,
    # dando ~41s hasta el primer token. Debe elegir el mas pequeno.
    models = ("gemma4:26b", "nomic-embed-text:latest", "qwen2.5-coder:7b")
    router = ModelRouter(FakeClient(models))
    route = router.route(Difficulty.SIMPLE, code=False)
    assert route.model == "qwen2.5-coder:7b"


def test_general_fallback_picks_smallest_non_embedding_model():
    # Cuando ningun modelo de GENERAL_TIERS esta instalado, el ultimo recurso
    # elige el modelo no-vision/no-embedding MAS PEQUENO (por tamano), nunca
    # el primero alfabetico ni un modelo de embeddings.
    models = ("gemma4:26b", "mistral:7b", "nomic-embed-text:latest")
    router = ModelRouter(FakeClient(models))
    route = router.route(Difficulty.NORMAL, code=False)
    assert route.model == "mistral:7b"


def test_general_never_picks_larger_than_smallest_available():
    # Invariante: para chat general, el modelo elegido nunca es mayor que el
    # mas pequeno de los modelos de texto instalados.
    for models in (
        ("gemma4:26b", "nomic-embed-text:latest", "qwen2.5-coder:7b"),
        ("gemma4:26b", "mistral:7b", "nomic-embed-text:latest"),
        ("llama3.1:70b", "llama3.1:8b", "nomic-embed-text:latest"),
    ):
        router = ModelRouter(FakeClient(models))
        chosen = router.route(Difficulty.NORMAL, code=False).model
        usable = [m for m in models if "embed" not in m]
        smallest = min(usable, key=ModelRouter._size_hint)
        assert chosen == smallest, f"{models}: eligio {chosen!r}, esperaba {smallest!r}"
