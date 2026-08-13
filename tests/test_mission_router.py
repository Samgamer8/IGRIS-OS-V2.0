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


def test_attached_image_routes_to_resize():
    action = MissionRouter().route(
        "redimensiona esta imagen a 800x600", ["foto.png"])
    assert action.capability == "image.resize"
    assert action.payload["width"] == 800
    assert action.payload["height"] == 600
    assert action.requires_confirmation


def test_attached_video_routes_to_audio_extraction():
    action = MissionRouter().route("extrae audio", ["video.mp4"])
    assert action.capability == "multimedia.extract_audio"


def test_multiple_attachments_route_to_read_only_inspection():
    action = MissionRouter().route(
        "analiza estos archivos", ["uno.py", "dos.md"])
    assert action.capability == "files.inspect"
    assert len(action.payload["sources"]) == 2
    assert not action.requires_confirmation


def test_javascript_creation_routes_to_multilang_developer():
    action = MissionRouter().route("crea un programa JavaScript de tareas")
    assert action.capability == "programming.multilang.develop"
    assert action.payload["language"] == "javascript"


def test_capability_question_uses_real_catalog():
    action = MissionRouter().route("que puedes hacer y cuales son tus funciones")
    assert action.capability == "system.capabilities"
    assert not action.requires_confirmation
