# -*- coding: utf-8 -*-
"""Bucle de debate por turnos entre dos personas de IGRIS sobre un mismo tema.

IGRIS OS e IGRIS OS ibrido comparten el mismo modelo (un unico
``llama-server.exe``), asi que esto NO es un entrenamiento real de pesos
entre dos cerebros distintos — eso exigiria un pipeline de fine-tuning
aparte (recoger transcripciones, entrenar un LoRA, sustituir el modelo).
Lo que si hace este modulo, con la arquitectura ya existente: mantiene dos
personas con system-prompts distintos turnandose sobre un tema con material
de referencia compartido (p. ej. la guia de GitHub sobre IA/Copilot), cada
una obligada a aportar algo nuevo sobre lo que dijo la otra, hasta que el
usuario decide parar. La transcripcion se persiste turno a turno (nunca se
pierde progreso si se interrumpe) y puede alimentar luego a
``SkillEvolutionManager``/``EvolutionLab`` si el debate cristaliza en una
decision de diseno concreta y verificable.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from igris_os.ai.ollama import ModelReply, OllamaClient

_DEFAULT_MANUAL_PATH = Path(__file__).with_name("resources") / "github_ai_manual.md"


def load_default_manual() -> str:
    """Devuelve el resumen local de la guia oficial de GitHub sobre IA/Copilot."""
    return _DEFAULT_MANUAL_PATH.read_text(encoding="utf-8")


@dataclass(frozen=True, slots=True)
class DebatePersona:
    """Un lado del debate: un nombre y su enfoque/prioridades."""
    name: str
    system_prompt: str


@dataclass(frozen=True, slots=True)
class DebateTurn:
    index: int
    persona: str
    message: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat())


#: Personas por defecto para el tema "interfaz eficiente / programacion
#: rapida", reflejando el enfoque real de cada proyecto.
DEFAULT_PERSONAS: tuple[DebatePersona, DebatePersona] = (
    DebatePersona(
        name="IGRIS OS",
        system_prompt=(
            "Priorizas estabilidad, cobertura de tests y un panel de "
            "control completo (galaxia/orb, cola de misiones, memoria "
            "persistente). Desconfias de atajos que compliquen mantener "
            "el sistema."),
    ),
    DebatePersona(
        name="IGRIS OS ibrido",
        system_prompt=(
            "Priorizas ligereza, arranque rapido y mezclar patrones de "
            "interfaz movil/Android con el escritorio de Windows 11 para "
            "ganar rendimiento y memoria en funciones concretas, sin tocar "
            "el panel de control compartido."),
    ),
)


class DualDebateSession:
    """Orquesta un debate por turnos entre dos personas sobre un mismo tema."""

    def __init__(self, client: OllamaClient, topic: str, *,
                 personas: tuple[DebatePersona, DebatePersona] = DEFAULT_PERSONAS,
                 reference_material: str | None = None,
                 log_path: Path, model: str = "qwen2.5-coder:7b",
                 history_window: int = 6, max_words: int = 180) -> None:
        if len(personas) != 2:
            raise ValueError("Se necesitan exactamente dos personas para el debate")
        self.client = client
        self.personas = personas
        self.topic = topic
        self.reference_material = (
            reference_material if reference_material is not None
            else load_default_manual())
        self.log_path = Path(log_path)
        self.model = model
        self.history_window = history_window
        self.max_words = max_words
        self.turns: list[DebateTurn] = []
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def _build_prompt(self, persona: DebatePersona) -> str:
        other = next(p for p in self.personas if p is not persona)
        history = self.turns[-self.history_window:]
        transcript = "\n\n".join(
            f"[{turn.persona}] {turn.message}" for turn in history)
        parts = [
            f"Eres {persona.name}. {persona.system_prompt}",
            f"Estas debatiendo con {other.name} sobre: {self.topic}",
            "Material de referencia (buenas practicas oficiales de GitHub "
            "sobre IA/Copilot, usalo para fundamentar tu postura):",
            self.reference_material,
        ]
        if transcript:
            parts.append("Transcripcion del debate hasta ahora:\n" + transcript)
            parts.append(
                f"Responde como {persona.name}. Aporta algo nuevo: refuta, "
                f"matiza o concreta lo que dijo {other.name} con una "
                f"propuesta o contrapropuesta especifica para IGRIS OS. "
                f"No repitas lo ya dicho. Maximo {self.max_words} palabras.")
        else:
            parts.append(
                f"Responde como {persona.name} abriendo el debate con una "
                f"propuesta concreta inicial. Maximo {self.max_words} palabras.")
        return "\n\n".join(parts)

    def _append_turn(self, turn: DebateTurn) -> None:
        self.turns.append(turn)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "index": turn.index, "persona": turn.persona,
                "message": turn.message, "timestamp": turn.timestamp,
            }, ensure_ascii=False) + "\n")

    def run(self, should_stop: Callable[[], bool],
             max_turns: int | None = None) -> list[DebateTurn]:
        """Alterna personas hasta que ``should_stop()`` sea True o se
        alcance ``max_turns`` (None = sin limite; el usuario decide cuando
        parar, tal como se pidio)."""
        index = len(self.turns)
        while not should_stop():
            if max_turns is not None and index >= max_turns:
                break
            persona = self.personas[index % 2]
            prompt = self._build_prompt(persona)
            reply: ModelReply = self.client.generate(prompt, self.model)
            message = (reply.text.strip() if reply.ok and reply.text.strip()
                       else f"[sin respuesta: {reply.error or 'fallo desconocido'}]")
            self._append_turn(
                DebateTurn(index=index, persona=persona.name, message=message))
            index += 1
        return list(self.turns)

    def render_markdown(self) -> str:
        """Transcripcion legible para guardar junto al .jsonl de turnos."""
        lines = [f"# Debate: {self.topic}", ""]
        for turn in self.turns:
            lines.append(f"## Turno {turn.index} — {turn.persona} ({turn.timestamp})")
            lines.append(turn.message)
            lines.append("")
        return "\n".join(lines)
