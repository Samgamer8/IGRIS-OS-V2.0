import math

from igris_os.retrieval import (
    LocalSemanticIndex,
    OllamaSemanticIndex,
    SemanticRetriever,
    normalize,
)


def test_normalize_strips_accents_and_symbols():
    assert normalize("Configuración, misión.") == "configuracion mision"


def test_local_index_is_deterministic():
    first = LocalSemanticIndex()
    second = LocalSemanticIndex()
    text = "IGRIS analiza archivos y ejecuta pruebas."
    assert first.vectorize(text) == second.vectorize(text)


def test_local_index_ranks_similar_text_higher():
    index = LocalSemanticIndex()
    query = "ejecutar pruebas de python"
    similar = index.score(query, "python pruebas ejecución automática")
    unrelated = index.score(query, "color rojo del coche")
    assert similar > unrelated


def test_retriever_combines_semantic_and_lexical():
    documents = [
        {"path": "a.py", "text": "def ejecuta_misiones(): return True"},
        {"path": "b.py", "text": "pintura de cuadros"},
    ]
    matches = SemanticRetriever().retrieve("ejecuta misiones", documents)
    assert matches[0].path == "a.py"
    assert matches[0].lexical > 0


def test_retriever_finds_semantic_without_lexical_match():
    documents = [
        {"path": "main.py", "text": "pruebas de ejecución automática"},
        {"path": "docs.md", "text": "instrucciones de instalacion del sistema"},
    ]
    matches = SemanticRetriever().retrieve("ejecucion automatica de pruebas", documents)
    assert matches
    assert matches[0].path == "main.py"
    assert matches[0].score > 0


def test_ollama_index_uses_embedded_vectors():
    class FakeClient:
        def embed(self, texts, model):
            return True, [[1.0, 0.0] for _ in texts]

    index = OllamaSemanticIndex(FakeClient(), "embed")
    assert index.score("algo", "otro") == 1.0
    assert index.score("nada", "vacio") > 0.0


def test_ollama_index_handles_failed_embeddings():
    class FailingClient:
        def embed(self, texts, model):
            return False, []

    index = OllamaSemanticIndex(FailingClient(), "embed")
    assert index.score("a", "b") == 0.0
