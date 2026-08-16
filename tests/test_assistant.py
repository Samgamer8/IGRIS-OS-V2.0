from igris_os.ai import ModelReply
from igris_os.application import AssistantService


class FakeClient:
    def models(self):
        return ("qwen2.5-coder:7b", "llama3.1:8b")

    def generate(self, prompt, model):
        return ModelReply(True, "Respuesta verificada", model)


def test_assistant_selects_coder_for_programming():
    result = AssistantService(FakeClient()).respond("crea programa Python")
    assert result.ok
    assert result.model == "qwen2.5-coder:7b"


def test_assistant_selects_general_model():
    result = AssistantService(FakeClient()).respond("explica la historia")
    assert result.model == "llama3.1:8b"


def test_assistant_includes_verified_context():
    class RecordingClient(FakeClient):
        prompt = ""

        def generate(self, prompt, model):
            self.prompt = prompt
            return super().generate(prompt, model)

    client = RecordingClient()
    AssistantService(client).respond(
        "continua", ("user: crea una calculadora", "igris: proyecto listo"))
    assert "CONTEXTO LOCAL VERIFICADO" in client.prompt
    assert "proyecto listo" in client.prompt


def test_run_command_rejects_unlisted_tool():
    assistant = AssistantService(FakeClient())
    out = assistant._tool_run_command("format C:")
    assert "Herramienta no permitida" in out


def test_run_command_rejects_shell_operators():
    assistant = AssistantService(FakeClient())
    out = assistant._tool_run_command("git status | more")
    assert "Operadores de shell no permitidos" in out


def test_run_command_runs_allowed_tool_without_shell():
    assistant = AssistantService(FakeClient())
    out = assistant._tool_run_command("git --version")
    assert "git version" in out


def test_system_info_runs_without_shell():
    assistant = AssistantService(FakeClient())
    out = assistant._tool_system_info("")
    assert out
    assert "sistema operativo" in out.lower() or "os" in out.lower()
