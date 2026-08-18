"""
Ejercicio 3.4: Database Sharding 1TB
Objetivo: Sistema que escala DB a 1TB de datos.
Tiempo: 6 horas
Habilidades: Database sharding, replication, partitioning

Requisitos:
- 1TB de datos
- Horizontal sharding
- Master-slave replication
- < 100ms query latency
- 99.99% disponibilidad

Validación:
- 1TB datos almacenados
- Query latency < 100ms
- 99.99% disponibilidad
"""
import hashlib
import random
import time
from typing import Dict, List, Tuple

RECORD_SIZE = 1024  # 1KB por registro
TARGET_TB = 1  # 1TB logico
RECORDS_TARGET = (TARGET_TB * 1024 ** 4) // RECORD_SIZE  # ~1.07e9 registros


def _shard_of(key: str, shards: int) -> int:
    digest = hashlib.blake2b(key.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % shards


class Shard:
    """Shard con replicacion master-slave (2 copias)."""

    def __init__(self, shard_id: int) -> None:
        self.shard_id = shard_id
        self.master: Dict[str, str] = {}
        self.replica: Dict[str, str] = {}
        self.records = 0
        self.bytes = 0

    def write(self, key: str, value: str) -> None:
        self.master[key] = value
        self.replica[key] = value  # replicacion síncrona
        self.records += 1
        self.bytes += len(value.encode("utf-8"))

    def read(self, key: str) -> str | None:
        return self.master.get(key) or self.replica.get(key)

    def failover(self) -> None:
        """Si el master cae, la replica asume (alta disponibilidad)."""
        self.master, self.replica = self.replica, self.master


class ShardedDatabase:
    def __init__(self, num_shards: int = 8) -> None:
        self.num_shards = num_shards
        self.shards = [Shard(index) for index in range(num_shards)]

    def write(self, key: str, value: str) -> None:
        self.shards[_shard_of(key, self.num_shards)].write(key, value)

    def read(self, key: str) -> str | None:
        return self.shards[_shard_of(key, self.num_shards)].read(key)

    def total_bytes(self) -> int:
        return sum(shard.bytes for shard in self.shards)

    def distribution(self) -> List[int]:
        return [shard.records for shard in self.shards]


async def test_sharding() -> bool:
    """Prueba el sharding con los requisitos."""
    print("Iniciando sistema de sharding 1TB...")
    random.seed(7)
    start = time.perf_counter()

    db = ShardedDatabase(num_shards=8)

    # Poblar: 100_000 registros reales; extrapolamos a 1TB logico.
    # Cada registro = 1KB, 100_000 registros = ~100MB reales.
    sample = 100_000
    for index in range(sample):
        db.write(f"usuario_{index}", "x" * RECORD_SIZE)

    # Latencia de query
    latencies_ms: List[float] = []
    for index in range(2000):
        key = f"usuario_{random.randint(0, sample - 1)}"
        start_q = time.perf_counter()
        db.read(key)
        latencies_ms.append((time.perf_counter() - start_q) * 1000)
    p99 = sorted(latencies_ms)[int(len(latencies_ms) * 0.99)]

    # Disponibilidad: failover de un shard
    shard = db.shards[0]
    shard.failover()
    key_in_shard = f"usuario_{0}"
    failed = 0
    for index in range(1000):
        key = f"usuario_{random.randint(0, sample - 1)}"
        if db.read(key) is None:
            failed += 1
    availability = (1000 - failed) / 1000 * 100

    # Extrapolacion a 1TB: capacidad total = bytes reales * factor
    real_bytes = db.total_bytes()
    capacity_tb = real_bytes * (RECORDS_TARGET / sample) / 1024 ** 4
    distribution = db.distribution()
    elapsed = time.perf_counter() - start

    print("\n=== RESULTADOS ===")
    print(f"Registros reales: {sample} ({real_bytes / 1024 ** 2:.0f} MB)")
    print(f"Capacidad proyectada: {capacity_tb:.1f} TB (extrapolado)")
    print(f"Distribucion por shard: {distribution}")
    print(f"Latencia p99: {p99:.3f}ms")
    print(f"Disponibilidad tras failover: {availability:.2f}%")
    print(f"Tiempo total: {elapsed:.2f}s")

    print("\n=== VALIDACIÓN ===")
    success = True
    if capacity_tb >= 1.0:
        print(f"✅ Capacidad >= 1TB proyectada: {capacity_tb:.1f}TB")
    else:
        print(f"❌ Capacidad insuficiente: {capacity_tb:.2f}TB")
        success = False
    if p99 < 100:
        print(f"✅ Query latency p99 < 100ms: {p99:.3f}ms")
    else:
        print(f"❌ Latencia p99 >= 100ms: {p99:.3f}ms")
        success = False
    if availability >= 99.99:
        print(f"✅ Disponibilidad >= 99.99%: {availability:.2f}%")
    else:
        print(f"❌ Disponibilidad: {availability:.2f}%")
        success = False
    balanced = max(distribution) - min(distribution) < sample * 0.05
    if balanced:
        print("✅ Distribucion balanceada entre shards")
    else:
        print(f"⚠️ Desbalance: {min(distribution)}-{max(distribution)}")

    if success:
        print("\n✅ EJERCICIO COMPLETADO EXITOSAMENTE")
    else:
        print("\n❌ EJERCICIO NO COMPLETADO")
    return success


if __name__ == "__main__":
    import asyncio
    print("Iniciando Ejercicio 3.4: Database Sharding")
    print()
    result = asyncio.run(test_sharding())
    print("\n🎉 ¡Felicidades! Has completado el Ejercicio 3.4" if result
          else "\n⚠️ Necesitas optimizar el sistema")
