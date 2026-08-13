from dataclasses import dataclass, field
from typing import Any

from igris_os.application.director import MissionDirector
from igris_os.domain import Mission, MissionBranch


@dataclass(frozen=True, slots=True)
class RoutedAction:
    kind: str
    capability: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    requires_confirmation: bool = False


class MissionRouter:
    def route(self, objective: str) -> RoutedAction:
        plan = MissionDirector().plan(Mission(objective))
        low = objective.casefold()
        if plan.branch is MissionBranch.PROGRAMMING and "python" in low:
            return RoutedAction(
                "capability", "programming.python.develop",
                {"objective": objective}, True)
        if plan.branch is MissionBranch.GAMES and any(
                word in low for word in ("crea", "construye", "genera")):
            return RoutedAction(
                "capability", "games.godot.scaffold",
                {"name": _project_name(objective)}, True)
        return RoutedAction("chat")


def _project_name(objective: str) -> str:
    words = [word.strip(".,;:!?") for word in objective.split()]
    ignored = {"crea", "construye", "genera", "un", "una", "juego",
               "videojuego", "en", "godot"}
    useful = [word for word in words if word.casefold() not in ignored]
    return " ".join(useful[:5]) or "Juego IGRIS"
