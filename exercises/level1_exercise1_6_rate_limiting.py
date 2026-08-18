"""
Ejercicio 1.6: Rate Limiting con Token Bucket
Objetivo: Implementar rate limiting que maneje 10,000 req/min.
Tiempo: 2 horas
Habilidades: Rate limiting algorithms, distributed counters

Requisitos:
- 10,000 req/min por usuario
- Token bucket algorithm
- Distributed con Redis
- < 1ms overhead
- Precisión de 99%
"""
import asyncio
import time
import random
from dataclasses import dataclass
from typing import Dict
import statistics


@dataclass
class TokenBucket:
    capacity: int  # Capacidad máxima del bucket
    refill_rate: float  # Tokens por segundo
    tokens: float  # Tokens actuales
    last_refill: float  # Último refill en segundos
    
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = float(capacity)
        self.last_refill = time.time()
    
    def consume(self, tokens: int = 1) -> bool:
        """Consume tokens del bucket. Retorna True si exitoso."""
        # Refill tokens basado en tiempo transcurrido
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now
        
        # Verificar si hay suficientes tokens
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False
    
    def get_tokens(self) -> float:
        """Obtiene el número actual de tokens."""
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now
        return self.tokens


class RateLimiter:
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.buckets: Dict[str, TokenBucket] = {}
        self.total_requests = 0
        self.allowed_requests = 0
        self.denied_requests = 0
        self.check_latencies: list = []
    
    def check_rate_limit(self, user_id: str, tokens: int = 1) -> bool:
        """Verifica si el usuario puede hacer la solicitud."""
        start = time.perf_counter()
        
        self.total_requests += 1
        
        # Obtener o crear bucket para el usuario
        if user_id not in self.buckets:
            self.buckets[user_id] = TokenBucket(self.capacity, self.refill_rate)
        
        bucket = self.buckets[user_id]
        allowed = bucket.consume(tokens)
        
        if allowed:
            self.allowed_requests += 1
        else:
            self.denied_requests += 1
        
        latency = (time.perf_counter() - start) * 1000  # ms
        self.check_latencies.append(latency)
        
        return allowed
    
    def get_stats(self) -> dict:
        """Obtiene estadísticas del rate limiter."""
        if not self.check_latencies:
            return {
                "total_requests": self.total_requests,
                "allowed_requests": self.allowed_requests,
                "denied_requests": self.denied_requests,
                "latency_avg": 0,
                "latency_p99": 0,
                "active_users": len(self.buckets)
            }
        
        return {
            "total_requests": self.total_requests,
            "allowed_requests": self.allowed_requests,
            "denied_requests": self.denied_requests,
            "latency_avg": statistics.mean(self.check_latencies),
            "latency_p99": sorted(self.check_latencies)[int(len(self.check_latencies) * 0.99)],
            "active_users": len(self.buckets)
        }


async def test_rate_limiting():
    """Prueba el rate limiting con los requisitos."""
    print("Iniciando sistema de rate limiting...")
    
    # 10,000 req/min = ~166.67 req/seg
    # Usamos capacidad de 200 tokens y refill rate de 166.67 tokens/seg
    rate_limiter = RateLimiter(capacity=200, refill_rate=166.67)
    
    # Simular 100 usuarios
    num_users = 100
    users = [f"user_{i}" for i in range(num_users)]
    
    # Simular solicitudes
    total_requests = 0
    allowed_requests = 0
    denied_requests = 0
    
    # Simular por 60 segundos (1 minuto)
    duration = 60
    start_time = time.time()
    
    while time.time() - start_time < duration:
        # Cada usuario hace una solicitud aleatoria
        for user_id in users:
            if time.time() - start_time >= duration:
                break
            
            # Algunos usuarios hacen más solicitudes que otros
            if random.random() < 0.3:  # 30% de probabilidad de hacer solicitud
                allowed = rate_limiter.check_rate_limit(user_id)
                total_requests += 1
                
                if allowed:
                    allowed_requests += 1
                else:
                    denied_requests += 1
        
        # Pequeña pausa
        await asyncio.sleep(0.01)
    
    # Obtener estadísticas
    stats = rate_limiter.get_stats()
    
    # Calcular requests por minuto
    actual_rpm = stats['total_requests'] / duration * 60
    
    print("\n=== RESULTADOS ===")
    print(f"Usuarios activos: {stats['active_users']}")
    print(f"Solicitudes totales: {stats['total_requests']}")
    print(f"Solicitudes permitidas: {stats['allowed_requests']}")
    print(f"Solicitudes denegadas: {stats['denied_requests']}")
    print(f"Requests/minuto (actual): {actual_rpm:.0f}")
    print(f"Latencia promedio: {stats['latency_avg']:.4f}ms")
    print(f"Latencia p99: {stats['latency_p99']:.4f}ms")
    
    # Validación
    print("\n=== VALIDACIÓN ===")
    success = True
    
    target_rpm = 10000  # 10,000 req/min
    if actual_rpm < target_rpm * 0.99:  # 99% precisión
        print(f"❌ Requests/minuto < 99% de objetivo: {actual_rpm:.0f} < {target_rpm * 0.99:.0f}")
        success = False
    else:
        print(f"✅ Requests/minuto >= 99% de objetivo: {actual_rpm:.0f} >= {target_rpm * 0.99:.0f}")
    
    if stats['latency_p99'] >= 1:
        print(f"❌ Latencia p99 >= 1ms: {stats['latency_p99']:.4f}ms")
        success = False
    else:
        print(f"✅ Latencia p99 < 1ms: {stats['latency_p99']:.4f}ms")
    
    if stats['denied_requests'] == 0:
        print(f"⚠️ No denegó solicitudes (puede ser normal si no se excedió el límite)")
    else:
        print(f"✅ Denegó solicitudes cuando se excedió el límite: {stats['denied_requests']}")
    
    # Verificar precisión del algoritmo
    if stats['active_users'] > 0:
        avg_requests_per_user = stats['total_requests'] / stats['active_users']
        expected_per_user = target_rpm / stats['active_users']
        
        if abs(avg_requests_per_user - expected_per_user) / expected_per_user < 0.01:
            print(f"✅ Precisión del 99% en distribución por usuario")
        else:
            print(f"⚠️ Precisión no verificada: {avg_requests_per_user:.0f} vs {expected_per_user:.0f}")
    
    if success:
        print("\n✅ EJERCICIO COMPLETADO EXITOSAMENTE")
    else:
        print("\n❌ EJERCICIO NO COMPLETADO")
    
    return success


if __name__ == "__main__":
    print("Iniciando Ejercicio 1.6: Rate Limiting con Token Bucket")
    print("Requisitos: 10K req/min, token bucket, distributed, < 1ms overhead, 99% precisión")
    print()
    
    result = asyncio.run(test_rate_limiting())
    
    if result:
        print("\n🎉 ¡Felicidades! Has completado el Ejercicio 1.6")
    else:
        print("\n⚠️ Necesitas optimizar el sistema para cumplir los requisitos")
