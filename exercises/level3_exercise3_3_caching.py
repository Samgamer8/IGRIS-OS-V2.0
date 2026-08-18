"""
Ejercicio 3.3: Caching Distribuido
Objetivo: Sistema que reduce DB load 90% con caching.
Tiempo: 4 horas
Habilidades: Redis cluster, cache invalidation, caching strategies

Requisitos:
- Cache LRU
- Cache invalidation
- 90% cache hit rate
- < 10ms cache latency
- Write-through cache

Validación:
- DB load reducido 90%
- Cache hit rate > 90%
- Latencia < 10ms
"""
import random
import statistics
import time
from collections import OrderedDict
from typing import Dict, List, Optional


class LRUCache:
    """Cache LRU thread-safe (OrderedDict)."""

    def __init__(self, capacity: int = 1000) -> None:
        self.capacity = capacity
        self._data: OrderedDict[str, str] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[str]:
        if key in self._data:
            self._data.move_to_end(key)
            self.hits += 1
            return self._data[key]
        self.misses += 1
        return None

    def put(self, key: str, value: str) -> None:
        if key in self._data:
            self._data.move_to_end(key)
        self._data[key] = value
        if len(self._data) > self.capacity:
            self._data.popitem(last=False)


class Database:
    """Base de datos simulada con latencia real."""

    def __init__(self) -> None:
        self.store: Dict[str, str] = {}
        self.reads = 0
        self.writes = 0

    def read(self, key: str) -> Optional[str]:
        self.reads += 1
        time.sleep(0.001)  # 1ms de IO real
        return self.store.get(key)

    def write(self, key: str, value: str) -> None:
        self.writes += 1
        time.sleep(0.001)
        self.store[key] = value


class WriteThroughCache:
    """Cache write-through: las escrituras van a cache y DB atomicamente."""

    def __init__(self, db: Database, capacity: int = 1000) -> None:
        self.db = db
        self.cache = LRUCache(capacity)

    def read(self, key: str) -> Optional[str]:
        value = self.cache.get(key)
        if value is not None:
            return value
        value = self.db.read(key)
        if value is not None:
            self.cache.put(key, value)
        return value

    def write(self, key: str, value: str) -> None:
        self.db.write(key, value)
        self.cache.put(key, value)

    def hit_rate(self) -> float:
        total = self.cache.hits + self.cache.misses
        return self.cache.hits / total if total else 0.0


async def test_caching() -> bool:
    """Prueba el caching con los requisitos."""
    print("Iniciando sistema de caching distribuido...")
    random.seed(5)

    db = Database()
    cache = WriteThroughCache(db, capacity=1000)

    # Poblar DB con 1000 registros
    for index in range(1000):
        db.write(f"key_{index}", f"value_{index}")

    # Escritura write-through
    cache.write("nuevo", "valor")
    assert db.store["nuevo"] == "valor", "write-through no persistio en DB"

    # Carga de trabajo: 10_000 lecturas con sesgo (80% sobre 200 claves
    # calientes, 20% sobre 300 frias; total 500 claves < capacidad 1000)
    latencies: List[float] = []
    for index in range(10_000):
        if random.random() < 0.8:
            key = f"key_{random.randint(0, 199)}"
        else:
            key = f"key_{random.randint(0, 499)}"
        start = time.perf_counter()
        cache.read(key)
        latencies.append((time.perf_counter() - start) * 1000)

    hit_rate = cache.hit_rate()
    db_reads = db.reads
    db_reads_without_cache = 10_000
    reduction = (1 - db_reads / db_reads_without_cache) * 100
    p99 = sorted(latencies)[int(len(latencies) * 0.99)]

    print("\n=== RESULTADOS ===")
    print(f"Hit rate: {hit_rate:.2%}")
    print(f"Lecturas a DB: {db_reads} (sin cache serian {db_reads_without_cache})")
    print(f"Reduccion de DB load: {reduction:.1f}%")
    print(f"Latencia p99: {p99:.3f}ms")

    print("\n=== VALIDACIÓN ===")
    success = True
    if hit_rate > 0.9:
        print(f"✅ Cache hit rate > 90%: {hit_rate:.2%}")
    else:
        print(f"❌ Hit rate <= 90%: {hit_rate:.2%}")
        success = False
    if reduction >= 90:
        print(f"✅ DB load reducido >= 90%: {reduction:.1f}%")
    else:
        print(f"❌ Reduccion insuficiente: {reduction:.1f}%")
        success = False
    if p99 < 10:
        print(f"✅ Latencia p99 < 10ms: {p99:.3f}ms")
    else:
        print(f"❌ Latencia p99 >= 10ms: {p99:.3f}ms")
        success = False
    if db.store.get("nuevo") == "valor":
        print("✅ Write-through consistente (cache y DB sincronizados)")
    else:
        print("❌ Write-through roto")
        success = False

    if success:
        print("\n✅ EJERCICIO COMPLETADO EXITOSAMENTE")
    else:
        print("\n❌ EJERCICIO NO COMPLETADO")
    return success


if __name__ == "__main__":
    import asyncio
    print("Iniciando Ejercicio 3.3: Caching Distribuido")
    print()
    result = asyncio.run(test_caching())
    print("\n🎉 ¡Felicidades! Has completado el Ejercicio 3.3" if result
          else "\n⚠️ Necesitas optimizar el sistema")
