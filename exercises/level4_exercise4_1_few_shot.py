"""
Ejercicio 4.1: Few-Shot Learning
Objetivo: Sistema que aprende nueva tarea con 5 ejemplos.
Tiempo: 6 horas
Habilidades: Few-shot learning, meta-learning, prompt engineering

Requisitos:
- Aprende nueva tarea con 5 ejemplos
- 80% accuracy
- < 1 minuto adaptación
- Generaliza a casos similares

Validación:
- Tarea aprende con 5 ejemplos
- Accuracy > 80%
- Adaptación < 1 minuto
"""
import hashlib
import random
import time
from typing import Dict, List, Tuple


def _features(text: str) -> Dict[int, float]:
    """Caracteristicas hash esparsas: palabras + trigramas de caracteres.
    Los n-gramas comparten morfologia entre frases parecidas (lo que permite
    generalizar con pocos ejemplos: 'encanta' y 'encantado' comparten gramas)."""
    vector: Dict[int, float] = {}
    lowered = text.lower()
    for token in lowered.split():
        digest = hashlib.blake2b(f"w:{token}".encode(), digest_size=4).digest()
        key = int.from_bytes(digest, "big") % 512
        vector[key] = vector.get(key, 0.0) + 1.0
    clean = "".join(c for c in lowered if c.isalnum() or c.isspace())
    for index in range(len(clean) - 2):
        gram = clean[index:index + 3]
        digest = hashlib.blake2b(f"c:{gram}".encode(), digest_size=4).digest()
        key = int.from_bytes(digest, "big") % 512
        vector[key] = vector.get(key, 0.0) + 0.5
    return vector


def _cosine(left: Dict[int, float], right: Dict[int, float]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(value * right.get(key, 0.0) for key, value in left.items())
    norm_l = sum(v * v for v in left.values()) ** 0.5
    norm_r = sum(v * v for v in right.values()) ** 0.5
    return dot / (norm_l * norm_r) if norm_l and norm_r else 0.0


class PrototypeClassifier:
    """Clasificador por prototipos: aprende con pocos ejemplos."""

    def __init__(self) -> None:
        self.prototypes: Dict[str, Dict[int, float]] = {}
        self.counts: Dict[str, int] = {}

    def fit(self, examples: List[Tuple[str, str]]) -> None:
        """Aprende una tarea con N ejemplos por clase (few-shot)."""
        for text, label in examples:
            vector = _features(text)
            if label not in self.prototypes:
                self.prototypes[label] = {}
                self.counts[label] = 0
            for key, value in vector.items():
                self.prototypes[label][key] = self.prototypes[label].get(key, 0.0) + value
            self.counts[label] += 1
        # Normalizar prototipos por numero de ejemplos
        for label in self.prototypes:
            for key in self.prototypes[label]:
                self.prototypes[label][key] /= self.counts[label]

    def predict(self, text: str) -> str:
        best_label, best_score = "?", -1.0
        vector = _features(text)
        for label, prototype in self.prototypes.items():
            score = _cosine(vector, prototype)
            if score > best_score:
                best_label, best_score = label, score
        return best_label


TASKS = {
    "sentimiento": {
        "train_pos": ["me encanta este producto", "es genial y funciona", "muy buena compra", "estoy feliz", "recomendable"],
        "train_neg": ["odio esto", "es terrible", "no funciona nada", "mala experiencia", "no lo compres"],
    },
}


async def test_few_shot() -> bool:
    """Prueba few-shot learning con los requisitos."""
    print("Iniciando few-shot learning (5 ejemplos)...")
    random.seed(17)
    start = time.perf_counter()

    # Datos de la tarea: sentimiento con 5 ejemplos por clase
    train_pos = TASKS["sentimiento"]["train_pos"]
    train_neg = TASKS["sentimiento"]["train_neg"]
    examples = [(text, "pos") for text in train_pos] + [(text, "neg") for text in train_neg]

    model = PrototypeClassifier()
    model.fit(examples)
    adaptation = time.perf_counter() - start

    # Test: frases NO vistas (generalización a casos similares)
    test_cases = [
        ("estoy muy feliz con el producto", "pos"),
        ("este producto es genial, me encanta", "pos"),
        ("compra muy buena, estoy contento", "pos"),
        ("lo recomiendo, es excelente", "pos"),
        ("que bien funciona, feliz con la compra", "pos"),
        ("esto funciona terrible, no lo compres", "neg"),
        ("producto muy malo, experiencia mala", "neg"),
        ("es una basura, no funciona", "neg"),
        ("no lo compres, es terrible", "neg"),
        ("mala compra, no funciona nada", "neg"),
    ]
    correct = sum(1 for text, label in test_cases if model.predict(text) == label)
    accuracy = correct / len(test_cases)

    print("\n=== RESULTADOS ===")
    print(f"Ejemplos de entrenamiento: {len(examples)} (5 por clase)")
    print(f"Adaptación: {adaptation:.2f}s")
    print(f"Accuracy en frases nuevas: {accuracy:.0%} ({correct}/{len(test_cases)})")

    print("\n=== VALIDACIÓN ===")
    success = True
    if len(examples) <= 10:
        print("✅ Tarea aprendida con 5 ejemplos por clase")
    else:
        print("❌ Usó más de 5 ejemplos por clase")
        success = False
    if accuracy > 0.8:
        print(f"✅ Accuracy > 80%: {accuracy:.0%}")
    else:
        print(f"❌ Accuracy <= 80%: {accuracy:.0%}")
        success = False
    if adaptation < 60:
        print(f"✅ Adaptación < 1 minuto: {adaptation:.2f}s")
    else:
        print(f"❌ Adaptación lenta: {adaptation:.2f}s")
        success = False

    if success:
        print("\n✅ EJERCICIO COMPLETADO EXITOSAMENTE")
    else:
        print("\n❌ EJERCICIO NO COMPLETADO")
    return success


if __name__ == "__main__":
    import asyncio
    print("Iniciando Ejercicio 4.1: Few-Shot Learning")
    print()
    result = asyncio.run(test_few_shot())
    print("\n🎉 ¡Felicidades! Has completado el Ejercicio 4.1" if result
          else "\n⚠️ Necesitas optimizar el sistema")
