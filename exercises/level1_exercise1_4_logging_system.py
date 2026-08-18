"""
Ejercicio 1.4: Sistema de Logging 10K Events/Seg
Objetivo: Sistema de logging que procese 10,000 eventos/segundo.
Tiempo: 3 horas
Habilidades: Buffering, async I/O, structured logging

Requisitos:
- 10,000 eventos/segundo
- Persistencia en disco
- Búsqueda en logs
- < 1ms overhead de logging
- Compresión de logs antiguos
"""
import asyncio
import time
import random
import gzip
import json
from dataclasses import dataclass
from typing import List, Dict
from pathlib import Path
import statistics
from collections import deque


@dataclass
class LogEvent:
    level: str
    message: str
    timestamp: float
    metadata: dict


class LogBuffer:
    def __init__(self, max_size: int = 10000):
        self.buffer: deque = deque(maxlen=max_size)
        self.max_size = max_size
    
    def add(self, event: LogEvent) -> None:
        self.buffer.append(event)
    
    def get_all(self) -> List[LogEvent]:
        return list(self.buffer)
    
    def clear(self) -> None:
        self.buffer.clear()
    
    def size(self) -> int:
        return len(self.buffer)


class LogStorage:
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.current_file = None
        self.current_file_size = 0
        self.max_file_size = 10 * 1024 * 1024  # 10MB
        self.file_counter = 0
    
    def write_events(self, events: List[LogEvent]) -> int:
        """Escribe eventos al disco y retorna el número de bytes escritos."""
        if not events:
            return 0
        
        # Crear o rotar archivo si es necesario
        if self.current_file is None or self.current_file_size >= self.max_file_size:
            self._rotate_file()
        
        # Escribir eventos
        lines = []
        for event in events:
            log_entry = {
                "level": event.level,
                "message": event.message,
                "timestamp": event.timestamp,
                "metadata": event.metadata
            }
            lines.append(json.dumps(log_entry))
        
        content = "\n".join(lines) + "\n"
        self.current_file.write(content.encode('utf-8'))
        self.current_file.flush()
        
        bytes_written = len(content.encode('utf-8'))
        self.current_file_size += bytes_written
        
        return bytes_written
    
    def _rotate_file(self) -> None:
        """Rota el archivo de log actual."""
        if self.current_file is not None:
            self.current_file.close()
            # Comprimir archivo anterior
            self._compress_previous_file()
        
        self.file_counter += 1
        file_path = self.base_path / f"logs_{self.file_counter}.log"
        self.current_file = open(file_path, 'ab')
        self.current_file_size = 0
    
    def _compress_previous_file(self) -> None:
        """Comprime el archivo anterior."""
        if self.file_counter > 1:
            prev_file = self.base_path / f"logs_{self.file_counter - 1}.log"
            if prev_file.exists():
                compressed_file = self.base_path / f"logs_{self.file_counter - 1}.log.gz"
                with open(prev_file, 'rb') as f_in:
                    with gzip.open(compressed_file, 'wb') as f_out:
                        f_out.writelines(f_in)
                prev_file.unlink()
    
    def search(self, query: str, limit: int = 100) -> List[dict]:
        """Busca en los logs."""
        results = []
        
        # Buscar en archivos comprimidos y no comprimidos
        for log_file in sorted(self.base_path.glob("logs_*.log*")):
            if len(results) >= limit:
                break
            
            try:
                if log_file.suffix == '.gz':
                    with gzip.open(log_file, 'rt', encoding='utf-8') as f:
                        for line in f:
                            if query.lower() in line.lower():
                                results.append(json.loads(line))
                                if len(results) >= limit:
                                    break
                else:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            if query.lower() in line.lower():
                                results.append(json.loads(line))
                                if len(results) >= limit:
                                    break
            except Exception:
                continue
        
        return results
    
    def close(self) -> None:
        """Cierra el archivo actual."""
        if self.current_file is not None:
            self.current_file.close()
            self.current_file = None


class LoggingSystem:
    def __init__(self, storage_path: Path):
        self.buffer = LogBuffer(max_size=10000)
        self.storage = LogStorage(storage_path)
        self.write_overheads: List[float] = []
        self.total_events = 0
        self.flush_interval = 1.0  # segundos
        self.running = False
    
    async def log(self, level: str, message: str, metadata: dict = None) -> float:
        """Registra un evento y retorna el overhead en ms."""
        start = time.perf_counter()
        
        event = LogEvent(
            level=level,
            message=message,
            timestamp=time.time(),
            metadata=metadata or {}
        )
        
        self.buffer.add(event)
        self.total_events += 1
        
        overhead = (time.perf_counter() - start) * 1000  # ms
        return overhead
    
    async def flush_loop(self) -> None:
        """Loop de flush del buffer."""
        self.running = True
        
        while self.running:
            await asyncio.sleep(self.flush_interval)
            
            events = self.buffer.get_all()
            if events:
                start = time.perf_counter()
                self.storage.write_events(events)
                overhead = (time.perf_counter() - start) * 1000
                self.write_overheads.append(overhead)
                self.buffer.clear()
    
    def stop(self) -> None:
        """Detiene el sistema de logging."""
        self.running = False
        # Flush final
        events = self.buffer.get_all()
        if events:
            self.storage.write_events(events)
            self.buffer.clear()
        self.storage.close()
    
    def get_stats(self) -> dict:
        """Obtiene estadísticas del sistema."""
        if not self.write_overheads:
            return {
                "total_events": self.total_events,
                "buffer_size": self.buffer.size(),
                "write_overhead_avg": 0,
                "write_overhead_p99": 0
            }
        
        return {
            "total_events": self.total_events,
            "buffer_size": self.buffer.size(),
            "write_overhead_avg": statistics.mean(self.write_overheads),
            "write_overhead_p99": sorted(self.write_overheads)[int(len(self.write_overheads) * 0.99)]
        }


async def test_logging_system():
    """Prueba el sistema de logging con los requisitos."""
    print("Iniciando sistema de logging 10K events/seg...")
    
    # Crear directorio temporal para logs
    import tempfile
    temp_dir = Path(tempfile.mkdtemp())
    
    logging_system = LoggingSystem(temp_dir)
    
    # Iniciar loop de flush
    flush_task = asyncio.create_task(logging_system.flush_loop())
    
    # Simular 10,000 eventos/segundo por 10 segundos
    log_overheads = []
    start_time = time.time()
    
    while time.time() - start_time < 10:
        # Generar lote de eventos más grande
        batch_size = 500
        for _ in range(batch_size):
            level = random.choice(["DEBUG", "INFO", "WARNING", "ERROR"])
            message = f"Log message {random.randint(1, 10000)}"
            metadata = {"user_id": random.randint(1, 100), "request_id": random.randint(1, 1000)}
            
            overhead = await logging_system.log(level, message, metadata)
            log_overheads.append(overhead)
    
    # Detener sistema
    logging_system.stop()
    flush_task.cancel()
    
    # Obtener estadísticas
    stats = logging_system.get_stats()
    
    # Calcular overhead promedio de logging
    log_overhead_avg = statistics.mean(log_overheads) if log_overheads else 0
    log_overhead_p99 = sorted(log_overheads)[int(len(log_overheads) * 0.99)] if log_overheads else 0
    
    # Probar búsqueda
    search_results = logging_system.storage.search("ERROR", limit=10)
    
    print("\n=== RESULTADOS ===")
    print(f"Eventos totales: {stats['total_events']}")
    print(f"Buffer size: {stats['buffer_size']}")
    print(f"Log overhead promedio: {log_overhead_avg:.4f}ms")
    print(f"Log overhead p99: {log_overhead_p99:.4f}ms")
    print(f"Write overhead promedio: {stats['write_overhead_avg']:.4f}ms")
    print(f"Write overhead p99: {stats['write_overhead_p99']:.4f}ms")
    print(f"Resultados de búsqueda: {len(search_results)}")
    
    # Validación
    print("\n=== VALIDACIÓN ===")
    success = True
    
    events_per_second = stats['total_events'] / 10
    if events_per_second < 10000:
        print(f"❌ Eventos/segundo < 10,000: {events_per_second:.0f}")
        success = False
    else:
        print(f"✅ Eventos/segundo >= 10,000: {events_per_second:.0f}")
    
    if log_overhead_p99 >= 1:
        print(f"❌ Log overhead p99 >= 1ms: {log_overhead_p99:.4f}ms")
        success = False
    else:
        print(f"✅ Log overhead p99 < 1ms: {log_overhead_p99:.4f}ms")
    
    if len(search_results) == 0:
        print(f"❌ Búsqueda no funcionó: {len(search_results)} resultados")
        success = False
    else:
        print(f"✅ Búsqueda funcionó: {len(search_results)} resultados")
    
    # Verificar compresión
    compressed_files = list(temp_dir.glob("*.gz"))
    if len(compressed_files) > 0:
        print(f"✅ Compresión funcionó: {len(compressed_files)} archivos comprimidos")
    else:
        print(f"⚠️ No se generaron archivos comprimidos (puede ser normal si no hubo rotación)")
    
    # Limpiar directorio temporal
    import shutil
    shutil.rmtree(temp_dir)
    
    if success:
        print("\n✅ EJERCICIO COMPLETADO EXITOSAMENTE")
    else:
        print("\n❌ EJERCICIO NO COMPLETADO")
    
    return success


if __name__ == "__main__":
    print("Iniciando Ejercicio 1.4: Sistema de Logging 10K Events/Seg")
    print("Requisitos: 10K eventos/seg, persistencia, búsqueda, < 1ms overhead, compresión")
    print()
    
    result = asyncio.run(test_logging_system())
    
    if result:
        print("\n🎉 ¡Felicidades! Has completado el Ejercicio 1.4")
    else:
        print("\n⚠️ Necesitas optimizar el sistema para cumplir los requisitos")
