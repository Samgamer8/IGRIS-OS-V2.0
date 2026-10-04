"""User Model: Construye un modelo profundo del usuario a través de sesiones."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class UserPreference(str, Enum):
    """Preferencias del usuario."""
    CODE_STYLE = "code_style"
    RESPONSE_LENGTH = "response_length"
    DETAIL_LEVEL = "detail_level"
    LANGUAGE = "language"
    FRAMEWORK_PREFERENCE = "framework_preference"


@dataclass(frozen=True, slots=True)
class UserSession:
    """Sesión de interacción con el usuario."""
    session_id: str
    start_time: str
    end_time: str
    tasks: list[str]
    outcomes: list[str]
    preferences: dict[str, Any]
    feedback: list[str] = field(default_factory=list)


@dataclass(slots=True)
class UserProfile:
    """Perfil del usuario construido a través del tiempo."""
    user_id: str
    preferences: dict[str, Any]
    common_patterns: list[str]
    success_factors: list[str]
    failure_factors: list[str]
    total_sessions: int
    last_updated: str


class UserModel:
    """Construye y mantiene un modelo del usuario."""

    def __init__(self, storage_path: Path, user_id: str = "default") -> None:
        self.storage_path = storage_path.resolve()
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.user_id = user_id
        
        self.sessions_file = self.storage_path / f"user_sessions_{user_id}.jsonl"
        self.profile_file = self.storage_path / f"user_profile_{user_id}.json"
        
        self._sessions: list[UserSession] = []
        self._profile: UserProfile | None = None
        
        self._load_sessions()
        self._load_profile()
        
        logger.info(f"UserModel inicializado para usuario {user_id} en {storage_path}")

    def record_session(self, session: UserSession) -> None:
        """Registrar una sesión del usuario."""
        self._sessions.append(session)
        
        # Persistir sesión
        with self.sessions_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "session_id": session.session_id,
                "start_time": session.start_time,
                "end_time": session.end_time,
                "tasks": session.tasks,
                "outcomes": session.outcomes,
                "preferences": session.preferences,
                "feedback": session.feedback,
            }, ensure_ascii=False) + "\n")
        
        # Actualizar perfil
        self._update_profile(session)
        
        logger.debug(f"Sesión registrada: {session.session_id}")

    def get_profile(self) -> UserProfile:
        """Obtener el perfil actual del usuario."""
        if self._profile is None:
            # Crear perfil por defecto
            self._profile = UserProfile(
                user_id=self.user_id,
                preferences={},
                common_patterns=[],
                success_factors=[],
                failure_factors=[],
                total_sessions=0,
                last_updated=datetime.now(timezone.utc).isoformat(),
            )
        return self._profile

    def predict_preference(self, preference_key: str) -> Any:
        """Predecir una preferencia del usuario basada en historial."""
        profile = self.get_profile()
        
        if preference_key in profile.preferences:
            return profile.preferences[preference_key]
        
        # Inferir de patrones comunes
        if preference_key == "code_style":
            if "functional" in profile.common_patterns:
                return "functional"
            elif "object_oriented" in profile.common_patterns:
                return "object_oriented"
            return "balanced"
        
        if preference_key == "detail_level":
            if "verbose" in profile.common_patterns:
                return "high"
            elif "concise" in profile.common_patterns:
                return "low"
            return "medium"
        
        return None

    def get_success_factors(self) -> list[str]:
        """Obtener factores que contribuyen al éxito del usuario."""
        profile = self.get_profile()
        return profile.success_factors

    def get_failure_factors(self) -> list[str]:
        """Obtener factores que contribuyen al fracaso del usuario."""
        profile = self.get_profile()
        return profile.failure_factors

    def _update_profile(self, session: UserSession) -> None:
        """Actualizar el perfil del usuario con nueva sesión."""
        current_profile = self.get_profile()
        
        # Actualizar preferencias
        for key, value in session.preferences.items():
            current_profile.preferences[key] = value
        
        # Analizar outcomes para identificar factores
        success_tasks = [
            task for task, outcome in zip(session.tasks, session.outcomes)
            if outcome == "success"
        ]
        failure_tasks = [
            task for task, outcome in zip(session.tasks, session.outcomes)
            if outcome == "failure"
        ]
        
        # Actualizar factores de éxito
        if success_tasks:
            for task in success_tasks:
                if task not in current_profile.success_factors:
                    current_profile.success_factors.append(task)
        
        # Actualizar factores de fracaso
        if failure_tasks:
            for task in failure_tasks:
                if task not in current_profile.failure_factors:
                    current_profile.failure_factors.append(task)
        
        # Detectar patrones comunes
        self._detect_patterns(session, current_profile)
        
        # Actualizar metadatos
        current_profile.total_sessions = len(self._sessions)
        current_profile.last_updated = datetime.now(timezone.utc).isoformat()
        
        self._profile = current_profile
        self._save_profile()

    def _detect_patterns(self, session: UserSession, profile: UserProfile) -> None:
        """Detectar patrones en la sesión del usuario."""
        # Detectar patrones de tareas
        task_types = [task.split("_")[0] for task in session.tasks]
        
        for task_type in task_types:
            pattern = f"{task_type}_focused"
            if pattern not in profile.common_patterns:
                if task_types.count(task_type) > 1:
                    profile.common_patterns.append(pattern)
        
        # Detectar patrones de feedback
        for feedback in session.feedback:
            if "verbose" in feedback.lower():
                if "verbose" not in profile.common_patterns:
                    profile.common_patterns.append("verbose")
            elif "concise" in feedback.lower():
                if "concise" not in profile.common_patterns:
                    profile.common_patterns.append("concise")

    def _load_sessions(self) -> None:
        """Cargar sesiones desde disco."""
        if not self.sessions_file.exists():
            return
        
        for line in self.sessions_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                self._sessions.append(UserSession(**data))
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.warning(f"Error cargando sesión: {e}")

    def _load_profile(self) -> None:
        """Cargar perfil desde disco."""
        if not self.profile_file.exists():
            return
        
        try:
            data = json.loads(self.profile_file.read_text(encoding="utf-8"))
            self._profile = UserProfile(**data)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Error cargando perfil: {e}")

    def _save_profile(self) -> None:
        """Guardar perfil a disco."""
        if self._profile:
            data = {
                "user_id": self._profile.user_id,
                "preferences": self._profile.preferences,
                "common_patterns": self._profile.common_patterns,
                "success_factors": self._profile.success_factors,
                "failure_factors": self._profile.failure_factors,
                "total_sessions": self._profile.total_sessions,
                "last_updated": self._profile.last_updated,
            }
            self.profile_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_user_summary(self) -> dict[str, Any]:
        """Obtener resumen del usuario."""
        profile = self.get_profile()
        
        return {
            "user_id": self.user_id,
            "total_sessions": len(self._sessions),
            "preferences": profile.preferences,
            "common_patterns": profile.common_patterns,
            "success_factors": profile.success_factors,
            "failure_factors": profile.failure_factors,
            "last_activity": profile.last_updated,
        }
