from igris_os.ai import ModelReply
from igris_os.application import AssistantService
from igris_os.application import assistant as assistant_module
from igris_os.application.assistant import is_conversational_input


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
    assert result.model == "qwen2.5-coder:7b"


def test_natural_greetings_use_dynamic_model_response():
    client = FakeClient()
    result = AssistantService(client).respond("¿Qué tal estás?")
    assert result.ok
    assert result.text == "Respuesta verificada"
    assert is_conversational_input("como estas?")
    assert is_conversational_input("que tal te encuentras?")
    assert is_conversational_input("¿ya no respondes?")
    assert is_conversational_input("un poco la misma respuesta, ¿no crees?")
    assert is_conversational_input(
        "tus dialogos son entrecortados y con forma poco logica, revisalo. "
        "tu sintaxis de las palabras es erronea, ¿no crees?")
    assert is_conversational_input("La información precisa es importante.")
    assert is_conversational_input("explica la historia")
    assert not is_conversational_input("construye un juego")
    assert not is_conversational_input(
        "podrias hacerme un juego de ajedrez con reglas y piezas medievales")


def test_short_conversation_skips_mission_planning():
    class NoPlanningAssistant(AssistantService):
        def __init__(self, client):
            super().__init__(client)
            self.director = None

    result = NoPlanningAssistant(FakeClient()).respond("que opinas de esto")
    assert result.ok
    assert result.text == "Respuesta verificada"


def test_short_conversation_does_not_probe_models_first():
    class CountingClient(FakeClient):
        model_calls = 0

        def models(self):
            self.model_calls += 1
            return super().models()

    client = CountingClient()
    result = AssistantService(client).respond("que opinas de esto")
    assert result.ok
    assert client.model_calls == 0


def test_conversation_keeps_structured_turns():
    assistant = AssistantService(FakeClient())
    assistant.respond("hola")
    assistant.respond("¿ya no respondes?")
    turns = list(assistant.state.turns)
    assert [(turn.role, turn.text) for turn in turns] == [
        ("user", "hola"),
        ("assistant", "Respuesta verificada"),
        ("user", "¿ya no respondes?"),
        ("assistant", "Respuesta verificada"),
    ]


def test_conversation_prompt_discourages_support_template():
    prompt = AssistantService._conversation_prompt(
        "que tal te encuentras?", ("user: hola", "assistant: Hola",))
    assert "No termines cada respuesta" in prompt
    assert "¿En que puedo ayudarte?" in prompt
    assert "Tu identidad es IGRIS OS" in prompt
    assert "No digas que eres Alibaba" in prompt
    assert "no puedes crear archivos" in prompt


def test_engineering_contract_requires_evidence_and_critique():
    assert "HECHO VERIFICADO" in assistant_module.SYSTEM
    assert "INFERENCIA" in assistant_module.SYSTEM
    assert "PRUEBA NECESARIA" in assistant_module.SYSTEM
    assert "copiloto senior y critico" in assistant_module.SYSTEM
    assert "KISS" in assistant_module.SYSTEM
    assert "O grande" in assistant_module.SYSTEM
    assert "razonamiento interno paso a paso" in assistant_module.SYSTEM


def test_conversation_model_can_be_configured(monkeypatch):
    monkeypatch.setenv("IGRIS_CONVERSATION_MODEL", "gemma4:26b")
    assert AssistantService(FakeClient())._conversation_model() == "gemma4:26b"


def test_assistant_carries_reasoning():
    class ReasoningClient(FakeClient):
        def generate(self, prompt, model):
            return ModelReply(True, "Respuesta verificada", model,
                              reasoning="pensamiento interno")

    result = AssistantService(ReasoningClient()).respond("razona esto")
    assert result.ok
    assert result.reasoning == "pensamiento interno"


def test_assistant_reuses_injected_client_for_mission_director():
    client = FakeClient()
    assistant = AssistantService(client)
    assert assistant.director.client is client


def test_assistant_includes_verified_context():
    class RecordingClient(FakeClient):
        prompt = ""

        def generate(self, prompt, model):
            self.prompt = prompt
            return super().generate(prompt, model)

    client = RecordingClient()
    AssistantService(client).respond(
        "continua", ("user: crea una calculadora", "igris: proyecto listo"))
    assert "HISTORIAL RECIENTE" in client.prompt
    assert "proyecto listo" in client.prompt


def test_exam_status_reports_real_deliveries_without_using_llm(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = FakeClient()

    result = AssistantService(client).respond("donde estan los trabajos del examen")

    assert result.ok
    assert result.model == "local"
    assert "chess_3d: NO CREADA" in result.text
    assert "pc_optimizer: NO CREADA" in result.text
    assert "control_panel: NO CREADA" in result.text


def test_chess_creation_is_not_mistaken_for_exam_status():
    result = AssistantService(FakeClient()).respond(
        "construye un juego de ajedrez medieval")

    assert "EXAMEN DE PRODUCTIVIDAD" not in result.text
    assert result.model == "qwen2.5-coder:7b"


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
