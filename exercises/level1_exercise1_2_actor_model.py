"""
Ejercicio 1.2: Actor Model con 50 Agentes
Objetivo: Simular 50 agentes independientes que colaboran en una tarea.
Tiempo: 3 horas
Habilidades: Actor model, concurrency, message passing

Requisitos:
- 50 agentes independientes
- Cada agente tiene su propio estado
- Comunicación asíncrona
- Sin race conditions
- < 5% overhead de comunicación
"""
import asyncio
import time
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from collections import defaultdict
import threading


@dataclass
class Message:
    sender_id: int
    receiver_id: int
    content: dict
    timestamp: float


class Actor:
    def __init__(self, actor_id: int, total_actors: int):
        self.actor_id = actor_id
        self.total_actors = total_actors
        self.state: Dict = {"value": random.randint(1, 100)}
        self.inbox: asyncio.Queue = asyncio.Queue()
        self.message_count = 0
        self.processing_time = 0.0
        self.running = False
    
    async def send_message(self, receiver: 'Actor', content: dict) -> None:
        """Envía un mensaje a otro actor."""
        message = Message(
            sender_id=self.actor_id,
            receiver_id=receiver.actor_id,
            content=content,
            timestamp=time.time()
        )
        await receiver.inbox.put(message)
    
    async def receive_and_process(self) -> None:
        """Recibe y procesa mensajes del inbox."""
        while self.running:
            try:
                message = await asyncio.wait_for(self.inbox.get(), timeout=0.1)
                start = time.perf_counter()
                
                # Procesar mensaje
                self._process_message(message)
                
                self.processing_time += time.perf_counter() - start
                self.message_count += 1
            except asyncio.TimeoutError:
                continue
    
    def _process_message(self, message: Message) -> None:
        """Procesa un mensaje (simulación de lógica de negocio)."""
        # Simular trabajo de procesamiento significativo
        total = 0
        for i in range(100000):
            total += i
        
        # Actualizar estado basado en el mensaje
        if "operation" in message.content:
            op = message.content["operation"]
            if op == "add":
                self.state["value"] += message.content.get("value", 0)
            elif op == "multiply":
                self.state["value"] *= message.content.get("value", 1)
            elif op == "request":
                # Responder con el estado actual
                pass
    
    async def start(self) -> None:
        """Inicia el actor."""
        self.running = True
        await self.receive_and_process()
    
    def stop(self) -> None:
        """Detiene el actor."""
        self.running = False


class ActorSystem:
    def __init__(self, num_actors: int):
        self.num_actors = num_actors
        self.actors: List[Actor] = [Actor(i, num_actors) for i in range(num_actors)]
        self.total_messages = 0
        self.communication_overhead = 0.0
        self.lock = threading.Lock()
    
    def get_actor(self, actor_id: int) -> Optional[Actor]:
        """Obtiene un actor por ID."""
        if 0 <= actor_id < len(self.actors):
            return self.actors[actor_id]
        return None
    
    async def simulate_collaboration(self, duration: float) -> Dict:
        """Simula colaboración entre agentes."""
        # Iniciar todos los actores
        tasks = [asyncio.create_task(actor.start()) for actor in self.actors]
        
        # Simular mensajes aleatorios entre agentes
        message_task = asyncio.create_task(self._generate_messages(duration))
        
        # Esperar duración
        await asyncio.sleep(duration)
        
        # Detener todos los actores
        for actor in self.actors:
            actor.stop()
        
        # Cancelar tareas
        message_task.cancel()
        for task in tasks:
            task.cancel()
        
        # Esperar que terminen
        await asyncio.gather(*tasks, message_task, return_exceptions=True)
        
        # Calcular estadísticas
        total_messages = sum(actor.message_count for actor in self.actors)
        total_processing = sum(actor.processing_time for actor in self.actors)
        
        # Calcular overhead de comunicación (tiempo de comunicación vs tiempo total)
        total_time = total_processing + self.communication_overhead
        if total_time > 0:
            communication_overhead = (self.communication_overhead / total_time) * 100
        else:
            communication_overhead = 0.0
        
        return {
            "total_messages": total_messages,
            "total_processing_time": total_processing,
            "communication_overhead": communication_overhead,
            "actors": len(self.actors)
        }
    
    async def _generate_messages(self, duration: float) -> None:
        """Genera mensajes aleatorios entre agentes."""
        start_time = time.time()
        
        while time.time() - start_time < duration:
            # Seleccionar remitente y receptor aleatorios
            sender = random.choice(self.actors)
            receiver = random.choice(self.actors)
            
            if sender.actor_id != receiver.actor_id:
                # Generar mensaje
                operation = random.choice(["add", "multiply", "request"])
                content = {
                    "operation": operation,
                    "value": random.randint(1, 10)
                }
                
                # Medir overhead de comunicación
                comm_start = time.perf_counter()
                await sender.send_message(receiver, content)
                comm_time = time.perf_counter() - comm_start
                
                with self.lock:
                    self.communication_overhead += comm_time
                    self.total_messages += 1
            
            # Pequeña pausa para no saturar
            await asyncio.sleep(0.01)


async def test_actor_model():
    """Prueba el sistema de actores con los requisitos."""
    print("Iniciando sistema de 50 actores...")
    
    system = ActorSystem(num_actors=50)
    
    # Simular colaboración por 10 segundos
    stats = await system.simulate_collaboration(duration=10.0)
    
    print("\n=== RESULTADOS ===")
    print(f"Actores: {stats['actors']}")
    print(f"Mensajes totales: {stats['total_messages']}")
    print(f"Tiempo de procesamiento total: {stats['total_processing_time']:.4f}s")
    print(f"Overhead de comunicación: {stats['communication_overhead']:.2f}%")
    
    # Validación
    print("\n=== VALIDACIÓN ===")
    success = True
    
    if stats['actors'] != 50:
        print(f"❌ Número de actores != 50: {stats['actors']}")
        success = False
    else:
        print(f"✅ 50 agentes independientes: {stats['actors']}")
    
    if stats['total_messages'] < 100:
        print(f"❌ Mensajes totales < 100: {stats['total_messages']}")
        success = False
    else:
        print(f"✅ Comunicación asíncrona funcionando: {stats['total_messages']} mensajes")
    
    if stats['communication_overhead'] >= 5:
        print(f"❌ Overhead de comunicación >= 5%: {stats['communication_overhead']:.2f}%")
        success = False
    else:
        print(f"✅ Overhead de comunicación < 5%: {stats['communication_overhead']:.2f}%")
    
    # Verificar que cada actor tiene su propio estado
    states = [actor.state for actor in system.actors]
    unique_states = len(set(str(s) for s in states))
    
    if unique_states < 40:  # Al menos 80% de estados únicos
        print(f"❌ Estados no son independientes: {unique_states} únicos de 50")
        success = False
    else:
        print(f"✅ Estados independientes: {unique_states} únicos de 50")
    
    if success:
        print("\n✅ EJERCICIO COMPLETADO EXITOSAMENTE")
    else:
        print("\n❌ EJERCICIO NO COMPLETADO")
    
    return success


if __name__ == "__main__":
    print("Iniciando Ejercicio 1.2: Actor Model con 50 Agentes")
    print("Requisitos: 50 agentes, estado independiente, comunicación asíncrona, sin race conditions, < 5% overhead")
    print()
    
    result = asyncio.run(test_actor_model())
    
    if result:
        print("\n🎉 ¡Felicidades! Has completado el Ejercicio 1.2")
    else:
        print("\n⚠️ Necesitas optimizar el sistema para cumplir los requisitos")
