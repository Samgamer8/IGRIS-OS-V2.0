import pytest

from igris_os.application import MissionDirector
from igris_os.domain import Mission, MissionBranch


@pytest.mark.parametrize(("objective", "branch"), [
    ("crea un videojuego en Godot", MissionBranch.GAMES),
    ("edita este video con ffmpeg", MissionBranch.VIDEO),
    ("construye un programa Python", MissionBranch.PROGRAMMING),
    ("modelo de inteligencia artificial", MissionBranch.ARTIFICIAL_INTELLIGENCE),
])
def test_director_routes(objective, branch):
    assert MissionDirector().plan(Mission(objective)).branch is branch


def test_vague_objective_needs_clarification():
    assert MissionDirector().plan(Mission("hazlo")).needs_clarification
