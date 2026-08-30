import json

from igris_os.ai import ModelReply
from igris_os.games import GodotGameDeveloper


class FakeGameClient:
    def generate(self, prompt, model):
        assert "Entrega código" in prompt
        return ModelReply(True, json.dumps({"files": [
            {"path": "main.gd", "content": (
                "extends Node2D\nfunc _ready():\n    print(\"ready\")")},
            {"path": "rules.gd", "content": (
                "class_name Rules\nstatic func valid() -> bool:\n    return true")},
        ]}), model)


def test_game_developer_writes_complete_code_package(tmp_path):
    result = GodotGameDeveloper(
        FakeGameClient(), tmp_path, "test-model").develop(
            "crea un juego de ajedrez", "Ajedrez", confirmed=True)

    assert result.ok
    assert result.project is not None
    assert set(result.changed_files) == {"main.gd", "rules.gd"}
    assert (result.project / "CODE_DELIVERY.json").is_file()


def test_game_developer_rejects_explanatory_model_reply(tmp_path):
    class ChattyClient:
        def generate(self, prompt, model):
            return ModelReply(True, "Aquí tienes una explicación.", model)

    result = GodotGameDeveloper(
        ChattyClient(), tmp_path, "test-model").develop(
            "crea un juego", "Juego", confirmed=True)

    assert not result.ok
    assert "aplicable" in result.message


def test_game_developer_retries_invalid_package(tmp_path):
    class RetryClient:
        def __init__(self):
            self.calls = 0

        def generate(self, prompt, model):
            self.calls += 1
            if self.calls == 1:
                return ModelReply(True, json.dumps({"files": []}), model)
            assert "ENTREGA ANTERIOR FALLO" in prompt
            return ModelReply(True, json.dumps({"files": [{
                "path": "main.gd",
                "content": "extends Node2D\nfunc _ready():\n    pass",
            }]}), model)

    client = RetryClient()
    result = GodotGameDeveloper(client, tmp_path, "test-model").develop(
        "crea un juego", "Retry", confirmed=True)

    assert result.ok
    assert client.calls == 2


def test_game_developer_accepts_chess_3d(tmp_path):
    class ChessClient:
        def generate(self, prompt, model):
            return ModelReply(True, json.dumps({"files": [{
                "path": "main.gd",
                "content": (
                    "extends Node3D\n"
                    "func _ready():\n"
                    "    print(\"CHESS_3D_READY\")"),
            }]}), model)

    result = GodotGameDeveloper(
        ChessClient(), tmp_path, "test-model").develop(
            "crea ajedrez 3D", "Chess", genre="chess_3d", confirmed=True)

    assert result.ok, result.diagnostics
    assert result.project is not None
    assert "Node3D" in (result.project / "main.tscn").read_text(encoding="utf-8")
