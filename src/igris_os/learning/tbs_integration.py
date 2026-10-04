"""Integración del sistema de aprendizaje continuo con arquitectura TBS."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from igris_os.learning import ContinuousLearner, SkillEvolutionManager
from igris_os.learning.continuous_learner import LearningEvent, LearningEventType
from igris_os.multi_agent.tbs import (
    MemoryHub,
    ScoutAgent,
    BuilderAgent,
    ReviewerAgent,
    TinyButSeriousOrchestrator,
)
from igris_os.multi_agent.tbs.scout_agent import ScoutResult
from igris_os.multi_agent.tbs.builder_agent import BuilderResult
from igris_os.multi_agent.tbs.reviewer_agent import ReviewerResult

logger = logging.getLogger(__name__)


class TBSLearningIntegrator:
    """Integra el sistema de aprendizaje continuo con la arquitectura TBS."""

    def __init__(
        self,
        tbs_storage_path: Path,
        learning_storage_path: Path,
        user_id: str = "default",
    ) -> None:
        self.tbs_storage_path = tbs_storage_path
        self.learning_storage_path = learning_storage_path
        self.user_id = user_id
        
        # Inicializar componentes TBS
        self.memory_hub = MemoryHub(tbs_storage_path)
        self.scout = ScoutAgent(self.memory_hub)
        self.builder = BuilderAgent(self.memory_hub)
        self.reviewer = ReviewerAgent(self.memory_hub)
        self.orchestrator = TinyButSeriousOrchestrator(tbs_storage_path)
        
        # Inicializar componentes de aprendizaje
        self.learner = ContinuousLearner(learning_storage_path / "learner")
        self.skill_evolution = SkillEvolutionManager(learning_storage_path / "skills")
        # UserModel se inicializa bajo demanda para evitar importación circular
        
        logger.info(f"TBSLearningIntegrator inicializado para usuario {user_id}")

    def execute_workflow_with_learning(
        self,
        objective: str,
        max_iterations: int = 3,
        record_session: bool = True,
    ) -> dict[str, Any]:
        """Ejecutar workflow TBS con aprendizaje continuo."""
        logger.info(f"Ejecutando workflow con aprendizaje: {objective[:50]}...")
        
        # Ejecutar workflow TBS
        tbs_result = self.orchestrator.execute_workflow(
            objective=objective,
            max_iterations=max_iterations,
        )
        
        # Aprender de los resultados
        learning_data = self._extract_learning_data(tbs_result)
        self._record_learning(learning_data)
        
        # Actualizar evolución de skills
        self._update_skill_evolution(tbs_result)
        
        # Registrar sesión del usuario si se solicita
        if record_session:
            self._record_user_session(objective, tbs_result, learning_data)
        
        # Generar insights
        insights = self.learner.get_insights(limit=5)
        
        return {
            "tbs_result": {
                "success": tbs_result.success,
                "final_stage": tbs_result.final_stage.value,
                "handoffs_performed": tbs_result.handoffs_performed,
                "total_duration_seconds": tbs_result.total_duration_seconds,
            },
            "learning_summary": self.learner.get_learning_summary(),
            "skill_evolution": self.skill_evolution.get_evolution_summary(),
            "user_profile": self.user_model.get_user_summary(),
            "insights": [i.recommendation for i in insights],
        }

    def _extract_learning_data(self, tbs_result) -> dict[str, Any]:
        """Extraer datos de aprendizaje del resultado TBS."""
        tasks_completed = 0
        tasks_failed = 0
        skills_used = []
        skill_success = {}
        
        # Analizar resultados de Scout
        for result in tbs_result.scout_results:
            if result.success:
                tasks_completed += 1
                skills_used.append("competitive_analysis")
                skill_success["competitive_analysis"] = True
            else:
                tasks_failed += 1
                skills_used.append("competitive_analysis")
                skill_success["competitive_analysis"] = False
        
        # Analizar resultados de Builder
        for result in tbs_result.builder_results:
            if result.success:
                tasks_completed += 1
                skills_used.append("feature_delivery")
                skill_success["feature_delivery"] = True
            else:
                tasks_failed += 1
                skills_used.append("feature_delivery")
                skill_success["feature_delivery"] = False
        
        # Analizar resultados de Reviewer
        for result in tbs_result.reviewer_results:
            if result.success:
                tasks_completed += 1
                skills_used.append("launch_checklist")
                skill_success["launch_checklist"] = True
            else:
                tasks_failed += 1
                skills_used.append("launch_checklist")
                skill_success["launch_checklist"] = False
        
        return {
            "tasks_completed": tasks_completed,
            "tasks_failed": tasks_failed,
            "skills_used": skills_used,
            "skill_success": skill_success,
            "total_handoffs": tbs_result.handoffs_performed,
            "success": tbs_result.success,
        }

    def _record_learning(self, learning_data: dict[str, Any]) -> None:
        """Registrar datos de aprendizaje."""
        # Registrar evento de tarea completada
        event = LearningEvent(
            event_type=LearningEventType.TASK_COMPLETED if learning_data["success"] else LearningEventType.TASK_FAILED,
            context={
                "skills_used": learning_data["skills_used"],
                "handoffs": learning_data["total_handoffs"],
            },
            outcome="success" if learning_data["success"] else "failure",
            metadata=learning_data,
        )
        self.learner.record_event(event)
        
        # Aprender de la sesión
        self.learner.learn_from_session(learning_data)

    def _update_skill_evolution(self, tbs_result) -> None:
        """Actualizar evolución de skills basada en resultados TBS."""
        # Actualizar skill de competitive_analysis
        for result in tbs_result.scout_results:
            self.skill_evolution.record_skill_usage(
                "competitive_analysis",
                "scout_analysis",
                success=result.success,
            )
        
        # Actualizar skill de feature_delivery
        for result in tbs_result.builder_results:
            self.skill_evolution.record_skill_usage(
                "feature_delivery",
                "builder_implementation",
                success=result.success,
            )
        
        # Actualizar skill de launch_checklist
        for result in tbs_result.reviewer_results:
            self.skill_evolution.record_skill_usage(
                "launch_checklist",
                "reviewer_validation",
                success=result.success,
            )

    def _get_user_model(self) -> Any:
        """Obtener instancia de UserModel (lazy initialization)."""
        from igris_os.learning.user_model import UserModel
        return UserModel(self.learning_storage_path / "user", user_id=self.user_id)

    def _record_user_session(self, objective: str, tbs_result, learning_data: dict[str, Any]) -> None:
        """Registrar sesión del usuario."""
        from igris_os.learning.user_model import UserSession
        from datetime import datetime, timezone
        
        # Obtener instancia de UserModel
        user_model = self._get_user_model()
        
        now = datetime.now(timezone.utc)
        
        tasks = []
        outcomes = []
        
        for result in tbs_result.scout_results:
            tasks.append(f"scout_{result.task_type.value}")
            outcomes.append("success" if result.success else "failure")
        
        for result in tbs_result.builder_results:
            tasks.append(f"builder_{result.task_type.value}")
            outcomes.append("success" if result.success else "failure")
        
        for result in tbs_result.reviewer_results:
            tasks.append(f"reviewer_{result.task_type.value}")
            outcomes.append("success" if result.success else "failure")
        
        session = UserSession(
            session_id=f"session_{now.strftime('%Y%m%d_%H%M%S')}",
            start_time=now.isoformat(),
            end_time=now.isoformat(),
            tasks=tasks,
            outcomes=outcomes,
            preferences={
                "objective": objective,
                "success_rate": learning_data["tasks_completed"] / (learning_data["tasks_completed"] + learning_data["tasks_failed"]) if learning_data["tasks_completed"] + learning_data["tasks_failed"] > 0 else 0.0,
            },
            feedback=[],
        )
        
        self.user_model.record_session(session)

    def get_learning_recommendations(self) -> list[str]:
        """Obtener recomendaciones basadas en aprendizaje."""
        recommendations = []
        
        # Obtener insights del learner
        insights = self.learner.get_insights(limit=10)
        for insight in insights:
            if insight.actionable:
                recommendations.append(insight.recommendation)
        
        # Obtener sugerencias de evolución de skills
        skills = ["competitive_analysis", "feature_delivery", "launch_checklist"]
        for skill in skills:
            suggestions = self.skill_evolution.suggest_improvements(skill)
            recommendations.extend(suggestions)
        
        # Obtener factores de éxito del usuario
        success_factors = self.user_model.get_success_factors()
        if success_factors:
            recommendations.append(f"Factores de éxito identificados: {', '.join(success_factors[:3])}")
        
        return recommendations[:10]

    def get_comprehensive_summary(self) -> dict[str, Any]:
        """Obtener resumen completo del sistema integrado."""
        return {
            "tbs_memory_hub": {
                "handoffs": self.memory_hub.get_recent_handoffs(limit=10),
                "skills": {
                    "competitive_analysis": self.memory_hub.get_skill("competitive_analysis"),
                    "feature_delivery": self.memory_hub.get_skill("feature_delivery"),
                    "launch_checklist": self.memory_hub.get_skill("launch_checklist"),
                },
            },
            "continuous_learning": self.learner.get_learning_summary(),
            "skill_evolution": self.skill_evolution.get_evolution_summary(),
            "user_model": self.user_model.get_user_summary(),
            "recommendations": self.get_learning_recommendations(),
        }
