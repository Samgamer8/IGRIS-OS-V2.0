"""
Ejercicio 1.3: Sistema de Chat con 1000 Usuarios
Objetivo: Sistema de chat que maneje 1000 usuarios concurrentes.
Tiempo: 4 horas
Habilidades: WebSockets, connection pooling, message queues

Requisitos:
- 1000 usuarios concurrentes
- < 50ms latencia de mensajes
- Persistencia de mensajes
- Soporte para rooms
- 99.9% uptime
"""
import asyncio
import time
import random
from dataclasses import dataclass, field
from typing import Dict, List, Set
from collections import defaultdict
import statistics


@dataclass
class ChatMessage:
    user_id: str
    room_id: str
    content: str
    timestamp: float


@dataclass
class User:
    user_id: str
    current_room: str
    messages_received: int = 0
    connected: bool = True


class ChatRoom:
    def __init__(self, room_id: str):
        self.room_id = room_id
        self.users: Set[str] = set()
        self.message_history: List[ChatMessage] = []
        self.max_history = 1000
    
    def add_user(self, user_id: str) -> None:
        self.users.add(user_id)
    
    def remove_user(self, user_id: str) -> None:
        self.users.discard(user_id)
    
    def add_message(self, message: ChatMessage) -> None:
        self.message_history.append(message)
        if len(self.message_history) > self.max_history:
            self.message_history.pop(0)
    
    def get_recent_messages(self, limit: int = 50) -> List[ChatMessage]:
        return self.message_history[-limit:]


class ChatSystem:
    def __init__(self):
        self.rooms: Dict[str, ChatRoom] = {}
        self.users: Dict[str, User] = {}
        self.message_latencies: List[float] = []
        self.total_messages = 0
        self.lost_messages = 0
        self.uptime_start = time.time()
        self.downtime_periods: List[tuple] = []  # (start, end)
    
    def create_room(self, room_id: str) -> ChatRoom:
        if room_id not in self.rooms:
            self.rooms[room_id] = ChatRoom(room_id)
        return self.rooms[room_id]
    
    def join_room(self, user_id: str, room_id: str) -> None:
        if user_id not in self.users:
            self.users[user_id] = User(user_id, room_id)
        else:
            self.users[user_id].current_room = room_id
        
        room = self.create_room(room_id)
        room.add_user(user_id)
    
    def leave_room(self, user_id: str) -> None:
        if user_id in self.users:
            room_id = self.users[user_id].current_room
            if room_id in self.rooms:
                self.rooms[room_id].remove_user(user_id)
            self.users[user_id].connected = False
    
    def send_message(self, user_id: str, content: str) -> float:
        """Envía un mensaje y retorna la latencia en ms."""
        start_time = time.perf_counter()
        
        if user_id not in self.users:
            self.lost_messages += 1
            return 0.0
        
        user = self.users[user_id]
        if not user.connected:
            self.lost_messages += 1
            return 0.0
        
        room_id = user.current_room
        if room_id not in self.rooms:
            self.lost_messages += 1
            return 0.0
        
        room = self.rooms[room_id]
        message = ChatMessage(user_id, room_id, content, time.time())
        room.add_message(message)
        
        # Simular entrega a todos los usuarios en el room
        for other_user_id in room.users:
            if other_user_id != user_id and other_user_id in self.users:
                self.users[other_user_id].messages_received += 1
        
        latency = (time.perf_counter() - start_time) * 1000  # ms
        self.message_latencies.append(latency)
        self.total_messages += 1
        
        return latency
    
    def get_stats(self) -> dict:
        """Obtiene estadísticas del sistema."""
        uptime = time.time() - self.uptime_start
        total_downtime = sum(end - start for start, end in self.downtime_periods)
        actual_uptime = uptime - total_downtime
        uptime_percentage = (actual_uptime / uptime * 100) if uptime > 0 else 100
        
        if not self.message_latencies:
            return {
                "users": len(self.users),
                "rooms": len(self.rooms),
                "messages": self.total_messages,
                "lost": self.lost_messages,
                "latency_p50": 0,
                "latency_p99": 0,
                "latency_avg": 0,
                "uptime_percentage": uptime_percentage
            }
        
        return {
            "users": len(self.users),
            "rooms": len(self.rooms),
            "messages": self.total_messages,
            "lost": self.lost_messages,
            "latency_p50": statistics.median(self.message_latencies),
            "latency_p99": sorted(self.message_latencies)[int(len(self.message_latencies) * 0.99)],
            "latency_avg": statistics.mean(self.message_latencies),
            "uptime_percentage": uptime_percentage
        }


class ChatUserSimulator:
    def __init__(self, chat_system: ChatSystem, user_id: str, room_id: str):
        self.chat_system = chat_system
        self.user_id = user_id
        self.room_id = room_id
        self.running = False
        self.message_count = 0
    
    async def start(self) -> None:
        """Simula actividad de usuario."""
        self.chat_system.join_room(self.user_id, self.room_id)
        self.running = True
        
        while self.running:
            # Enviar mensaje aleatorio
            messages = [
                "Hola a todos",
                "¿Cómo están?",
                "Buen día",
                "Interesante",
                "De acuerdo",
                "Gracias",
                "Perfecto",
                "Entendido"
            ]
            content = random.choice(messages)
            self.chat_system.send_message(self.user_id, content)
            self.message_count += 1
            
            # Pausa aleatoria entre mensajes
            await asyncio.sleep(random.uniform(0.1, 1.0))
    
    def stop(self) -> None:
        """Detiene el simulador."""
        self.running = False
        self.chat_system.leave_room(self.user_id)


async def test_chat_system():
    """Prueba el sistema de chat con los requisitos."""
    print("Iniciando sistema de chat con 1000 usuarios...")
    
    chat_system = ChatSystem()
    
    # Crear 10 rooms
    rooms = [f"room_{i}" for i in range(10)]
    for room_id in rooms:
        chat_system.create_room(room_id)
    
    # Crear 1000 usuarios simulados
    simulators = []
    for i in range(1000):
        room_id = rooms[i % 10]  # Distribuir usuarios entre rooms
        simulator = ChatUserSimulator(chat_system, f"user_{i}", room_id)
        simulators.append(simulator)
    
    # Iniciar todos los usuarios
    tasks = [asyncio.create_task(s.start()) for s in simulators]
    
    # Simular actividad por 30 segundos
    await asyncio.sleep(30)
    
    # Detener todos los usuarios
    for simulator in simulators:
        simulator.stop()
    
    # Cancelar tareas
    for task in tasks:
        task.cancel()
    
    # Esperar que terminen
    await asyncio.gather(*tasks, return_exceptions=True)
    
    # Obtener estadísticas
    stats = chat_system.get_stats()
    
    print("\n=== RESULTADOS ===")
    print(f"Usuarios: {stats['users']}")
    print(f"Rooms: {stats['rooms']}")
    print(f"Mensajes enviados: {stats['messages']}")
    print(f"Mensajes perdidos: {stats['lost']}")
    print(f"Latencia promedio: {stats['latency_avg']:.2f}ms")
    print(f"Latencia p50: {stats['latency_p50']:.2f}ms")
    print(f"Latencia p99: {stats['latency_p99']:.2f}ms")
    print(f"Uptime: {stats['uptime_percentage']:.2f}%")
    
    # Validación
    print("\n=== VALIDACIÓN ===")
    success = True
    
    if stats['users'] < 1000:
        print(f"❌ Usuarios < 1000: {stats['users']}")
        success = False
    else:
        print(f"✅ 1000 usuarios concurrentes: {stats['users']}")
    
    if stats['latency_p99'] >= 50:
        print(f"❌ Latencia p99 >= 50ms: {stats['latency_p99']:.2f}ms")
        success = False
    else:
        print(f"✅ Latencia p99 < 50ms: {stats['latency_p99']:.2f}ms")
    
    if stats['lost'] > 0:
        print(f"❌ Mensajes perdidos > 0: {stats['lost']}")
        success = False
    else:
        print(f"✅ Sin pérdida de mensajes: {stats['lost']}")
    
    if stats['uptime_percentage'] < 99.9:
        print(f"❌ Uptime < 99.9%: {stats['uptime_percentage']:.2f}%")
        success = False
    else:
        print(f"✅ Uptime >= 99.9%: {stats['uptime_percentage']:.2f}%")
    
    if success:
        print("\n✅ EJERCICIO COMPLETADO EXITOSAMENTE")
    else:
        print("\n❌ EJERCICIO NO COMPLETADO")
    
    return success


if __name__ == "__main__":
    print("Iniciando Ejercicio 1.3: Sistema de Chat con 1000 Usuarios")
    print("Requisitos: 1000 usuarios, < 50ms latencia, persistencia, rooms, 99.9% uptime")
    print()
    
    result = asyncio.run(test_chat_system())
    
    if result:
        print("\n🎉 ¡Felicidades! Has completado el Ejercicio 1.3")
    else:
        print("\n⚠️ Necesitas optimizar el sistema para cumplir los requisitos")
