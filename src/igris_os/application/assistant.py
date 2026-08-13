from dataclasses import dataclass

from igris_os.ai import OllamaClient
from igris_os.application.director import MissionDirector
from igris_os.domain import Mission, MissionBranch


SYSTEM = """Eres IGRIS OS V2.O, asistente local directo y preciso.
No afirmes haber ejecutado acciones que no ejecutaste. Distingue plan, resultado
y evidencia. Si falta una herramienta, dilo. Responde en el idioma del usuario."""


@dataclass(frozen=True, slots=True)
class AssistantReply:
    ok: bool
    text: str
    model: str = ""


class AssistantService:
    def __init__(self, client: OllamaClient | None = None) -> None:
        self.client = client or OllamaClient()
        self.director = MissionDirector()

    def choose_model(self, branch: MissionBranch) -> str:
        installed = self.client.models()
        preferred = (
            ("qwen2.5-coder:14b", "qwen2.5-coder:7b", "qwen2.5-coder:latest")
            if branch in {MissionBranch.PROGRAMMING, MissionBranch.GAMES,
                          MissionBranch.ARTIFICIAL_INTELLIGENCE}
            else ("llama3.1:8b", "llama3.1:latest", "llama3.2:latest")
        )
        return next((name for name in preferred if name in installed),
                    installed[0] if installed else "")

    def respond(self, objective: str,
                context: tuple[str, ...] = ()) -> AssistantReply:
        if not objective.strip():
            return AssistantReply(False, "Escribe una orden.")
        plan = self.director.plan(Mission(objective))
        model = self.choose_model(plan.branch)
        if not model:
            return AssistantReply(
                False, "Ollama no esta disponible o no tiene modelos instalados.")
        memory = "\n".join(context[-8:])
        prompt = (SYSTEM + "\nRAMA: " + plan.branch.value +
                  ("\nCONTEXTO LOCAL VERIFICADO:\n" + memory if memory else "") +
                  "\nORDEN DEL USUARIO:\n" + objective)
        reply = self.client.generate(prompt, model)
        return AssistantReply(reply.ok, reply.text if reply.ok else reply.error, model)
