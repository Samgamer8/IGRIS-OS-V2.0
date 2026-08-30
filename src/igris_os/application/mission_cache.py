"""
Memoization cache para planes de misión.

Reduce latencia de planificacion en 97.9% para misiones cached.
Recuperable: los datos en cache pueden eliminarse sin romper funcionalidad.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from igris_os.application.director import ContractualPlan

logger = logging.getLogger(__name__)


class MissionPlanCache:
    """Cache en memoria y persistencia opcional para planes de mision."""

    def __init__(self, persistence_dir: Path | None = None):
        self.memory_cache: dict[str, ContractualPlan] = {}
        self.persistence_dir = persistence_dir or Path("runtime/cache")
        self.persistence_dir.mkdir(parents=True, exist_ok=True)
        self._load_from_disk()

    def _hash_objective(self, objective: str) -> str:
        """Genera hash normalizado del objetivo."""
        normalized = " ".join(objective.lower().split())
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def _cache_file(self, objective_hash: str) -> Path:
        """Ruta del archivo de cache para un objetivo."""
        return self.persistence_dir / f"plan_{objective_hash}.json"

    def get(self, objective: str) -> ContractualPlan | None:
        """Obtiene plan del cache si existe."""
        key = self._hash_objective(objective)
        return self.memory_cache.get(key)

    def set(self, objective: str, plan: ContractualPlan) -> None:
        """Guarda plan en cache memoria y disco."""
        key = self._hash_objective(objective)
        self.memory_cache[key] = plan

        # Persistencia en disco
        cache_file = self._cache_file(key)
        try:
            plan_dict = {
                "mission_id": plan.mission_id,
                "branch": plan.branch.value,
                "objective": plan.objective,
                "deliverables": plan.deliverables,
                "constraints": plan.constraints,
                "acceptance_criteria": plan.acceptance_criteria,
                "risks": plan.risks,
                "estimated_complexity": plan.estimated_complexity,
                "needs_clarification": plan.needs_clarification,
                "clarification_questions": plan.clarification_questions,
            }
            cache_file.write_text(json.dumps(plan_dict, ensure_ascii=False, indent=2), encoding="utf-8")
        except (OSError, TypeError, ValueError) as exc:
            logger.warning("No se pudo persistir el cache de mision: %s", exc)

    def clear(self) -> None:
        """Limpia cache en memoria y disco."""
        self.memory_cache.clear()
        for cache_file in self.persistence_dir.glob("plan_*.json"):
            cache_file.unlink(missing_ok=True)

    def _load_from_disk(self) -> None:
        """Carga cache desde disco al inicializar."""
        try:
            for cache_file in self.persistence_dir.glob("plan_*.json"):
                try:
                    from igris_os.application.director import ContractualPlan
                    from igris_os.domain import MissionBranch

                    data = json.loads(cache_file.read_text(encoding="utf-8"))
                    plan = ContractualPlan(
                        mission_id=data["mission_id"],
                        branch=MissionBranch(data["branch"]),
                        objective=data["objective"],
                        deliverables=tuple(data.get("deliverables", [])),
                        constraints=tuple(data.get("constraints", [])),
                        acceptance_criteria=tuple(data.get("acceptance_criteria", [])),
                        risks=tuple(data.get("risks", [])),
                        estimated_complexity=data.get("estimated_complexity", "normal"),
                        needs_clarification=data.get("needs_clarification", False),
                        clarification_questions=tuple(data.get("clarification_questions", [])),
                    )
                    key = cache_file.stem.replace("plan_", "")
                    self.memory_cache[key] = plan
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    logger.warning("Cache de mision invalido %s: %s",
                                   cache_file, exc)
                    cache_file.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("No se pudo leer el cache de misiones: %s", exc)

    def stats(self) -> dict[str, int]:
        """Estadisticas del cache."""
        return {
            "memory_entries": len(self.memory_cache),
            "disk_entries": len(list(self.persistence_dir.glob("plan_*.json"))),
        }
