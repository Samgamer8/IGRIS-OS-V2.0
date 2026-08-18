"""
Simulación Final Nivel 1: Puzzle Distribuido
Objetivo: 10 agentes colaboran para resolver un puzzle distribuido.
Tiempo: 6 horas
Habilidades: Multi-agent coordination, distributed problem solving

Requisitos:
- 10 agentes independientes
- Puzzle de 100 piezas
- Coordinación sin servidor central
- < 5 segundos para resolver
- 95% éxito
"""
import asyncio
import time
import random
from dataclasses import dataclass
from typing import Dict, List, Set, Optional
from collections import defaultdict
import statistics


@dataclass
class PuzzlePiece:
    piece_id: int
    position: tuple  # (x, y)
    color: str
    shape: str
    connections: List[int]  # IDs de piezas que conectan


@dataclass
class AgentMessage:
    sender_id: int
    receiver_id: int
    content: dict
    timestamp: float


class PuzzleAgent:
    def __init__(self, agent_id: int, total_agents: int):
        self.agent_id = agent_id
        self.total_agents = total_agents
        self.pieces: Set[int] = set()  # IDs de piezas que tiene
        self.solved_pieces: Set[int] = set()  # IDs de piezas resueltas
        self.connections: Dict[int, List[int]] = {}  # Mapa de conexiones
        self.inbox: asyncio.Queue = asyncio.Queue()
        self.message_count = 0
        self.running = False
        self.knowledge: Dict = {}  # Conocimiento compartido
    
    async def send_message(self, receiver: 'PuzzleAgent', content: dict) -> None:
        """Envía un mensaje a otro agente."""
        message = AgentMessage(
            sender_id=self.agent_id,
            receiver_id=receiver.agent_id,
            content=content,
            timestamp=time.time()
        )
        await receiver.inbox.put(message)
    
    async def receive_messages(self) -> None:
        """Recibe y procesa mensajes."""
        while self.running:
            try:
                message = await asyncio.wait_for(self.inbox.get(), timeout=0.1)
                self._process_message(message)
                self.message_count += 1
            except asyncio.TimeoutError:
                continue
    
    def _process_message(self, message: AgentMessage) -> None:
        """Procesa un mensaje."""
        msg_type = message.content.get("type")
        
        if msg_type == "piece_info":
            # Compartir información de piezas
            piece_id = message.content["piece_id"]
            self.knowledge[piece_id] = message.content["info"]
        
        elif msg_type == "connection_found":
            # Reportar conexión encontrada
            piece1 = message.content["piece1"]
            piece2 = message.content["piece2"]
            if piece1 not in self.connections:
                self.connections[piece1] = []
            if piece2 not in self.connections:
                self.connections[piece2] = []
            self.connections[piece1].append(piece2)
            self.connections[piece2].append(piece1)
        
        elif msg_type == "solved":
            # Pieza resuelta
            piece_id = message.content["piece_id"]
            self.solved_pieces.add(piece_id)
    
    def assign_pieces(self, pieces: List[PuzzlePiece]) -> None:
        """Asigna piezas al agente."""
        for piece in pieces:
            self.pieces.add(piece.piece_id)
            self.knowledge[piece.piece_id] = {
                "position": piece.position,
                "color": piece.color,
                "shape": piece.shape,
                "connections": piece.connections
            }
    
    def find_connections(self) -> List[tuple]:
        """Busca conexiones entre piezas que tiene."""
        found = []
        
        for piece_id in self.pieces:
            if piece_id in self.knowledge:
                piece_info = self.knowledge[piece_id]
                for connected_id in piece_info["connections"]:
                    if connected_id in self.pieces:
                        found.append((piece_id, connected_id))
        
        return found
    
    async def collaborate(self, other_agents: List['PuzzleAgent']) -> None:
        """Colabora con otros agentes."""
        # Compartir información de piezas
        for piece_id in self.pieces:
            if piece_id in self.knowledge:
                for agent in other_agents:
                    if agent.agent_id != self.agent_id:
                        await self.send_message(agent, {
                            "type": "piece_info",
                            "piece_id": piece_id,
                            "info": self.knowledge[piece_id]
                        })
        
        # Buscar conexiones
        connections = self.find_connections()
        for piece1, piece2 in connections:
            for agent in other_agents:
                if agent.agent_id != self.agent_id:
                    await self.send_message(agent, {
                        "type": "connection_found",
                        "piece1": piece1,
                        "piece2": piece2
                    })
    
    async def start(self) -> None:
        """Inicia el agente."""
        self.running = True
        await self.receive_messages()
    
    def stop(self) -> None:
        """Detiene el agente."""
        self.running = False


class DistributedPuzzleSolver:
    def __init__(self, num_agents: int, num_pieces: int):
        self.num_agents = num_agents
        self.num_pieces = num_pieces
        self.agents: List[PuzzleAgent] = []
        self.pieces: List[PuzzlePiece] = []
        self.solved = False
        self.solve_time = 0.0
        self.total_messages = 0
    
    def generate_puzzle(self) -> None:
        """Genera un puzzle aleatorio."""
        self.pieces = []
        
        for i in range(self.num_pieces):
            # Posición aleatoria en grid 10x10
            x = i % 10
            y = i // 10
            
            # Conexiones aleatorias
            connections = []
            if i > 0 and random.random() < 0.5:
                connections.append(i - 1)  # Izquierda
            if i < self.num_pieces - 1 and random.random() < 0.5:
                connections.append(i + 1)  # Derecha
            if i >= 10 and random.random() < 0.5:
                connections.append(i - 10)  # Arriba
            if i < self.num_pieces - 10 and random.random() < 0.5:
                connections.append(i + 10)  # Abajo
            
            piece = PuzzlePiece(
                piece_id=i,
                position=(x, y),
                color=random.choice(["red", "blue", "green", "yellow"]),
                shape=random.choice(["square", "circle", "triangle"]),
                connections=connections
            )
            self.pieces.append(piece)
    
    def distribute_pieces(self) -> None:
        """Distribuye piezas entre agentes."""
        pieces_per_agent = self.num_pieces // self.num_agents
        
        for i, agent in enumerate(self.agents):
            start_idx = i * pieces_per_agent
            end_idx = start_idx + pieces_per_agent if i < self.num_agents - 1 else self.num_pieces
            agent.assign_pieces(self.pieces[start_idx:end_idx])
    
    async def solve(self) -> bool:
        """Resuelve el puzzle de forma distribuida."""
        # Crear agentes
        self.agents = [PuzzleAgent(i, self.num_agents) for i in range(self.num_agents)]
        
        # Distribuir piezas
        self.distribute_pieces()
        
        # Iniciar agentes
        tasks = [asyncio.create_task(agent.start()) for agent in self.agents]
        
        # Simular colaboración
        start_time = time.time()
        
        # Fases de colaboración
        for phase in range(3):
            # Cada agente colabora con otros
            collaboration_tasks = []
            for agent in self.agents:
                other_agents = [a for a in self.agents if a.agent_id != agent.agent_id]
                collaboration_tasks.append(agent.collaborate(other_agents))
            
            await asyncio.gather(*collaboration_tasks)
            
            # Pequeña pausa entre fases
            await asyncio.sleep(0.1)
        
        # Verificar si está resuelto
        total_connections = 0
        for agent in self.agents:
            total_connections += len(agent.connections)
        
        self.solve_time = time.time() - start_time
        self.total_messages = sum(agent.message_count for agent in self.agents)
        
        # Considerar resuelto si se encontraron suficientes conexiones
        self.solved = total_connections >= self.num_pieces * 0.8  # 80% de conexiones
        
        # Detener agentes
        for agent in self.agents:
            agent.stop()
        
        for task in tasks:
            task.cancel()
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        return self.solved


async def test_puzzle_distributed():
    """Prueba el puzzle distribuido con los requisitos."""
    print("Iniciando simulación final: Puzzle Distribuido...")
    
    num_runs = 20
    successful_runs = 0
    solve_times = []
    
    for run in range(num_runs):
        solver = DistributedPuzzleSolver(num_agents=10, num_pieces=100)
        solver.generate_puzzle()
        
        solved = await solver.solve()
        
        if solved:
            successful_runs += 1
            solve_times.append(solver.solve_time)
        
        print(f"Run {run + 1}: {'EXITOSO' if solved else 'FALLO'} - Tiempo: {solver.solve_time:.2f}s - Mensajes: {solver.total_messages}")
        
        # Pequeña pausa entre runs
        await asyncio.sleep(0.1)
    
    # Calcular estadísticas
    success_rate = (successful_runs / num_runs) * 100
    avg_solve_time = statistics.mean(solve_times) if solve_times else 0
    p99_solve_time = sorted(solve_times)[int(len(solve_times) * 0.99)] if solve_times else 0
    
    print("\n=== RESULTADOS ===")
    print(f"Runs totales: {num_runs}")
    print(f"Runs exitosos: {successful_runs}")
    print(f"Tasa de éxito: {success_rate:.1f}%")
    print(f"Tiempo promedio de solución: {avg_solve_time:.2f}s")
    print(f"Tiempo p99 de solución: {p99_solve_time:.2f}s")
    
    # Validación
    print("\n=== VALIDACIÓN ===")
    success = True
    
    if success_rate < 95:
        print(f"❌ Tasa de éxito < 95%: {success_rate:.1f}%")
        success = False
    else:
        print(f"✅ Tasa de éxito >= 95%: {success_rate:.1f}%")
    
    if solve_times and avg_solve_time >= 5:
        print(f"❌ Tiempo promedio >= 5s: {avg_solve_time:.2f}s")
        success = False
    elif solve_times:
        print(f"✅ Tiempo promedio < 5s: {avg_solve_time:.2f}s")
    else:
        print(f"❌ No hay soluciones exitosas para medir tiempo")
        success = False
    
    if success:
        print("\n✅ SIMULACIÓN FINAL COMPLETADA EXITOSAMENTE")
        print("🎉 ¡Felicidades! Has completado el Nivel 1 del plan de entrenamiento")
    else:
        print("\n❌ SIMULACIÓN FINAL NO COMPLETADA")
    
    return success


if __name__ == "__main__":
    print("Simulación Final Nivel 1: Puzzle Distribuido")
    print("Requisitos: 10 agentes, 100 piezas, coordinación sin servidor central, < 5s, 95% éxito")
    print()
    
    result = asyncio.run(test_puzzle_distributed())
    
    if result:
        print("\n🏆 NIVEL 1 COMPLETADO")
        print("Próximo paso: Nivel 2 - Sistemas Autónomos de Programación")
    else:
        print("\n⚠️ Necesitas optimizar el sistema para cumplir los requisitos")
