"""Skill Evolution: Sistema que mejora habilidades con el uso."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SkillVersion:
    """Versión de una habilidad."""
    version: str
    code: str
    success_rate: float
    usage_count: int
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(slots=True)
class SkillEvolution:
    """Evolución de una habilidad a través del tiempo."""
    skill_name: str
    versions: list[SkillVersion]
    current_version: str
    total_usage: int
    improvement_rate: float


class SkillEvolutionManager:
    """Gestiona la evolución de habilidades basada en uso."""

    def __init__(self, storage_path: Path) -> None:
        self.storage_path = storage_path.resolve()
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.skills_file = self.storage_path / "skill_evolution.json"
        
        self._skills: dict[str, SkillEvolution] = {}
        self._load_skills()
        
        logger.info(f"SkillEvolutionManager inicializado en {storage_path}")

    def record_skill_usage(self, skill_name: str, code: str, success: bool) -> None:
        """Registrar uso de una habilidad."""
        if skill_name not in self._skills:
            # Nueva habilidad
            version = SkillVersion(
                version="1.0.0",
                code=code,
                success_rate=1.0 if success else 0.0,
                usage_count=1,
            )
            self._skills[skill_name] = SkillEvolution(
                skill_name=skill_name,
                versions=[version],
                current_version="1.0.0",
                total_usage=1,
                improvement_rate=0.0,
            )
        else:
            # Actualizar habilidad existente
            evolution = self._skills[skill_name]
            
            # Actualizar versión actual
            current_version = next(
                (v for v in evolution.versions if v.version == evolution.current_version),
                None
            )
            
            if current_version:
                # Calcular nueva tasa de éxito
                new_success_rate = (
                    (current_version.success_rate * current_version.usage_count + (1.0 if success else 0.0))
                    / (current_version.usage_count + 1)
                )
                
                # Si la tasa de éxito mejoró significativamente, crear nueva versión
                if new_success_rate > current_version.success_rate + 0.1:
                    new_version_num = self._increment_version(evolution.current_version)
                    new_version = SkillVersion(
                        version=new_version_num,
                        code=code,
                        success_rate=new_success_rate,
                        usage_count=1,
                    )
                    evolution.versions.append(new_version)
                    evolution.current_version = new_version_num
                    evolution.improvement_rate = new_success_rate - current_version.success_rate
                    logger.info(f"Habilidad {skill_name} mejorada a versión {new_version_num}")
                else:
                    # Actualizar versión existente
                    updated_version = SkillVersion(
                        version=current_version.version,
                        code=code,
                        success_rate=new_success_rate,
                        usage_count=current_version.usage_count + 1,
                    )
                    # Reemplazar versión actual
                    evolution.versions = [
                        v if v.version != current_version.version else updated_version
                        for v in evolution.versions
                    ]
            
            evolution.total_usage += 1
        
        self._save_skills()

    def get_best_version(self, skill_name: str) -> SkillVersion | None:
        """Obtener la mejor versión de una habilidad."""
        if skill_name not in self._skills:
            return None
        
        evolution = self._skills[skill_name]
        best = max(evolution.versions, key=lambda v: v.success_rate)
        return best

    def get_skill_evolution(self, skill_name: str) -> SkillEvolution | None:
        """Obtener evolución completa de una habilidad."""
        return self._skills.get(skill_name)

    def suggest_improvements(self, skill_name: str) -> list[str]:
        """Sugerir mejoras para una habilidad basada en su evolución."""
        if skill_name not in self._skills:
            return ["Habilidad no encontrada. Registrar uso primero."]
        
        evolution = self._skills[skill_name]
        suggestions = []
        
        if evolution.improvement_rate < 0.05:
            suggestions.append("La habilidad no ha mejorado significativamente. Considerar refactorización.")
        
        current_version = next(
            (v for v in evolution.versions if v.version == evolution.current_version),
            None
        )
        
        if current_version and current_version.success_rate < 0.7:
            suggestions.append("Tasa de éxito baja. Revisar lógica de la habilidad.")
        
        if evolution.total_usage < 10:
            suggestions.append("Uso limitado. Necesita más datos para evaluar mejora.")
        
        if not suggestions:
            suggestions.append("Habilidad funcionando bien. Mantener enfoque actual.")
        
        return suggestions

    def _increment_version(self, version: str) -> str:
        """Incrementar número de versión."""
        parts = version.split(".")
        if len(parts) != 3:
            return f"{int(parts[0]) + 1}.0.0"
        
        major, minor, patch = map(int, parts)
        return f"{major}.{minor}.{patch + 1}"

    def _load_skills(self) -> None:
        """Cargar habilidades desde disco."""
        if not self.skills_file.exists():
            return
        
        try:
            data = json.loads(self.skills_file.read_text(encoding="utf-8"))
            for skill_name, skill_data in data.items():
                versions = [
                    SkillVersion(**v) for v in skill_data["versions"]
                ]
                self._skills[skill_name] = SkillEvolution(
                    skill_name=skill_name,
                    versions=versions,
                    current_version=skill_data["current_version"],
                    total_usage=skill_data["total_usage"],
                    improvement_rate=skill_data["improvement_rate"],
                )
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Error cargando habilidades: {e}")

    def _save_skills(self) -> None:
        """Guardar habilidades a disco."""
        data = {
            skill_name: {
                "versions": [
                    {
                        "version": v.version,
                        "code": v.code,
                        "success_rate": v.success_rate,
                        "usage_count": v.usage_count,
                        "created_at": v.created_at,
                    }
                    for v in evolution.versions
                ],
                "current_version": evolution.current_version,
                "total_usage": evolution.total_usage,
                "improvement_rate": evolution.improvement_rate,
            }
            for skill_name, evolution in self._skills.items()
        }
        self.skills_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_evolution_summary(self) -> dict[str, Any]:
        """Obtener resumen de evolución de habilidades."""
        if not self._skills:
            return {"message": "Sin habilidades registradas aún"}
        
        total_skills = len(self._skills)
        total_usage = sum(e.total_usage for e in self._skills.values())
        avg_improvement = sum(e.improvement_rate for e in self._skills.values()) / total_skills
        
        improving_skills = sum(1 for e in self._skills.values() if e.improvement_rate > 0.1)
        
        return {
            "total_skills": total_skills,
            "total_usage": total_usage,
            "avg_improvement_rate": avg_improvement,
            "improving_skills": improving_skills,
            "top_skills": sorted(
                [(name, e.total_usage) for name, e in self._skills.items()],
                key=lambda x: x[1],
                reverse=True
            )[:5],
        }
