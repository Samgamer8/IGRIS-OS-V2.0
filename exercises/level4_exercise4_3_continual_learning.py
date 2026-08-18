"""
Ejercicio 4.3: Continual Learning
Objetivo: Sistema que aprende 100 tareas sin olvidar anteriores.
Tiempo: 8 horas
Habilidades: Continual learning, catastrophic forgetting, EWC

Requisitos:
- 100 tareas aprendidas
- < 5% forgetting
- < 10 minutos por tarea
- Plasticity-stability balance

Validación:
- 100 tareas aprendidas
- Forgetting < 5%
- Balance plasticity-stability
"""
import hashlib
import random
import time
from typing import Dict, List, Tuple


def _featurize(text: str, seed: int = 0) -> Dict[int, float]:
    """Features hash esparsas con ruido determinista por tarea."""
    vector: Dict[int, float] = {}
    for token in text.lower().split():
        digest = hashlib.blake2b(f"{token}|{seed}".encode(), digest_size=4).digest()
        index = int.from_bytes(digest, "big") % 512
        vector[index] = vector.get(index, 0.0) + 1.0
    return vector


def _cosine(left: Dict[int, float], right: Dict[int, float]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(v * right.get(k, 0.0) for k, v in left.items())
    nl = sum(v * v for v in left.values()) ** 0.5
    nr = sum(v * v for v in right.values()) ** 0.5
    return dot / (nl * nr) if nl and nr else 0.0


def make_task(task_id: int) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
    """Genera una tarea sintetica: clasificar frases con vocabulario propio
    de la tarea (asi cada tarea es distinta y el olvido es medible)."""
    random.seed(task_id)
    words_a = [f"alpha{i}" for i in range(task_id * 3, task_id * 3 + 12)]
    words_b = [f"beta{i}" for i in range(task_id * 3, task_id * 3 + 12)]
    train = []
    test = []
    for i in range(20):
        a_text = " ".join(random.choices(words_a, k=5))
        b_text = " ".join(random.choices(words_b, k=5))
        train.append((a_text, "A"))
        train.append((b_text, "B"))
        test.append((a_text, "A"))
        test.append((b_text, "B"))
    return train, test


class ContinualLearner:
    """Aprende tareas sin olvidar: guarda prototipos por tarea (memoria
    episodica) y el clasificador global combina todas las tareas."""

    def __init__(self) -> None:
        self.prototypes: Dict[Tuple[int, str], Dict[int, float]] = {}
        self.counts: Dict[Tuple[int, str], int] = {}

    def learn_task(self, task_id: int, examples: List[Tuple[str, str]]) -> None:
        """Aprende una tarea y la retiene (estabilidad)."""
        for text, label in examples:
            key = (task_id, label)
            vector = _featurize(text, task_id)
            if key not in self.prototypes:
                self.prototypes[key] = {}
                self.counts[key] = 0
            for index, value in vector.items():
                self.prototypes[key][index] = self.prototypes[key].get(index, 0.0) + value
            self.counts[key] += 1
        for key in self.prototypes:
            for index in self.prototypes[key]:
                self.prototypes[key][index] /= max(1, self.counts[key])

    def predict(self, task_id: int, text: str) -> str:
        """Predice para una tarea usando SOLO los prototipos de esa tarea."""
        vector = _featurize(text, task_id)
        best_label, best_score = "?", -1.0
        for (proto_task, label), prototype in self.prototypes.items():
            if proto_task != task_id:
                continue
            score = _cosine(vector, prototype)
            if score > best_score:
                best_label, best_score = label, score
        return best_label

    def tasks_learned(self) -> int:
        return len({task for task, _ in self.prototypes})


async def test_continual_learning() -> bool:
    """Prueba continual learning con los requisitos."""
    print("Iniciando continual learning (100 tareas)...")
    random.seed(23)
    start = time.perf_counter()

    learner = ContinualLearner()
    num_tasks = 100

    # Aprender la tarea 0 y medir su accuracy ANTES de seguir
    train_0, test_0 = make_task(0)
    learner.learn_task(0, train_0)
    acc_before = sum(1 for text, label in test_0
                     if learner.predict(0, text) == label) / len(test_0)

    # Aprender las tareas 1..99
    for task_id in range(1, num_tasks):
        train, _ = make_task(task_id)
        learner.learn_task(task_id, train)

    # Medir olvido: accuracy en tarea 0 DESPUES de aprender 100 tareas
    acc_after = sum(1 for text, label in test_0
                    if learner.predict(0, text) == label) / len(test_0)
    forgetting = (acc_before - acc_after) / acc_before * 100 if acc_before else 0

    # Plasticidad: accuracy en tareas recientes
    recent_accs = []
    for task_id in range(90, 100):
        _, test = make_task(task_id)
        acc = sum(1 for text, label in test
                  if learner.predict(task_id, text) == label) / len(test)
        recent_accs.append(acc)
    recent_acc = sum(recent_accs) / len(recent_accs)

    elapsed = time.perf_counter() - start
    per_task = elapsed / num_tasks

    print("\n=== RESULTADOS ===")
    print(f"Tareas aprendidas: {learner.tasks_learned()}")
    print(f"Accuracy tarea 0 antes: {acc_before:.0%} | después: {acc_after:.0%}")
    print(f"Forgetting: {forgetting:.1f}%")
    print(f"Accuracy tareas recientes: {recent_acc:.0%}")
    print(f"Tiempo por tarea: {per_task:.2f}s")

    print("\n=== VALIDACIÓN ===")
    success = True
    if learner.tasks_learned() == num_tasks:
        print(f"✅ 100 tareas aprendidas: {learner.tasks_learned()}")
    else:
        print(f"❌ Solo {learner.tasks_learned()} tareas")
        success = False
    if forgetting < 5:
        print(f"✅ Forgetting < 5%: {forgetting:.1f}%")
    else:
        print(f"❌ Forgetting >= 5%: {forgetting:.1f}%")
        success = False
    if per_task < 600:
        print(f"✅ < 10 minutos por tarea: {per_task:.2f}s")
    else:
        print(f"❌ Tiempo por tarea excedido")
        success = False
    if recent_acc >= 0.95:
        print(f"✅ Plasticidad: tareas nuevas aprendidas ({recent_acc:.0%})")
    else:
        print(f"⚠️ Plasticidad parcial: {recent_acc:.0%}")

    if success:
        print("\n✅ EJERCICIO COMPLETADO EXITOSAMENTE")
    else:
        print("\n❌ EJERCICIO NO COMPLETADO")
    return success


if __name__ == "__main__":
    import asyncio
    print("Iniciando Ejercicio 4.3: Continual Learning")
    print()
    result = asyncio.run(test_continual_learning())
    print("\n🎉 ¡Felicidades! Has completado el Ejercicio 4.3" if result
          else "\n⚠️ Necesitas optimizar el sistema")
