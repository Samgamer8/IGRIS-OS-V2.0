import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from igris_os.ai import ModelRouter, OllamaClient
from igris_os.application.director import MissionDirector
from igris_os.domain import Mission, MissionBranch
from igris_os.memory.compressor import ContextCompressor


SYSTEM = """Eres IGRIS OS V2.O. No eres un chatbot generico: eres el operador local del sistema.

TONO:
- Directo, natural, sin relleno ni florituras.
- Primero la respuesta util, luego el detalle solo si hace falta.
- No empieces con "Hola, soy IGRIS..." cada vez.
- No repitas la orden del usuario como si no la hubieras leido.
- Evita listas interminables y frases como "en cuanto a..." o "he verificado que...".

HERRAMIENTAS:
- Puedes usar herramientas del sistema cuando el panel lo solicite: archivos, Git, multimedia, Godot, navegador/web, etc.
- Si el usuario pide algo de Internet y la herramienta esta disponible, usala.
- Si no tienes una herramienta concreta, dilo directamente, sin disculpas.
- No inventes resultados. Distingue entre lo que hiciste, lo que planeas y lo que necesitas del usuario.

EJECUCION:
- Cuando ejecutes algo, indica: que hiciste, donde quedo el resultado y que puede hacer el usuario ahora.
- Si algo falla, di la causa real y el siguiente paso, no una excusa generica.
- Si hace falta confirmacion, pidela sola.

MULTI-TURN:
- Si la respuesta requiere varias herramientas, encadena llamadas usando TOOL_CALL en cada turno.
- Limite: hasta 5 rondas de herramientas por mensaje del usuario.
- Despues de cada herramienta, observa el resultado y decide si necesitas otra.
- Cuando tengas la respuesta final, escribe el texto sin TOOL_CALL."""


@dataclass(frozen=True, slots=True)
class AssistantReply:
    ok: bool
    text: str
    model: str = ""
    tokens: int = 0


@dataclass
class ToolCallResult:
    tool_name: str
    args: str
    output: str = ""
    ok: bool = False
    error: str = ""


@dataclass
class ConversationTurn:
    role: str
    text: str
    tool_calls: List[ToolCallResult] = field(default_factory=list)


@dataclass
class ConversationState:
    turns: List[ConversationTurn] = field(default_factory=list)
    max_tool_rounds: int = 5
    summarize_every: int = 10

    def add_turn(self, role: str, text: str) -> None:
        self.turns.append(ConversationTurn(role=role, text=text))

    def add_tool_result(self, tool_name: str, args: str, output: str, ok: bool, error: str = "") -> None:
        if self.turns and self.turns[-1].role == "assistant":
            self.turns[-1].tool_calls.append(
                ToolCallResult(tool_name=tool_name, args=args, output=output, ok=ok, error=error))
        else:
            self.turns.append(ConversationTurn(role="tool", text=output,
                                               tool_calls=[ToolCallResult(tool_name=tool_name, args=args,
                                                                          output=output, ok=ok, error=error)]))

    def should_summarize(self) -> bool:
        return len(self.turns) > 0 and len(self.turns) % self.summarize_every == 0

    def recent_context(self, limit: int = 20) -> List[Dict[str, str]]:
        context = []
        for turn in self.turns[-limit:]:
            context.append({"role": turn.role, "text": turn.text})
            for tc in turn.tool_calls:
                context.append({"role": "tool", "text": f"[{tc.tool_name}] {tc.output}"})
        return context


class AssistantService:
    def __init__(self, client: OllamaClient | None = None,
                 on_tool_call: Optional[Callable[[str, str, str, bool], None]] = None) -> None:
        self.client = client or OllamaClient()
        self.director = MissionDirector()
        self.router = ModelRouter(self.client)
        self.compressor = ContextCompressor()
        self._tools: Dict[str, Callable[..., str]] = {
            "list_files": self._tool_list_files,
            "git_status": self._tool_git_status,
            "git_diff": self._tool_git_diff,
            "system_info": self._tool_system_info,
            "run_command": self._tool_run_command,
        }
        self.state = ConversationState()
        self.on_tool_call = on_tool_call

    def choose_model(self, branch: MissionBranch,
                     objective: str = "") -> str:
        code = branch in {MissionBranch.PROGRAMMING, MissionBranch.GAMES,
                          MissionBranch.ARTIFICIAL_INTELLIGENCE}
        difficulty = self.router.infer_difficulty(objective or "normal")
        return self.router.route(difficulty, code=code).model

    def _parse_messages(self, context: Tuple[str, ...]) -> List[Dict[str, str]]:
        messages: List[Dict[str, str]] = []
        for msg in context[-50:]:
            if msg.startswith(("user: ", "igris: ", "system: ", "assistant: ")):
                role, text = msg.split(": ", 1)
                messages.append({"role": role, "text": text})
            else:
                messages.append({"role": "user", "text": msg})
        return messages

    def _build_context(self, context: Tuple[str, ...]) -> str:
        recent = context[-50:]
        flat = "\n".join(recent)
        if len(flat) > 4000:
            messages = self._parse_messages(context)
            return self.compressor.compress(messages, max_tokens=500)
        return flat

    def _parse_tool_call(self, text: str) -> Optional[Tuple[str, str]]:
        match = re.match(r"TOOL_CALL:(\w+)(.*)", text.strip())
        if match:
            return match.group(1), match.group(2).strip()
        return None

    def _execute_tool(self, tool_name: str, args: str) -> str:
        fn = self._tools.get(tool_name)
        if not fn:
            return f"[ERROR] Herramienta desconocida: {tool_name}"
        try:
            return fn(args)
        except Exception as exc:
            return f"[ERROR {tool_name}] {exc}"

    def _tool_list_files(self, args: str) -> str:
        target = Path(args.strip()) if args.strip() else Path.cwd()
        if not target.exists():
            return f"Ruta no existe: {target}"
        if target.is_file():
            return f"FILE {target.name}"
        entries = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        lines = [f"{'DIR ' if p.is_dir() else 'FILE'} {p.name}" for p in entries]
        return "\n".join(lines[:100])

    def _tool_git_status(self, args: str) -> str:
        cwd = args.strip() or "."
        result = subprocess.run(["git", "status", "--short"], capture_output=True, text=True, cwd=cwd, timeout=30)
        return result.stdout.strip() or "working tree clean"

    def _tool_git_diff(self, args: str) -> str:
        cwd = args.strip() or "."
        result = subprocess.run(["git", "diff", "--stat"], capture_output=True, text=True, cwd=cwd, timeout=30)
        return result.stdout.strip() or "no changes"

    def _tool_system_info(self, args: str) -> str:
        result = subprocess.run(["systeminfo"], capture_output=True, text=True, timeout=30, shell=True)
        output = result.stdout.strip() or result.stderr.strip()
        return output[:2000] if output else "sin datos"

    def _tool_run_command(self, args: str) -> str:
        result = subprocess.run(args, capture_output=True, text=True, shell=True, timeout=60)
        out = result.stdout.strip()
        err = result.stderr.strip()
        if out and err:
            return f"STDOUT:\n{out}\nSTDERR:\n{err}"
        return out or err or "comando ejecutado sin salida"

    def _summarize_if_needed(self) -> Optional[str]:
        if not self.state.should_summarize():
            return None
        old_turns = self.state.turns[:-4] if len(self.state.turns) > 4 else self.state.turns
        if not old_turns:
            return None
        summary = self.compressor.fallback_summarize(
            [{"role": t.role, "text": t.text} for t in old_turns])
        self.state.turns = self.state.turns[len(old_turns):]
        if self.state.turns and self.state.turns[0].role == "assistant":
            self.state.turns[0].text = f"[Contexto resumido]\n{summary}\n\n" + self.state.turns[0].text
        else:
            self.state.turns.insert(0, ConversationTurn(role="system", text=f"[Contexto resumido]\n{summary}"))
        return summary

    def respond(self, objective: str,
                context: Tuple[str, ...] = ()) -> AssistantReply:
        if not objective.strip():
            return AssistantReply(False, "Escribe una orden.", "", 0)
        lower = objective.strip().lower()
        greetings = {
            "hola", "hey", "hi", "buenas", "que tal", "como estas",
            "buenos dias", "buenas tardes", "buenas noches", "buen dia",
        }
        if lower.strip("¿?!. ") in greetings:
            return AssistantReply(True, "Aqui estoy. Que necesitas?", "", 0)
        plan = self.director.plan(Mission(objective))
        model = self.choose_model(plan.branch, objective)
        if not model:
            return AssistantReply(
                False, "Ollama no esta disponible o no tiene modelos instalados.", "", 0)
        memory = self._build_context(context)
        prompt = (SYSTEM + "\nRAMA: " + plan.branch.value +
                  ("\nCONTEXTO LOCAL VERIFICADO:\n" + memory if memory else "") +
                  "\nORDEN DEL USUARIO:\n" + objective)
        reply = self.client.generate(prompt, model)
        text = reply.text if reply.ok else reply.error
        tokens = self.compressor.estimate_tokens(text)
        tool_call = self._parse_tool_call(text)
        if tool_call:
            tool_name, tool_args = tool_call
            text = self._execute_tool(tool_name, tool_args)
        return AssistantReply(reply.ok, text, model, tokens)

    def respond_agentic(self, objective: str,
                        context: Tuple[str, ...] = ()) -> AssistantReply:
        if not objective.strip():
            return AssistantReply(False, "Escribe una orden.", "", 0)
        self.state.add_turn("user", objective)
        self._summarize_if_needed()
        plan = self.director.plan(Mission(objective))
        model = self.choose_model(plan.branch, objective)
        if not model:
            return AssistantReply(False, "Ollama no esta disponible.", "", 0)
        memory = self._build_context(context)
        turns_context = self.state.recent_context(limit=20)
        history = "\n".join(f"{t['role']}: {t['text']}" for t in turns_context)
        prompt = (SYSTEM +
                  "\nRAMA: " + plan.branch.value +
                  ("\nCONTEXTO LOCAL VERIFICADO:\n" + memory if memory else "") +
                  ("\nHISTORIAL RECIENTE:\n" + history if history else "") +
                  "\nORDEN DEL USUARIO:\n" + objective)
        final_text = ""
        total_tool_rounds = 0
        current_text = ""
        for round_idx in range(self.state.max_tool_rounds):
            reply = self.client.generate(prompt + "\nRespuesta de IGRIS:", model)
            if not reply.ok:
                final_text = reply.error
                break
            current_text = reply.text.strip()
            tool_call = self._parse_tool_call(current_text)
            if not tool_call:
                final_text = current_text
                break
            tool_name, tool_args = tool_call
            output = self._execute_tool(tool_name, tool_args)
            self.state.add_tool_result(tool_name, tool_args, output, ok=True)
            if self.on_tool_call:
                self.on_tool_call(tool_name, tool_args, output, True)
            total_tool_rounds += 1
            prompt += f"\n[HERRAMIENTA {tool_name} resultado]: {output}\nObserva el resultado y continua."
        if not final_text:
            final_text = current_text or "Sin respuesta."
        self.state.add_turn("assistant", final_text)
        self._summarize_if_needed()
        tokens = self.compressor.estimate_tokens(final_text)
        return AssistantReply(ok=True, text=final_text, model=model, tokens=tokens)