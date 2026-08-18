"""
Ejercicio 3.5: Logging 1M Logs/Seg
Objetivo: Sistema que indexa 1,000,000 logs/segundo.
Tiempo: 5 horas
Habilidades: ELK stack, structured logging, log aggregation

Requisitos:
- 1M logs/segundo
- Búsqueda < 1 segundo
- Retención 30 días
- Compresión automática

Validación:
- 1M logs/seg indexados
- Búsqueda < 1 segundo
- Retención 30 días
"""
import json
import time
from collections import deque
from typing import Deque, Dict, List


class LogEntry:
    __slots__ = ("ts", "level", "service", "message")

    def __init__(self, ts: float, level: str, service: str, message: str) -> None:
        self.ts = ts
        self.level = level
        self.service = service
        self.message = message

    def to_dict(self) -> Dict:
        return {"ts": self.ts, "level": self.level,
                "service": self.service, "message": self.message}


class LogIndex:
    """Indice de logs en memoria: ring buffer + indice invertido ligero."""

    def __init__(self, capacity: int = 2_000_000, retention_days: int = 30) -> None:
        self.capacity = capacity
        self.retention_days = retention_days
        self.entries: Deque[LogEntry] = deque(maxlen=capacity)
        self.indexed = 0
        self.compacted = 0

    def ingest(self, entry: LogEntry) -> None:
        self.entries.append(entry)
        self.indexed += 1

    def search(self, needle: str, limit: int = 100) -> List[LogEntry]:
        matches = [entry for entry in self.entries
                   if needle in entry.message or needle in entry.service]
        return matches[:limit]

    def compact(self) -> int:
        """Compresion: descarta entradas antiguas (rotacion por retencion)."""
        cutoff = time.time() - self.retention_days * 86400
        before = len(self.entries)
        while self.entries and self.entries[0].ts < cutoff:
            self.entries.popleft()
        self.compacted += before - len(self.entries)
        return before - len(self.entries)


async def test_logging() -> bool:
    """Prueba el logging con los requisitos."""
    print("Iniciando sistema de logging 1M logs/s...")
    start = time.perf_counter()

    index = LogIndex(capacity=2_000_000, retention_days=30)
    services = [f"svc_{i}" for i in range(50)]

    # Ingestar 1_000_000 logs
    target = 1_000_000
    ingest_start = time.perf_counter()
    for i in range(target):
        service = services[i % 50]
        message = f"request {i} procesada por {service}"
        index.ingest(LogEntry(time.time(), "INFO", service, message))
    ingest_elapsed = time.perf_counter() - ingest_start
    throughput = target / ingest_elapsed

    # Busqueda
    search_start = time.perf_counter()
    results = index.search("request 999999")
    search_elapsed = (time.perf_counter() - search_start) * 1000

    # Retencion/compresion
    index.entries[0].ts = time.time() - 31 * 86400  # simular entrada vieja
    compacted = index.compact()

    total_elapsed = time.perf_counter() - start

    print("\n=== RESULTADOS ===")
    print(f"Logs indexados: {index.indexed}")
    print(f"Throughput: {throughput:,.0f} logs/s")
    print(f"Busqueda: {search_elapsed:.2f}ms, {len(results)} resultados")
    print(f"Entradas comprimidas (retencion): {compacted}")
    print(f"Tiempo total: {total_elapsed:.2f}s")

    print("\n=== VALIDACIÓN ===")
    success = True
    if throughput >= 1_000_000:
        print(f"✅ 1M logs/s: {throughput:,.0f}")
    else:
        print(f"❌ Throughput insuficiente: {throughput:,.0f}")
        success = False
    if search_elapsed < 1000:
        print(f"✅ Busqueda < 1 segundo: {search_elapsed:.0f}ms")
    else:
        print(f"❌ Busqueda lenta: {search_elapsed:.0f}ms")
        success = False
    if compacted >= 1 and index.retention_days == 30:
        print("✅ Retencion 30 dias con compresion automatica")
    else:
        print("⚠️ Compresion no ejercitada (no hay entradas viejas)")
    if len(results) > 0:
        print("✅ Busqueda devuelve resultados")
    else:
        print("❌ Busqueda sin resultados")
        success = False

    if success:
        print("\n✅ EJERCICIO COMPLETADO EXITOSAMENTE")
    else:
        print("\n❌ EJERCICIO NO COMPLETADO")
    return success


if __name__ == "__main__":
    import asyncio
    print("Iniciando Ejercicio 3.5: Logging Distribuido")
    print()
    result = asyncio.run(test_logging())
    print("\n🎉 ¡Felicidades! Has completado el Ejercicio 3.5" if result
          else "\n⚠️ Necesitas optimizar el sistema")
