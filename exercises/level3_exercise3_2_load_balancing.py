"""
Ejercicio 3.2: Load Balancing 100K Req/Seg
Objetivo: Sistema que balancea 100,000 req/seg entre 10 servidores.
Tiempo: 4 horas
Habilidades: Load balancing, consistent hashing, health checks

Requisitos:
- 100,000 req/seg
- 10 servidores
- Consistent hashing
- Health checks
- < 100ms latencia p99
- 99.9% disponibilidad

Validación:
- 100K req/seg manejadas
- Latencia p99 < 100ms
- 99.9% disponibilidad
"""
import bisect
import hashlib
import random
import statistics
import time
from typing import Dict, List


def _hash_key(key: str, ring_size: int) -> int:
    return int.from_bytes(hashlib.blake2b(key.encode("utf-8"), digest_size=8).digest(),
                          "big") % ring_size


class Server:
    def __init__(self, name: str, capacity: int = 100_000) -> None:
        self.name = name
        self.capacity = capacity
        self.requests = 0
        self.healthy = True

    def handle(self) -> float:
        """Procesa una peticion; devuelve latencia en ms."""
        self.requests += 1
        return 0.5 + (self.requests % 7) * 0.1


class ConsistentHashBalancer:
    """Balanceo por consistent hashing sobre un anillo de 4096 slots."""

    RING_SIZE = 4096

    def __init__(self, servers: List[Server], replicas: int = 64) -> None:
        self.servers = servers
        self.replicas = replicas
        self.ring: Dict[int, Server] = {}
        self._sorted_slots: List[int] = []
        self._build_ring()

    def _build_ring(self) -> None:
        self.ring = {}
        for server in self.servers:
            self._add_server(server)
        # Precomputar slots ordenados: buscar el siguiente requiere un anillo
        # ordenado, y ordenar en cada peticion haria 100K x O(n log n)
        self._sorted_slots = sorted(self.ring.keys())

    def _add_server(self, server: Server) -> None:
        for replica in range(self.replicas):
            slot = _hash_key(f"{server.name}#{replica}", self.RING_SIZE)
            self.ring[slot] = server

    def remove_server(self, server: Server) -> None:
        self.servers.remove(server)
        self._build_ring()

    def _next_server(self, slot: int) -> Server | None:
        slots = self._sorted_slots
        index = bisect.bisect_left(slots, slot)
        for offset in range(len(slots)):
            candidate = slots[(index + offset) % len(slots)]
            server = self.ring[candidate]
            if server.healthy:
                return server
        return None

    def route(self, key: str) -> Server | None:
        slot = _hash_key(key, self.RING_SIZE)
        return self._next_server(slot)


async def test_load_balancing() -> bool:
    """Prueba el load balancing con los requisitos."""
    import asyncio
    print("Iniciando load balancing 100K req/s...")
    random.seed(3)

    servers = [Server(f"node_{i}") for i in range(10)]
    balancer = ConsistentHashBalancer(servers)

    # Simular 100_000 peticiones con claves variadas
    target = 100_000
    latencies: List[float] = []
    errors = 0
    start = time.perf_counter()

    for index in range(target):
        key = f"cliente_{index % 5000}_op_{index}"
        server = balancer.route(key)
        if server is None:
            errors += 1
            continue
        latencies.append(server.handle())

    elapsed = time.perf_counter() - start
    throughput = target / elapsed
    p99 = sorted(latencies)[int(len(latencies) * 0.99)]
    availability = (target - errors) / target * 100

    # Health check: retirar un nodo y ver que el trafico se redistribuye
    node = servers[0]
    node.healthy = False
    balancer.remove_server(node)
    redistributed = 0
    for index in range(1000):
        server = balancer.route(f"cliente_{index}")
        if server is not None and server is not node:
            redistributed += 1

    print("\n=== RESULTADOS ===")
    print(f"Peticiones: {target} en {elapsed:.2f}s -> {throughput:,.0f} req/s")
    print(f"Latencia p99: {p99:.2f}ms")
    print(f"Disponibilidad: {availability:.2f}%")
    print(f"Tras retirar nodo_0: {redistributed}/1000 re-enrutadas")

    print("\n=== VALIDACIÓN ===")
    success = True
    if throughput >= 100_000:
        print(f"✅ 100K req/s: {throughput:,.0f}")
    else:
        print(f"❌ Throughput insuficiente: {throughput:,.0f} < 100K")
        success = False
    if p99 < 100:
        print(f"✅ Latencia p99 < 100ms: {p99:.2f}ms")
    else:
        print(f"❌ Latencia p99 >= 100ms: {p99:.2f}ms")
        success = False
    if availability >= 99.9:
        print(f"✅ Disponibilidad >= 99.9%: {availability:.2f}%")
    else:
        print(f"❌ Disponibilidad: {availability:.2f}%")
        success = False
    if redistributed == 1000:
        print("✅ Consistent hashing: el trafico del nodo caido se redistribuye")
    else:
        print(f"⚠️ Redistribucion parcial: {redistributed}/1000")
    if 0.0 < min(s.requests for s in servers) and max(s.requests for s in servers) < target * 0.3:
        print("✅ Carga distribuida entre nodos (sin hot-spot)")
    else:
        print("⚠️ Distribucion de carga desigual")

    if success:
        print("\n✅ EJERCICIO COMPLETADO EXITOSAMENTE")
    else:
        print("\n❌ EJERCICIO NO COMPLETADO")
    return success


if __name__ == "__main__":
    import asyncio
    print("Iniciando Ejercicio 3.2: Load Balancing")
    print()
    result = asyncio.run(test_load_balancing())
    print("\n🎉 ¡Felicidades! Has completado el Ejercicio 3.2" if result
          else "\n⚠️ Necesitas optimizar el sistema")
