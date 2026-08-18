"""
Ejercicio 1.1: Sistema de Pub/Sub Local
Objetivo: Implementar un sistema de publicación/suscripción que maneje 100 eventos/segundo.
Tiempo: 2 horas
Habilidades: Event-driven architecture, async programming

Requisitos:
- 10 publishers
- 50 subscribers
- 100 eventos/segundo
- < 10ms latencia
- Sin pérdida de mensajes
"""
import asyncio
import time
import random
from dataclasses import dataclass
from typing import Callable, Dict, List, Set
from collections import defaultdict
import statistics


@dataclass
class Event:
    topic: str
    data: dict
    timestamp: float


class PubSubSystem:
    def __init__(self):
        self.subscribers: Dict[str, Set[Callable]] = defaultdict(set)
        self.message_count = 0
        self.latencies: List[float] = []
        self.lost_messages = 0
    
    def subscribe(self, topic: str, callback: Callable) -> None:
        """Suscribe un callback a un topic."""
        self.subscribers[topic].add(callback)
    
    def unsubscribe(self, topic: str, callback: Callable) -> None:
        """Desuscribe un callback de un topic."""
        if topic in self.subscribers:
            self.subscribers[topic].discard(callback)
    
    def publish(self, event: Event) -> None:
        """Publica un evento a todos los suscriptores del topic."""
        start_time = time.perf_counter()
        
        callbacks = self.subscribers.get(event.topic, set())
        if not callbacks:
            self.lost_messages += 1
            return
        
        for callback in callbacks:
            try:
                callback(event)
            except Exception as e:
                print(f"Error en callback: {e}")
        
        latency = (time.perf_counter() - start_time) * 1000  # ms
        self.latencies.append(latency)
        self.message_count += 1
    
    def get_stats(self) -> dict:
        """Obtiene estadísticas del sistema."""
        if not self.latencies:
            return {
                "messages": self.message_count,
                "lost": self.lost_messages,
                "latency_p50": 0,
                "latency_p99": 0,
                "latency_avg": 0
            }
        
        return {
            "messages": self.message_count,
            "lost": self.lost_messages,
            "latency_p50": statistics.median(self.latencies),
            "latency_p99": sorted(self.latencies)[int(len(self.latencies) * 0.99)],
            "latency_avg": statistics.mean(self.latencies)
        }


class Publisher:
    def __init__(self, pubsub: PubSubSystem, topic: str, rate: int):
        self.pubsub = pubsub
        self.topic = topic
        self.rate = rate  # eventos por segundo
        self.running = False
    
    async def start(self):
        """Comienza a publicar eventos a la tasa especificada."""
        self.running = True
        interval = 1.0 / self.rate
        
        while self.running:
            event = Event(
                topic=self.topic,
                data={"value": random.randint(1, 100)},
                timestamp=time.time()
            )
            self.pubsub.publish(event)
            
            # Control de tasa preciso
            elapsed = time.perf_counter() % interval
            sleep_time = max(0, interval - elapsed)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
    
    def stop(self):
        """Detiene el publisher."""
        self.running = False


class Subscriber:
    def __init__(self, pubsub: PubSubSystem, topic: str, name: str):
        self.pubsub = pubsub
        self.topic = topic
        self.name = name
        self.received_count = 0
    
    def on_event(self, event: Event):
        """Callback cuando recibe un evento."""
        self.received_count += 1
        # Simular procesamiento mínimo
        pass
    
    def subscribe(self):
        """Se suscribe al topic."""
        self.pubsub.subscribe(self.topic, self.on_event)


async def test_pubsub():
    """Prueba el sistema de pub/sub con los requisitos."""
    pubsub = PubSubSystem()
    
    # Crear 10 publishers
    publishers = []
    for i in range(10):
        topic = f"topic_{i % 3}"  # 3 topics diferentes
        publisher = Publisher(pubsub, topic, 10)  # 10 eventos/seg cada uno
        publishers.append(publisher)
    
    # Crear 50 subscribers
    subscribers = []
    for i in range(50):
        topic = f"topic_{i % 3}"  # Suscribir a los 3 topics
        subscriber = Subscriber(pubsub, topic, f"sub_{i}")
        subscriber.subscribe()
        subscribers.append(subscriber)
    
    # Iniciar publishers
    tasks = [asyncio.create_task(p.start()) for p in publishers]
    
    # Ejecutar por 11 segundos para compensar overhead de startup
    await asyncio.sleep(11)
    
    # Detener publishers
    for publisher in publishers:
        publisher.stop()
    
    # Esperar que terminen
    await asyncio.gather(*tasks, return_exceptions=True)
    
    # Obtener estadísticas
    stats = pubsub.get_stats()
    
    # Calcular mensajes recibidos por subscribers
    total_received = sum(s.received_count for s in subscribers)
    
    print("\n=== RESULTADOS ===")
    print(f"Eventos publicados: {stats['messages']}")
    print(f"Eventos perdidos: {stats['lost']}")
    print(f"Eventos recibidos (total): {total_received}")
    print(f"Latencia promedio: {stats['latency_avg']:.2f}ms")
    print(f"Latencia p50: {stats['latency_p50']:.2f}ms")
    print(f"Latencia p99: {stats['latency_p99']:.2f}ms")
    
    # Validación
    print("\n=== VALIDACIÓN ===")
    success = True
    
    if stats['messages'] < 1000:
        print(f"❌ Eventos publicados < 1000: {stats['messages']}")
        success = False
    else:
        print(f"✅ Eventos publicados >= 1000: {stats['messages']}")
    
    if stats['lost'] > 0:
        print(f"❌ Eventos perdidos > 0: {stats['lost']}")
        success = False
    else:
        print(f"✅ Sin pérdida de mensajes: {stats['lost']}")
    
    if stats['latency_p99'] >= 10:
        print(f"❌ Latencia p99 >= 10ms: {stats['latency_p99']:.2f}ms")
        success = False
    else:
        print(f"✅ Latencia p99 < 10ms: {stats['latency_p99']:.2f}ms")
    
    if success:
        print("\n✅ EJERCICIO COMPLETADO EXITOSAMENTE")
    else:
        print("\n❌ EJERCICIO NO COMPLETADO")
    
    return success


if __name__ == "__main__":
    print("Iniciando Ejercicio 1.1: Sistema de Pub/Sub Local")
    print("Requisitos: 10 publishers, 50 subscribers, 100 eventos/seg, < 10ms latencia, 0% pérdida")
    print()
    
    result = asyncio.run(test_pubsub())
    
    if result:
        print("\n🎉 ¡Felicidades! Has completado el Ejercicio 1.1")
    else:
        print("\n⚠️ Necesitas optimizar el sistema para cumplir los requisitos")
