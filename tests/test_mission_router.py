from igris_os.application import MissionRouter


def test_python_creation_routes_to_verified_developer():
    action = MissionRouter().route("crea un programa Python de tareas")
    assert action.capability == "programming.python.develop"
    assert action.requires_confirmation


def test_game_creation_routes_to_godot():
    action = MissionRouter().route("crea un videojuego medieval en Godot")
    assert action.capability == "games.godot.scaffold"


def test_general_request_routes_to_chat():
    assert MissionRouter().route("explica la historia").kind == "chat"
