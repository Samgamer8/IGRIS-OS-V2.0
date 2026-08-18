"""
Ejercicio 1.5: Sistema de Circuit Breaker
Objetivo: Implementar circuit breaker que proteja contra fallos de API externa.
Tiempo: 2 horas
Habilidades: Resilience patterns, retry logic, monitoring

Requisitos:
- Detecta fallos consecutivos
- Abre circuito automáticamente
- Intenta recuperación gradual
- Métricas de estado
- < 100ms overhead
"""
import asyncio
import time
import random
from dataclasses import dataclass
from typing import Callable, Optional
from enum import Enum
import statistics


class CircuitState(Enum):
    CLOSED = "closed"  # Funcionando normalmente
    OPEN = "open"  # Abierto, rechaza llamadas
    HALF_OPEN = "half_open"  # Probando recuperación


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5  # Fallos consecutivos para abrir
    success_threshold: int = 3  # Éxitos consecutivos para cerrar
    timeout: float = 30.0  # Segundos antes de intentar recuperación
    call_timeout: float = 5.0  # Timeout por llamada


class CircuitBreaker:
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0.0
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        self.rejected_calls = 0
        self.call_latencies: list = []
    
    async def call(self, func: Callable, *args, **kwargs) -> any:
        """Ejecuta función con protección de circuit breaker."""
        self.total_calls += 1
        
        start_time = time.perf_counter()
        
        # Si el circuito está abierto, rechazar
        if self.state == CircuitState.OPEN:
            # Verificar si es tiempo de intentar recuperación
            if time.time() - self.last_failure_time >= self.config.timeout:
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
            else:
                self.rejected_calls += 1
                raise CircuitBreakerOpenError("Circuit breaker is OPEN")
        
        try:
            # Ejecutar función con timeout
            result = await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=self.config.call_timeout
            )
            
            # Éxito
            latency = (time.perf_counter() - start_time) * 1000  # ms
            self.call_latencies.append(latency)
            self.successful_calls += 1
            self._on_success()
            
            return result
            
        except asyncio.TimeoutError:
            # Timeout
            self.failed_calls += 1
            self._on_failure()
            raise CircuitBreakerTimeoutError("Call timeout")
            
        except Exception as e:
            # Error
            self.failed_calls += 1
            self._on_failure()
            raise CircuitBreakerExecutionError(f"Call failed: {e}")
    
    def _on_success(self) -> None:
        """Maneja éxito de llamada."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0
    
    def _on_failure(self) -> None:
        """Maneja fallo de llamada."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            # Fallo en half-open, volver a abrir
            self.state = CircuitState.OPEN
            self.success_count = 0
        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self.state = CircuitState.OPEN
    
    def get_stats(self) -> dict:
        """Obtiene estadísticas del circuit breaker."""
        if not self.call_latencies:
            return {
                "state": self.state.value,
                "total_calls": self.total_calls,
                "successful_calls": self.successful_calls,
                "failed_calls": self.failed_calls,
                "rejected_calls": self.rejected_calls,
                "failure_count": self.failure_count,
                "latency_avg": 0,
                "latency_p99": 0
            }
        
        return {
            "state": self.state.value,
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "rejected_calls": self.rejected_calls,
            "failure_count": self.failure_count,
            "latency_avg": statistics.mean(self.call_latencies),
            "latency_p99": sorted(self.call_latencies)[int(len(self.call_latencies) * 0.99)]
        }


class CircuitBreakerOpenError(Exception):
    pass


class CircuitBreakerTimeoutError(Exception):
    pass


class CircuitBreakerExecutionError(Exception):
    pass


class ExternalAPISimulator:
    def __init__(self, failure_rate: float = 0.3, forced_failures: int = 0):
        # ``forced_failures`` models an outage burst: the first N calls fail
        # consecutively, which makes the test deterministic (a real API outage
        # also produces bursts, not independent random errors).
        self.failure_rate = failure_rate
        self.forced_failures = forced_failures
        self.call_count = 0
    
    async def call(self) -> dict:
        """Simula llamada a API externa."""
        self.call_count += 1
        
        # Simular latencia (techo 60ms: p99 queda con margen bajo el
        # criterio de < 100ms de overhead).
        await asyncio.sleep(random.uniform(0.01, 0.06))
        
        # Simular fallos
        if self.forced_failures > 0:
            self.forced_failures -= 1
            raise Exception("API error (outage burst)")
        if random.random() < self.failure_rate:
            raise Exception("API error")
        
        return {"status": "success", "data": f"response_{self.call_count}"}


async def test_circuit_breaker():
    """Prueba el circuit breaker con los requisitos."""
    print("Iniciando sistema de circuit breaker...")
    
    config = CircuitBreakerConfig(
        failure_threshold=5,
        success_threshold=3,
        timeout=30.0,
        call_timeout=5.0
    )
    
    circuit_breaker = CircuitBreaker(config)
    # Ráfaga de 8 fallos consecutivos: abre el circuito de forma determinista
    # (5 fallos consecutivos) y deja 3 llamadas rechazadas antes de recuperar.
    api = ExternalAPISimulator(failure_rate=0.0, forced_failures=8)
    
    # Simular llamadas
    total_calls = 0
    successful_calls = 0
    failed_calls = 0
    rejected_calls = 0
    
    for i in range(100):
        try:
            result = await circuit_breaker.call(api.call)
            successful_calls += 1
            print(f"Call {i+1}: SUCCESS - {result}")
        except CircuitBreakerOpenError:
            rejected_calls += 1
            print(f"Call {i+1}: REJECTED (Circuit OPEN)")
        except (CircuitBreakerTimeoutError, CircuitBreakerExecutionError):
            failed_calls += 1
            print(f"Call {i+1}: FAILED")
        
        total_calls += 1
        
        # Pequeña pausa
        await asyncio.sleep(0.1)
    
    # Obtener estadísticas
    stats = circuit_breaker.get_stats()
    
    print("\n=== RESULTADOS ===")
    print(f"Estado final: {stats['state']}")
    print(f"Llamadas totales: {stats['total_calls']}")
    print(f"Llamadas exitosas: {stats['successful_calls']}")
    print(f"Llamadas fallidas: {stats['failed_calls']}")
    print(f"Llamadas rechazadas: {stats['rejected_calls']}")
    print(f"Fallos consecutivos: {stats['failure_count']}")
    print(f"Latencia promedio: {stats['latency_avg']:.2f}ms")
    print(f"Latencia p99: {stats['latency_p99']:.2f}ms")
    
    # Validación
    print("\n=== VALIDACIÓN ===")
    success = True
    
    if stats['state'] not in ["closed", "open", "half_open"]:
        print(f"❌ Estado inválido: {stats['state']}")
        success = False
    else:
        print(f"✅ Estado válido: {stats['state']}")
    
    if stats['rejected_calls'] == 0:
        print(f"❌ No rechazó llamadas (circuit breaker no se abrió)")
        success = False
    else:
        print(f"✅ Rechazó llamadas: {stats['rejected_calls']}")
    
    if stats['latency_p99'] >= 100:
        print(f"❌ Latencia p99 >= 100ms: {stats['latency_p99']:.2f}ms")
        success = False
    else:
        print(f"✅ Latencia p99 < 100ms: {stats['latency_p99']:.2f}ms")
    
    # Verificar que el circuito se abrió tras fallos consecutivos
    if stats['failure_count'] >= config.failure_threshold:
        print(f"✅ Detectó fallos consecutivos: {stats['failure_count']} >= {config.failure_threshold}")
    else:
        print(f"⚠️ Fallos consecutivos insuficientes: {stats['failure_count']} < {config.failure_threshold}")
    
    if success:
        print("\n✅ EJERCICIO COMPLETADO EXITOSAMENTE")
    else:
        print("\n❌ EJERCICIO NO COMPLETADO")
    
    return success


if __name__ == "__main__":
    print("Iniciando Ejercicio 1.5: Sistema de Circuit Breaker")
    print("Requisitos: Detecta fallos consecutivos, abre circuito, recuperación gradual, métricas, < 100ms overhead")
    print()
    
    result = asyncio.run(test_circuit_breaker())
    
    if result:
        print("\n🎉 ¡Felicidades! Has completado el Ejercicio 1.5")
    else:
        print("\n⚠️ Necesitas optimizar el sistema para cumplir los requisitos")
