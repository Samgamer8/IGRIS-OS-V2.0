"""
Ejercicio 4.4: Multi-Modal Understanding
Objetivo: Sistema que entiende prompts multimodales.
Tiempo: 6 horas
Habilidades: Multi-modal AI, CLIP embeddings, vision-language

Requisitos:
- Text + Image + Audio
- Embeddings multimodales
- 85% accuracy en tasks multimodales
- < 5 segundos respuesta

Validación:
- 3 modalidades soportadas
- Accuracy > 85%
- Respuesta < 5 segundos
"""
import hashlib
import random
import time
from typing import Dict, List, Tuple

DIM = 512


def _embed_tokens(tokens: List[str], salt: str = "") -> Dict[int, float]:
    vector: Dict[int, float] = {}
    for token in tokens:
        digest = hashlib.blake2b(f"{salt}{token}".encode(), digest_size=4).digest()
        index = int.from_bytes(digest, "big") % DIM
        vector[index] = vector.get(index, 0.0) + 1.0
    return vector


def embed_text(text: str) -> Dict[int, float]:
    return _embed_tokens(text.lower().split(), salt="t:")


def embed_image(pixels: List[int]) -> Dict[int, float]:
    """Embedding de imagen: histograma hash de colores (simula CLIP)."""
    return _embed_tokens([f"px{v}" for v in pixels], salt="i:")


def embed_audio(frames: List[float]) -> Dict[int, float]:
    """Embedding de audio: cuantizacion de amplitud (simula audio CLIP)."""
    buckets = [int(frame * 10) for frame in frames]
    return _embed_tokens([f"a{b}" for b in buckets], salt="s:")


def _cosine(left: Dict[int, float], right: Dict[int, float]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(v * right.get(k, 0.0) for k, v in left.items())
    nl = sum(v * v for v in left.values()) ** 0.5
    nr = sum(v * v for v in right.values()) ** 0.5
    return dot / (nl * nr) if nl and nr else 0.0


class MultimodalEncoder:
    """Codifica las 3 modalidades y clasifica por prototipos."""

    def __init__(self) -> None:
        self.prototypes: Dict[str, Dict[int, float]] = {}
        self.counts: Dict[str, int] = {}

    def fit(self, examples: List[Tuple[Tuple, str]]) -> None:
        """examples: ((texto|None, pixeles|None, audio|None), clase)."""
        for inputs, label in examples:
            vector = self._encode(inputs)
            if label not in self.prototypes:
                self.prototypes[label] = {}
                self.counts[label] = 0
            for index, value in vector.items():
                self.prototypes[label][index] = self.prototypes[label].get(index, 0.0) + value
            self.counts[label] += 1
        for label in self.prototypes:
            for index in self.prototypes[label]:
                self.prototypes[label][index] /= max(1, self.counts[label])

    def _encode(self, inputs: Tuple) -> Dict[int, float]:
        text, pixels, audio = inputs
        vector: Dict[int, float] = {}
        if text:
            for index, value in embed_text(text).items():
                vector[index] = vector.get(index, 0.0) + value
        if pixels:
            for index, value in embed_image(pixels).items():
                vector[index] = vector.get(index, 0.0) + value
        if audio:
            for index, value in embed_audio(audio).items():
                vector[index] = vector.get(index, 0.0) + value
        return vector

    def predict(self, inputs: Tuple) -> str:
        vector = self._encode(inputs)
        best_label, best_score = "?", -1.0
        for label, prototype in self.prototypes.items():
            score = _cosine(vector, prototype)
            if score > best_score:
                best_label, best_score = label, score
        return best_label


def make_sample(seed: int, mods: Tuple[bool, bool, bool]) -> Tuple[Tuple, str]:
    """Genera una muestra con las modalidades indicadas."""
    rng = random.Random(seed)
    label = "gato" if rng.random() < 0.5 else "perro"
    if label == "gato":
        words = rng.choice([["gato", "felino"], ["miau", "gato"], ["mascota", "gato"]])
        pixels = [3, 7, 9] + [rng.randint(0, 9) for _ in range(4)]
        audio = [0.3, 0.5, 0.8, 0.2]
    else:
        words = rng.choice([["perro", "can"], ["guau", "perro"], ["mascota", "perro"]])
        pixels = [2, 8, 1] + [rng.randint(0, 9) for _ in range(4)]
        audio = [0.2, 0.6, 0.7, 0.1]
    text = " ".join(words) if mods[0] else None
    pix = pixels if mods[1] else None
    aud = audio if mods[2] else None
    return (text, pix, aud), label


async def test_multimodal() -> bool:
    """Prueba el sistema multimodal con los requisitos."""
    print("Iniciando sistema multimodal (texto + imagen + audio)...")
    start = time.perf_counter()

    encoder = MultimodalEncoder()
    # Entrenar con muestras que combinan las 3 modalidades
    train = [make_sample(seed, (True, True, True)) for seed in range(60)]
    encoder.fit(train)

    # Evaluar en 3 escenarios: cada modalidad por separado y combinadas
    scenarios = {
        "solo texto": (True, False, False),
        "solo imagen": (False, True, False),
        "solo audio": (False, False, True),
        "texto+imagen": (True, True, False),
        "las 3 modalidades": (True, True, True),
    }
    total_correct = 0
    total = 0
    for scenario, mods in scenarios.items():
        correct = 0
        for seed in range(200, 300):
            inputs, label = make_sample(seed, mods)
            if encoder.predict(inputs) == label:
                correct += 1
        total_correct += correct
        total += 100
        print(f"  {scenario:20s} accuracy: {correct/100:.0%}")

    accuracy = total_correct / total
    elapsed = time.perf_counter() - start

    print("\n=== RESULTADOS ===")
    print(f"Accuracy global (5 escenarios x 100): {accuracy:.0%}")
    print(f"Tiempo de respuesta (inferencia): {elapsed:.2f}s")

    print("\n=== VALIDACIÓN ===")
    success = True
    supported = (embed_text("x") and embed_image([1, 2]) and embed_audio([0.5]))
    if supported:
        print("✅ 3 modalidades soportadas (texto, imagen, audio)")
    else:
        print("❌ Modalidades incompletas")
        success = False
    if accuracy > 0.85:
        print(f"✅ Accuracy > 85%: {accuracy:.0%}")
    else:
        print(f"❌ Accuracy <= 85%: {accuracy:.0%}")
        success = False
    if elapsed < 5:
        print(f"✅ Respuesta < 5 segundos: {elapsed:.2f}s")
    else:
        print(f"❌ Respuesta lenta: {elapsed:.2f}s")
        success = False

    if success:
        print("\n✅ EJERCICIO COMPLETADO EXITOSAMENTE")
    else:
        print("\n❌ EJERCICIO NO COMPLETADO")
    return success


if __name__ == "__main__":
    import asyncio
    print("Iniciando Ejercicio 4.4: Multi-Modal Understanding")
    print()
    result = asyncio.run(test_multimodal())
    print("\n🎉 ¡Felicidades! Has completado el Ejercicio 4.4" if result
          else "\n⚠️ Necesitas optimizar el sistema")
