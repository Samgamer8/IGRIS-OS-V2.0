"""Continuous Learner: Bucle de aprendizaje continuo estilo Hermes."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class LearningEventType(str, Enum):
    """Tipos de eventos de aprendizaje."""
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    SKILL_USED = "skill_used"
    USER_FEEDBACK = "user_feedback"
    PATTERN_DISCOVERED = "pattern_discovered"


@dataclass(frozen=True, slots=True)
class LearningEvent:
    """Evento de aprendizaje."""
    event_type: LearningEventType
    context: dict[str, Any]
    outcome: str  # "success", "failure", "partial"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LearningInsight:
    """Insight derivado del aprendizaje."""
    pattern: str
    confidence: float
    actionable: bool
    recommendation: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ContinuousLearner:
    """Sistema de aprendizaje continuo que mejora con el uso."""

    def __init__(self, storage_path: Path) -> None:
        self.storage_path = storage_path.resolve()
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Archivos de almacenamiento
        self.events_file = self.storage_path / "learning_events.jsonl"
        self.insights_file = self.storage_path / "learning_insights.json"
        self.patterns_file = self.storage_path / "patterns.json"
        
        # Estado en memoria
        self._events: list[LearningEvent] = []
        self._insights: list[LearningInsight] = []
        self._patterns: dict[str, dict] = {}
        
        # Cargar datos existentes
        self._load_events()
        self._load_insights()
        self._load_patterns()
        
        logger.info(f"ContinuousLearner inicializado en {storage_path}")

    def record_event(self, event: LearningEvent) -> None:
        """Registrar un evento de aprendizaje."""
        self._events.append(event)
        
        # Persistir evento
        with self.events_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "event_type": event.event_type.value,
                "context": event.context,
                "outcome": event.outcome,
                "timestamp": event.timestamp,
                "metadata": event.metadata,
            }, ensure_ascii=False) + "\n")
        
        # Procesar evento para generar insights
        self._process_event(event)
        
        logger.debug(f"Evento registrado: {event.event_type.value} - {event.outcome}")

    def get_insights(self, limit: int = 10) -> list[LearningInsight]:
        """Obtener insights recientes."""
        return self._insights[-limit:]

    def get_patterns(self) -> dict[str, dict]:
        """Obtener patrones descubiertos."""
        return self._patterns.copy()

    def search_history(self, query: str, limit: int = 20) -> list[LearningEvent]:
        """Buscar en el historial de eventos."""
        query_lower = query.lower()
        matching = []
        
        for event in reversed(self._events):
            if len(matching) >= limit:
                break
            
            # Buscar en contexto y metadata
            context_str = json.dumps(event.context).lower()
            metadata_str = json.dumps(event.metadata).lower()
            
            if query_lower in context_str or query_lower in metadata_str:
                matching.append(event)
        
        return matching

    def learn_from_session(self, session_data: dict[str, Any]) -> list[LearningInsight]:
        """Aprender de una sesión completa."""
        insights = []
        
        # Analizar resultados de la sesión
        tasks_completed = session_data.get("tasks_completed", 0)
        tasks_failed = session_data.get("tasks_failed", 0)
        total_tasks = tasks_completed + tasks_failed
        
        if total_tasks > 0:
            success_rate = tasks_completed / total_tasks
            
            # Generar insight sobre tasa de éxito
            if success_rate > 0.8:
                insight = LearningInsight(
                    pattern="high_success_rate",
                    confidence=success_rate,
                    actionable=True,
                    recommendation=f"Alta tasa de éxito ({success_rate:.1%}). Mantener enfoque actual.",
                )
                insights.append(insight)
            elif success_rate < 0.5:
                insight = LearningInsight(
                    pattern="low_success_rate",
                    confidence=1.0 - success_rate,
                    actionable=True,
                    recommendation=f"Baja tasa de éxito ({success_rate:.1%}). Considerar cambiar estrategia.",
                )
                insights.append(insight)
            else:
                # Generar insight para tasas medias
                insight = LearningInsight(
                    pattern="moderate_success_rate",
                    confidence=success_rate,
                    actionable=True,
                    recommendation=f"Tasa de éxito moderada ({success_rate:.1%}). Optimizar estrategia.",
                )
                insights.append(insight)
        
        # Analizar skills usados
        skills_used = session_data.get("skills_used", [])
        for skill in skills_used:
            skill_success = session_data.get("skill_success", {}).get(skill, True)
            
            event = LearningEvent(
                event_type=LearningEventType.SKILL_USED,
                context={"skill": skill},
                outcome="success" if skill_success else "failure",
                metadata={"session_data": session_data},
            )
            self.record_event(event)
        
        # Guardar insights
        for insight in insights:
            self._insights.append(insight)
        
        self._save_insights()
        
        return insights

    def _process_event(self, event: LearningEvent) -> None:
        """Procesar evento para detectar patrones."""
        # Detectar patrones de éxito/fracaso
        if event.event_type == LearningEventType.TASK_COMPLETED:
            self._update_pattern("task_success", event.context, 1.0)
        elif event.event_type == LearningEventType.TASK_FAILED:
            self._update_pattern("task_failure", event.context, 1.0)
        
        # Detectar patrones de uso de skills
        if event.event_type == LearningEventType.SKILL_USED:
            skill_name = event.context.get("skill", "unknown")
            self._update_pattern(f"skill_usage_{skill_name}", event.context, 1.0)

    def _update_pattern(self, pattern_key: str, context: dict[str, Any], weight: float) -> None:
        """Actualizar un patrón con nuevo contexto."""
        if pattern_key not in self._patterns:
            self._patterns[pattern_key] = {
                "count": 0,
                "contexts": [],
                "success_rate": 0.0,
            }
        
        pattern = self._patterns[pattern_key]
        pattern["count"] += 1
        pattern["contexts"].append(context)
        
        # Actualizar tasa de éxito
        success_count = sum(1 for ctx in pattern["contexts"] if ctx.get("outcome") == "success")
        pattern["success_rate"] = success_count / len(pattern["contexts"])
        
        # Guardar patrones
        self._save_patterns()

    def _load_events(self) -> None:
        """Cargar eventos desde disco."""
        if not self.events_file.exists():
            return
        
        for line in self.events_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                self._events.append(LearningEvent(
                    event_type=LearningEventType(data["event_type"]),
                    context=data["context"],
                    outcome=data["outcome"],
                    timestamp=data["timestamp"],
                    metadata=data.get("metadata", {}),
                ))
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning(f"Error cargando evento: {e}")

    def _load_insights(self) -> None:
        """Cargar insights desde disco."""
        if not self.insights_file.exists():
            return
        
        try:
            data = json.loads(self.insights_file.read_text(encoding="utf-8"))
            for insight_data in data:
                self._insights.append(LearningInsight(**insight_data))
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Error cargando insights: {e}")

    def _load_patterns(self) -> None:
        """Cargar patrones desde disco."""
        if not self.patterns_file.exists():
            return
        
        try:
            self._patterns = json.loads(self.patterns_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            logger.warning(f"Error cargando patrones: {e}")

    def _save_insights(self) -> None:
        """Guardar insights a disco."""
        data = [
            {
                "pattern": insight.pattern,
                "confidence": insight.confidence,
                "actionable": insight.actionable,
                "recommendation": insight.recommendation,
                "timestamp": insight.timestamp,
            }
            for insight in self._insights
        ]
        self.insights_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _save_patterns(self) -> None:
        """Guardar patrones a disco."""
        self.patterns_file.write_text(json.dumps(self._patterns, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_learning_summary(self) -> dict[str, Any]:
        """Obtener resumen del aprendizaje."""
        if not self._events:
            return {"message": "Sin eventos de aprendizaje aún"}
        
        total_events = len(self._events)
        successes = sum(1 for e in self._events if e.outcome == "success")
        failures = sum(1 for e in self._events if e.outcome == "failure")
        
        return {
            "total_events": total_events,
            "success_rate": successes / total_events if total_events > 0 else 0.0,
            "successes": successes,
            "failures": failures,
            "insights_count": len(self._insights),
            "patterns_count": len(self._patterns),
            "recent_insights": [i.recommendation for i in self._insights[-3:]],
        }
