import hashlib
import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Protocol


def normalize(text: str) -> str:
    value = unicodedata.normalize("NFKD", text.casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(re.findall(r"[a-z0-9]+", value))


def _tokens(text: str, ngram: int = 3) -> tuple[str, ...]:
    words = normalize(text).split()
    grams = set(words)
    for size in range(2, ngram + 1):
        for index in range(len(words) - size + 1):
            grams.add(" ".join(words[index:index + size]))
    return tuple(grams)


def _hash_index(gram: str, dimensions: int) -> int:
    return int.from_bytes(
        hashlib.blake2b(gram.encode("utf-8"), digest_size=8).digest(),
        "big") % dimensions


class LocalSemanticIndex:
    """Indice semantico local sin dependencias externas basado en hashing de
    n-gramas. Produce vectores esparsos deterministicos y mide similitud por
    coseno, complementando la busqueda textual exacta."""

    def __init__(self, dimensions: int = 512, ngram: int = 3) -> None:
        if dimensions <= 0:
            raise ValueError("Dimensiones invalidas")
        self.dimensions = dimensions
        self.ngram = ngram

    def vectorize(self, text: str) -> dict[int, float]:
        vector: dict[int, float] = {}
        for gram in _tokens(text, self.ngram):
            index = _hash_index(gram, self.dimensions)
            vector[index] = vector.get(index, 0.0) + 1.0
        return vector

    @staticmethod
    def _dot(left: dict[int, float], right: dict[int, float]) -> float:
        smaller, larger = (left, right) if len(left) <= len(right) else (right, left)
        return sum(value * larger.get(key, 0.0) for key, value in smaller.items())

    def score(self, query: str, text: str) -> float:
        query_vector = self.vectorize(query)
        text_vector = self.vectorize(text)
        query_norm = math.sqrt(sum(v * v for v in query_vector.values()))
        text_norm = math.sqrt(sum(v * v for v in text_vector.values()))
        if not query_norm or not text_norm:
            return 0.0
        return self._dot(query_vector, text_vector) / (query_norm * text_norm)


@dataclass(frozen=True, slots=True)
class SemanticMatch:
    path: str
    score: float
    lexical: int


class OllamaSemanticIndex:
    """Indice semantico con embeddings locales de Ollama. Cacifica los vectores
    por texto para no repetir llamadas a la API."""

    def __init__(self, client, model: str) -> None:
        self.client = client
        self.model = model
        self._cache: dict[str, tuple[float, ...]] = {}

    def _embed(self, text: str) -> tuple[float, ...] | None:
        if text in self._cache:
            return self._cache[text]
        ok, vectors = self.client.embed([text], self.model)
        if not ok or not vectors:
            return None
        vector = tuple(vectors[0])
        self._cache[text] = vector
        return vector

    def score(self, query: str, text: str) -> float:
        query_vector = self._embed(query)
        text_vector = self._embed(text)
        if not query_vector or not text_vector:
            return 0.0
        dot = sum(a * b for a, b in zip(query_vector, text_vector))
        query_norm = math.sqrt(sum(value * value for value in query_vector))
        text_norm = math.sqrt(sum(value * value for value in text_vector))
        if not query_norm or not text_norm:
            return 0.0
        return dot / (query_norm * text_norm)


class SemanticRetriever:
    """Recupera documentos por similitud semantica local mas apoyo lexico."""

    def __init__(self, index: LocalSemanticIndex | None = None,
                 lexical_weight: float = 1.0) -> None:
        self.index = index or LocalSemanticIndex()
        self.lexical_weight = lexical_weight

    @staticmethod
    def _terms(query: str) -> set[str]:
        ignored = {"este", "esta", "analiza", "proyecto", "repositorio",
                   "busca", "encuentra", "donde", "cuando", "quiere"}
        return {word for word in normalize(query).split()
                if len(word) >= 3 and word not in ignored}

    def retrieve(self, query: str,
                 documents: list[dict]) -> list[SemanticMatch]:
        terms = self._terms(query)
        results: list[SemanticMatch] = []
        for document in documents:
            text = document.get("text", "")
            lexical = sum(text.count(term) for term in terms)
            semantic = self.index.score(query, text)
            score = semantic + self.lexical_weight * lexical
            if score > 0:
                results.append(SemanticMatch(
                    str(document.get("path", "")), score, lexical))
        return sorted(results,
                      key=lambda item: (-item.score, item.path))[:12]
