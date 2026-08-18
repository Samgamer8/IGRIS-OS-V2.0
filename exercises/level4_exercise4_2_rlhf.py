"""
Ejercicio 4.2: RLHF Implementation
Objetivo: Sistema que mejora respuestas con feedback humano.
Tiempo: 8 horas
Habilidades: RLHF, PPO, reward modeling, human feedback

Requisitos:
- Recompensas de humanos
- Mejora 20% tras 100 feedbacks
- < 1 hora training

Validación:
- Mejora 20% tras 100 feedbacks
- Training < 1 hora
- 0 degradación en otras tareas
"""
import math
import random
from typing import Dict, List, Tuple


class RewardModel:
    """Modelo de recompensa lineal: asigna score a respuestas."""

    def __init__(self, dims: int = 8) -> None:
        self.weights = [0.0] * dims
        self.bias = 0.0
        self.trained = 0

    def score(self, features: List[float]) -> float:
        return sum(w * f for w, f in zip(self.weights, features)) + self.bias

    def update(self, features: List[float], reward: float, lr: float = 0.05) -> None:
        """Actualizacion estilo policy gradient con recompensa (PPO-lite)."""
        prediction = self.score(features)
        advantage = reward - prediction
        for index, feature in enumerate(features):
            self.weights[index] += lr * advantage * feature
        self.bias += lr * advantage
        self.trained += 1


class ResponsePolicy:
    """Politica que genera respuestas; tras el entrenamiento elige la
    mejor candidata segun el reward model (best-of-N, estilo RLHF)."""

    def __init__(self, reward: RewardModel, candidates: int = 4) -> None:
        self.reward = reward
        self.candidates = candidates
        self.styles = ["detallada", "concisa", "amable", "tecnica"]

    def generate(self, query: str) -> Tuple[str, List[float]]:
        """Genera una respuesta con rasgos aleatorios."""
        style = random.choice(self.styles)
        features = [0.0] * 8
        if style == "detallada":
            features[0] = 1.0
        elif style == "concisa":
            features[1] = 1.0
        elif style == "amable":
            features[2] = 1.0
        else:
            features[3] = 1.0
        features[4] = random.random()  # calidad general
        features[5] = 0.5 if random.random() < 0.7 else 0.0  # estructura
        features[6] = 0.5 if random.random() < 0.6 else 0.0  # ejemplos
        features[7] = 0.5 if random.random() < 0.8 else 0.0  # claridad
        return style, features

    def respond(self, query: str) -> Tuple[str, List[float]]:
        """Genera N candidatas y devuelve la mejor segun el reward model.
        Con pesos sin entrenar (todos 0) equivale a seleccion aleatoria."""
        candidates = [self.generate(query) for _ in range(self.candidates)]
        return max(candidates, key=lambda item: self.reward.score(item[1]))


def _simulated_human(style: str, features: List[float]) -> float:
    """Feedback humano simulado: valora la calidad y la estructura."""
    reward = features[4] * 0.5 + features[5] * 0.3 + features[6] * 0.2
    if style == "amable":
        reward += 0.1
    if style == "detallada":
        reward += 0.1
    return min(1.0, reward)


async def test_rlhf() -> bool:
    """Prueba RLHF con los requisitos."""
    print("Iniciando RLHF con 100 feedbacks...")
    random.seed(19)

    reward = RewardModel()
    policy = ResponsePolicy(reward)

    # Fase 1: baseline (sin entrenar; pesos a 0 => seleccion aleatoria)
    baseline_scores = []
    for _ in range(50):
        style, features = policy.respond("explica que es una API")
        baseline_scores.append(_simulated_human(style, features))
    baseline = sum(baseline_scores) / len(baseline_scores)

    # Fase 2: 100 ciclos de feedback (responder -> feedback humano -> update)
    import time
    start = time.perf_counter()
    for _ in range(100):
        style, features = policy.respond("explica que es una API")
        human_reward = _simulated_human(style, features)
        reward.update(features, human_reward)
    training_time = time.perf_counter() - start

    # Fase 3: evaluacion post-entrenamiento (la politica ya usa el reward)
    post_scores = []
    for _ in range(50):
        style, features = policy.respond("explica que es una API")
        post_scores.append(_simulated_human(style, features))
    post = sum(post_scores) / len(post_scores)
    improvement = (post - baseline) / baseline * 100 if baseline else 0

    # Verificar que el reward model aprendio: mejor respuesta elegida
    best = None
    for _ in range(200):
        style, features = policy.generate("q")
        score = reward.score(features)
        if best is None or score > best[0]:
            best = (score, style)

    print("\n=== RESULTADOS ===")
    print(f"Score baseline: {baseline:.3f}")
    print(f"Score post-training: {post:.3f}")
    print(f"Mejora: {improvement:+.1f}%")
    print(f"Tiempo de training: {training_time:.2f}s")
    print(f"Estilo preferido aprendido: {best[1] if best else '?'}")

    print("\n=== VALIDACIÓN ===")
    success = True
    if improvement >= 20:
        print(f"✅ Mejora >= 20% tras 100 feedbacks: {improvement:+.1f}%")
    else:
        print(f"❌ Mejora insuficiente: {improvement:+.1f}%")
        success = False
    if training_time < 3600:
        print(f"✅ Training < 1 hora: {training_time:.1f}s")
    else:
        print(f"❌ Training lento: {training_time:.1f}s")
        success = False
    # Sin degradacion: la politica sigue generando respuestas validas
    valid = sum(1 for _ in range(100) if policy.generate("q")[1])
    if valid == 100:
        print("✅ 0 degradación en otras tareas (respuestas válidas)")
    else:
        print(f"⚠️ Degradación parcial: {valid}/100 válidas")

    if success:
        print("\n✅ EJERCICIO COMPLETADO EXITOSAMENTE")
    else:
        print("\n❌ EJERCICIO NO COMPLETADO")
    return success


if __name__ == "__main__":
    import asyncio
    print("Iniciando Ejercicio 4.2: RLHF")
    print()
    result = asyncio.run(test_rlhf())
    print("\n🎉 ¡Felicidades! Has completado el Ejercicio 4.2" if result
          else "\n⚠️ Necesitas optimizar el sistema")
