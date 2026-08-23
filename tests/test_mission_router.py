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
    assert action.capability == "programming.autonomous.develop"
    assert action.payload["language"] == "javascript"


def test_go_creation_routes_to_multilang_developer():
    action = MissionRouter().route("crea un programa Go de tareas")
    assert action.capability == "programming.autonomous.develop"
    assert action.payload["language"] == "go"


def test_typescript_creation_routes_to_multilang_developer():
    action = MissionRouter().route("crea un programa TypeScript de tareas")
    assert action.capability == "programming.autonomous.develop"
    assert action.payload["language"] == "typescript"


def test_capability_question_uses_real_catalog():
    action = MissionRouter().route("que puedes hacer y cuales son tus funciones")
    assert action.capability == "system.capabilities"
    assert not action.requires_confirmation


def test_accented_capability_question_is_recognized():
    assert MissionRouter().route(
        "¿qué puedes hacer?").capability == "system.capabilities"


def test_unicode_dimensions_are_recognized():
    action = MissionRouter().route(
        "redimensiona a 640×480", ["foto.png"])
    assert action.payload["width"] == 640
    assert action.payload["height"] == 480


def test_video_edit_routes_to_verified_pipeline():
    action = MissionRouter().route("edita este video", ["demo.mp4"])
    assert action.capability == "multimedia.pipeline"
    assert [step["kind"] for step in action.payload["operations"]] == [
        "thumbnail", "transcode"]
    assert action.requires_confirmation


def test_repository_folder_routes_to_deep_analysis(tmp_path):
    action = MissionRouter().route(
        "analiza este repositorio y su código", [str(tmp_path)])
    assert action.capability == "repository.analyze"
    assert action.requires_confirmation


def test_repository_work_routes_to_isolated_copy(tmp_path):
    action = MissionRouter().route(
        "prepara este proyecto para trabajar", [str(tmp_path)])
    assert action.capability == "repository.stage"


def test_repository_change_routes_to_isolated_developer(tmp_path):
    action = MissionRouter().route(
        "implementa una función nueva en este proyecto", [str(tmp_path)])
    assert action.capability == "repository.develop"
    assert action.requires_confirmation


def test_routes_specialist_coordination():
    action = MissionRouter().route(
        "coordina especialistas para diseñar una API")
    assert action.capability == "mission.coordinate"
    assert action.requires_confirmation


def test_selects_platformer_genre():
    action = MissionRouter().route(
        "crea un videojuego de plataformas en Godot")
    assert action.capability == "games.godot.scaffold"
    assert action.payload["genre"] == "platformer"


def test_game_test_routes_to_playtest():
    action = MissionRouter().route("prueba el juego")
    assert action.capability == "games.godot.playtest"
    assert action.requires_confirmation


def test_game_export_routes_to_export():
    action = MissionRouter().route("exporta el juego a ejecutable")
    assert action.capability == "games.godot.export"
    assert action.requires_confirmation


def test_voice_question_routes_to_chat_not_voice():
    action = MissionRouter().route("busco la voz de Jarvis en espanol")
    assert action.kind == "chat"


def test_listening_question_routes_to_chat_not_voice():
    action = MissionRouter().route(
        "tienes muestras de esa voz para que las escuche")
    assert action.kind == "chat"


def test_explicit_voice_command_routes_to_voice():
    action = MissionRouter().route("di algo")
    assert action.capability == "voice.set"
