from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True, slots=True)
class ProjectQuestion:
    key: str
    prompt: str
    choices: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ProjectContract:
    objective: str
    project_name: str
    destination: Path | None
    technology: str
    delivery: str
    acceptance: tuple[str, ...] = ()
    questions: tuple[ProjectQuestion, ...] = ()
    constraints: tuple[str, ...] = ()

    @property
    def ready(self) -> bool:
        return not self.questions


class ProjectIntake:
    """Convierte un encargo abierto en un contrato ejecutable o preguntas breves."""

    _TECHNOLOGIES = ("python", "godot", "web", "javascript", "typescript")
    _DELIVERIES = ("source", "source_and_exe", "source_and_web")

    def build(self, objective: str,
              answers: Mapping[str, object] | None = None) -> ProjectContract:
        text = objective.strip()
        if not text:
            raise ValueError("Falta el objetivo del proyecto")
        values = {str(key): str(value).strip()
                  for key, value in (answers or {}).items()
                  if str(value).strip()}
        technology = values.get("technology", "").casefold()
        delivery = values.get("delivery", "").casefold()
        destination = self._destination(values.get("destination", ""))
        acceptance = self._items(values.get("acceptance", ""))
        constraints = self._items(values.get("constraints", ""))
        questions: list[ProjectQuestion] = []
        if technology not in self._TECHNOLOGIES:
            questions.append(ProjectQuestion(
                "technology", "¿Con qué tecnología debe construirse?",
                self._TECHNOLOGIES))
        if delivery not in self._DELIVERIES:
            questions.append(ProjectQuestion(
                "delivery", "¿Qué entrega necesitas?",
                self._DELIVERIES))
        if destination is None:
            questions.append(ProjectQuestion(
                "destination", "¿En qué carpeta debo entregar el proyecto?"))
        if not acceptance:
            questions.append(ProjectQuestion(
                "acceptance", "¿Qué debe poder comprobarse al terminar?"))
        return ProjectContract(
            objective=text,
            project_name=self._project_name(values.get("name", "") or text),
            destination=destination,
            technology=technology,
            delivery=delivery,
            acceptance=acceptance,
            questions=tuple(questions),
            constraints=constraints,
        )

    @staticmethod
    def _destination(value: str) -> Path | None:
        if not value:
            return None
        path = Path(value).expanduser()
        return path.resolve() if path.is_dir() else None

    @staticmethod
    def _items(value: str) -> tuple[str, ...]:
        return tuple(item.strip() for item in value.split(";") if item.strip())

    @staticmethod
    def _project_name(value: str) -> str:
        words = re.findall(r"[A-Za-z0-9_-]+", value)
        return "_".join(words[:6]) or "proyecto_igris"