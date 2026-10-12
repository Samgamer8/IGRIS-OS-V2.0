import collections
import os
import re
import shlex
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from igris_os.ai import ModelRouter, OllamaClient
from igris_os.ai.orchestrator import ModelOrchestrator, ModelPurpose, ModelRoute
from igris_os.application.director import MissionDirector
from igris_os.application.consent import ConsentGate
from igris_os.application.intent_classifier import (
    is_conversation_intent, normalize_intent, _GREETING_CANNED,
)
from igris_os.domain import Mission, MissionBranch
from igris_os.memory.compressor import ContextCompressor
from igris_os.security.sandbox import JobObjectSandbox, SandboxRun


PERSONALITY = """ESTILO DE IGRIS:
- Responde siempre en espanol, salvo que el usuario pida otro idioma. No mezcles idiomas.
- Estilo de mayordomo moderno: educado, sereno, firme, servicial y con criterio propio.
- Trata al usuario de usted por defecto, sin solemnidad excesiva; adapta el trato si lo pide.
- No repitas 'senor' ni formulas de obediencia en cada frase. Tu identidad es IGRIS, no JARVIS.
- Se sincero y directo. No des la razon por complacer ni adules al usuario.
- Si discrepas, explica brevemente el motivo y ofrece una alternativa concreta.
- Reconoce los errores y la incertidumbre sin excusas, dramatismo ni falsas promesas.
- No ocultes ni maquilles errores al usuario, aunque te lo pida. Informale y propone corregirlos.
- Usa humor seco solo de forma ocasional y nunca ante un fallo serio o una preocupacion del usuario.
- Contesta con dos a cuatro frases cuando baste; amplia solo si la pregunta o el trabajo lo requiere.
- No conviertas cada respuesta en una lista, un informe o una oferta de ayuda repetida.
- Distingue los hechos comprobados de las suposiciones y de las acciones pendientes.
"""


SYSTEM = """Eres IGRIS OS. Eres un sistema productivo de creación y un operador local seguro.
""" + PERSONALITY + """

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
- En conversación, responde al último mensaje y usa el contexto reciente. No repitas una plantilla ni cierres cada turno con la misma oferta de ayuda.
- Si el usuario señala que estás repitiendo, reconoce el patrón y cambia la respuesta; no vuelvas a decir que estás bien automáticamente.

EJECUCION:
- Cuando ejecutes algo, indica: que hiciste, donde quedo el resultado y que puede hacer el usuario ahora.
- Si algo falla, di la causa real y el siguiente paso, no una excusa generica.
- Si hace falta confirmacion, pidela sola.
- En tareas de programacion, actua como copiloto senior y critico: cuestiona requisitos ambiguos, detecta riesgos de seguridad, rendimiento y mantenimiento, y propone alternativas cuando la idea pueda fallar.
- Antes de cambiar o ejecutar codigo, distingue: HECHO VERIFICADO, INFERENCIA, RIESGO, CAMBIO PROPUESTO y PRUEBA NECESARIA.
- Nunca afirmes que modificaste, ejecutaste, compilaste o verificaste algo si no existe evidencia de esa accion.
- No prometas experiencia humana ni un nivel absoluto; mide tus capacidades por resultados reproducibles.
- Para codigo de produccion aplica KISS, DRY y SOLID sin sobreingenieria; valida entradas, errores y casos limite.
- No uses placeholders ni afirmes que una libreria esta actualizada sin comprobar el entorno o la documentacion disponible.
- Antes de un cambio complejo resume en pocas lineas la estrategia, sus costes aproximados O grande y los cambios de arquitectura necesarios.
- Al entregar trabajo tecnico separa: resultado, riesgos potenciales, optimizacion futura y estrategia de pruebas.
- No expongas razonamiento interno paso a paso; entrega solo una justificacion tecnica breve y auditable.

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
    backend: str = ""
    reasoning: str = ""
    data: dict[str, Any] = field(default_factory=dict)


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
    turns: collections.deque = field(default_factory=collections.deque)
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
        for turn in list(self.turns)[-max(1, limit):]:
            context.append({"role": turn.role, "text": turn.text})
            for tc in turn.tool_calls:
                context.append({"role": "tool", "text": f"[{tc.tool_name}] {tc.output}"})
        return context

    def add_conversation_turn(self, role: str, text: str) -> None:
        """Guarda solo texto conversacional, sin herramientas ni metadatos."""
        self.turns.append(ConversationTurn(role=role, text=text.strip()))
        while len(self.turns) > 20:
            self.turns.popleft()


def standalone_sha256(text: str) -> str | None:
    """Devuelve un SHA-256 pegado como unico contenido, sin consultar al LLM."""
    value = text.strip().casefold()
    return value if re.fullmatch(r'[0-9a-f]{64}', value) else None


def is_conversational_input(text: str) -> bool:
    """Una única fuente de verdad decide si el turno puede ir al chat."""
    return is_conversation_intent(text)


class AssistantService:
    def __init__(self, client: OllamaClient | None = None,
                 on_tool_call: Optional[Callable[[str, str, str, bool], None]] = None) -> None:
        self.client = client or OllamaClient()
        self.director = MissionDirector(client=self.client)
        self.router = ModelRouter(self.client)
        self.orchestrator = ModelOrchestrator(self.client)
        self.last_model_route: ModelRoute | None = None
        self.compressor = ContextCompressor()
        self.sandbox = JobObjectSandbox(memory_limit_mb=512, cpu_seconds=60,
                                        max_processes=4)
        self._tools: Dict[str, Callable[..., str]] = {
            "list_files": self._tool_list_files,
            "exam_status": self._tool_exam_status,
            "git_status": self._tool_git_status,
            "git_diff": self._tool_git_diff,
            "system_info": self._tool_system_info,
            # La conversacion no recibe shell generico. La programacion y la
            # administracion se ejecutan mediante capabilities tipadas.
        }
        self.state = ConversationState()
        self.consent = ConsentGate()
        self.on_tool_call = on_tool_call

    def _consent_gate(self) -> ConsentGate:
        """Devuelve el gate de consentimiento, creandolo si hace falta.

        Tolerante a instancias creadas con ``__new__`` (que saltan ``__init__``
        en algunos tests): garantiza que el flujo nunca rompe por falta de
        atributo, sin obligar a construir el asistente completo.
        """
        gate = getattr(self, "consent", None)
        if gate is None:
            gate = ConsentGate()
            self.consent = gate
        return gate

    def choose_model(self, branch: MissionBranch,
                     objective: str = "") -> str:
        route = self._orchestrator().route(
            self._orchestrator().infer_purpose(objective, branch.value))
        self.last_model_route = route
        return route.model

    def _orchestrator(self) -> ModelOrchestrator:
        orchestrator = getattr(self, "orchestrator", None)
        if orchestrator is None:
            orchestrator = ModelOrchestrator(self.client)
            self.orchestrator = orchestrator
        return orchestrator

    def _model_route_data(self) -> dict[str, Any]:
        route = getattr(self, "last_model_route", None)
        if route is None:
            return {}
        return {"orchestration": {
            "purpose": route.purpose.value,
            "model": route.model,
            "backend": route.backend,
            "reason": route.reason,
            "resources": route.resources,
            "fallback": route.fallback,
            "considered_models": list(route.considered),
        }}

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

    def _tool_exam_status(self, args: str = "") -> str:
        """Reporta solo entregas reales del examen, no prototipos internos."""
        root = Path.cwd()
        exam_root = root / "workspace" / "exam_deliveries"
        expected = {
            "chess_3d": exam_root / "chess_3d",
            "pc_optimizer": exam_root / "pc_optimizer",
            "control_panel": exam_root / "control_panel",
        }
        lines = ["EXAMEN DE PRODUCTIVIDAD REAL"]
        for name, path in expected.items():
            state = "ENTREGA PRESENTE" if path.is_dir() else "NO CREADA"
            lines.append(f"{name}: {state} | {path}")
        report = root / "runtime" / "audit" / "productivity_exam_2026-08-26.json"
        lines.append("informe: " + (str(report) if report.is_file() else "NO EXISTE"))
        return "\n".join(lines)

    def _run_sandboxed(self, command: Sequence[str], cwd: Optional[str] = None,
                       timeout_seconds: Optional[int] = None) -> SandboxRun:
        return self.sandbox.run(list(command), cwd=cwd,
                                timeout=timeout_seconds if timeout_seconds is not None else 60)

    def _tool_git_status(self, args: str) -> str:
        cwd = args.strip() or "."
        result = self._run_sandboxed(["git", "status", "--short"], cwd=cwd,
                                     timeout_seconds=30)
        if result.timed_out:
            return "[TIMEOUT] git status excedio el limite"
        return result.stdout.strip() or "working tree clean"

    def _tool_git_diff(self, args: str) -> str:
        cwd = args.strip() or "."
        result = self._run_sandboxed(["git", "diff", "--stat"], cwd=cwd,
                                     timeout_seconds=30)
        if result.timed_out:
            return "[TIMEOUT] git diff excedio el limite"
        return result.stdout.strip() or "no changes"

    def _tool_system_info(self, args: str) -> str:
        import os
        import platform
        if os.name != "nt":
            return "Sistema operativo: " + platform.platform()
        result = self._run_sandboxed(["systeminfo"], timeout_seconds=30)
        if result.timed_out:
            return "[TIMEOUT] systeminfo excedio el limite"
        output = result.stdout.strip() or result.stderr.strip()
        return output[:2000] if output else "sin datos"

    _ALLOWED_TOOLS = frozenset({
        "git", "ffmpeg", "ffprobe", "python", "py", "where",
    })

    def _tool_run_command(self, args: str) -> str:
        try:
            parts = shlex.split(args, posix=False)
        except ValueError:
            return "[ERROR] Comando mal formado"
        if not parts:
            return "[ERROR] Comando vacio"
        if parts[0].lower() not in self._ALLOWED_TOOLS:
            return (f"[ERROR] Herramienta no permitida: {parts[0]}. "
                    f"Permitidas: {', '.join(sorted(self._ALLOWED_TOOLS))}")
        if any(part in {"&", "|", ">", "<", ";", "&&", "||"} for part in parts):
            return "[ERROR] Operadores de shell no permitidos"
        result = self._run_sandboxed(parts)
        if result.timed_out:
            return "[TIMEOUT] El comando excedio el limite y fue terminado"
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
        for _ in range(len(old_turns)):
            self.state.turns.popleft()
        if self.state.turns and self.state.turns[0].role == "assistant":
            self.state.turns[0].text = f"[Contexto resumido]\n{summary}\n\n" + self.state.turns[0].text
        else:
            self.state.turns.appendleft(ConversationTurn(role="system", text=f"[Contexto resumido]\n{summary}"))
        return summary

    def respond(self, objective: str,
                context: Tuple[str, ...] = ()) -> AssistantReply:
        self.last_model_route = None
        # Si hay una propuesta de alto calado esperando, la respuesta del
        # usuario se interpreta como si/no, no como una orden nueva. Asi el
        # asistente pregunta y espera en vez de ejecutar a ciegas.
        if self._consent_gate().has_pending():
            outcome = self._consent_gate().resolve(objective)
            text = outcome["reason"]
            self.state.add_conversation_turn("user", objective.strip())
            self.state.add_conversation_turn("assistant", text)
            data = {"consent": {"decision": outcome["decision"],
                                "action_id": outcome["proposal"].action_id}}
            return AssistantReply(True, text, "", 0, "local", data=data)
        if not objective.strip():
            return AssistantReply(False, "Escribe una orden.", "", 0)
        lower = objective.strip().lower()
        from igris_os.application.intent_classifier import classify_intent
        if classify_intent(objective).subtype == 'media_creation':
            return AssistantReply(False,
                'Esta peticion necesita un motor multimedia y una ejecucion real. '
                'El chat no ha generado ni guardado ningun archivo; no voy a prometer una entrega desde esta respuesta.',
                'local', backend='local', data={'requires_execution': True})

        # Fast-path para saludos conocidos: sin llamar al LLM. Devuelve el texto
        # preformateado inmediatamente y evita que el modelo se descargue de VRAM
        # tras la inactividad, con lo que la respuesta y la voz son instantáneos.
        if lower in (_GREETING_CANNED):
            with open("runtime/logs/greeting_debug.log", "a", encoding="utf-8") as _dbg:

                canned = _GREETING_CANNED[lower]

            canned = _GREETING_CANNED[lower]
            self.state.add_conversation_turn("user", objective.strip())
            self.state.add_conversation_turn("assistant", canned)
            data = self._model_route_data()
            return AssistantReply(True, canned, "", 0, "local", data=data)
        if self._is_self_description_question(lower):
            text = (
                "Soy IGRIS OS, un asistente local creado para conversar contigo y "
                "ayudarte a convertir tus objetivos en trabajo útil. Puedo apoyarte "
                "con programación y revisión de proyectos o archivos, juegos Godot "
                "y algunas tareas locales de Windows y multimedia. Antes de hacer "
                "cambios importantes pido autorización; si una herramienta no está "
                "disponible en este equipo, te lo diré claramente. También puedo "
                "responder por voz cuando el audio local está activo."
            )
            self.state.add_conversation_turn("user", objective.strip())
            self.state.add_conversation_turn("assistant", text)
            return AssistantReply(
                True, text, "local", self.compressor.estimate_tokens(text), "local")
        exam_terms = ("estado del examen", "trabajos del examen",
                      "entregas del examen", "donde estan los trabajos del examen",
                      "dónde están los trabajos del examen")
        if any(term in lower for term in exam_terms):
            text = self._tool_exam_status()
            return AssistantReply(True, text, "local", 0, "filesystem")
        if self._is_github_repo_search(lower):
            return self._handle_github_repo_search(objective)
        consent_gate = self._maybe_request_consent(objective, lower)
        if consent_gate is not None:
            return consent_gate
        if self._is_conversation(lower):
            model = self._conversation_model()
            if not model:
                reason = getattr(self.last_model_route, "reason", "")
                return AssistantReply(
                    False, reason or "No hay un modelo local apto para esta conversación.",
                    "", 0, data=self._model_route_data())
            conversation_context = self._conversation_context(context)
            reply = self.client.generate(
                self._conversation_prompt(objective.strip(), conversation_context), model)
            missing_model = any(term in (reply.error or "").casefold() for term in
                                ("not found", "no encontrado", "no existe", "404"))
            if not reply.ok and missing_model:
                orchestrator = self._orchestrator()
                fallback_route = orchestrator.route(
                    ModelPurpose.GENERAL,
                    available=(name for name in orchestrator.available_models()
                               if name != model),
                )
                self.last_model_route = fallback_route
                if fallback_route.model:
                    model = fallback_route.model
                    reply = self.client.generate(
                        self._conversation_prompt(objective.strip(), conversation_context), model)
            text = reply.text if reply.ok else reply.error
            if reply.ok and text.strip():
                self.state.add_conversation_turn("user", objective.strip())
                self.state.add_conversation_turn("assistant", text)
            return AssistantReply(
                reply.ok, text, reply.model or model,
                self.compressor.estimate_tokens(text),
                getattr(reply, "backend", ""), getattr(reply, "reasoning", ""),
                self._model_route_data())
        plan = self.director.plan(Mission(objective))
        model = self.choose_model(plan.branch, objective)
        if not model:
            return AssistantReply(
                False,
                getattr(self.last_model_route, "reason", "") or
                "Servidor LLM no disponible o sin modelos instalados.",
                "", 0, data=self._model_route_data())
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
        return AssistantReply(reply.ok, text, model, tokens,
                              getattr(reply, "backend", ""),
                              getattr(reply, "reasoning", ""),
                              self._model_route_data())

    @staticmethod
    def _is_conversation(text: str) -> bool:
        return is_conversational_input(text)

    @staticmethod
    def _is_self_description_question(text: str) -> bool:
        normalized = normalize_intent(text)
        return bool(
            re.search(
                r"\b(?:quien eres|que eres|que (?:me )?puedes decir de ti|"
                r"hablame de ti|cuentame(?: un poco)? (?:sobre|de) ti|para que (?:te )?"
                r"(?:crearon|estas creado|estas creada|fuiste creado|fuiste creada)|"
                r"para que sirves)\b",
                normalized,
            )
            or re.search(
                r"\b(?:explicame|esplicame|cuentame|dime)\b.{0,70}"
                r"\b(?:funciones|habilidades|capacidades)\b",
                normalized,
            )
        )

    @staticmethod
    def _is_github_repo_search(text: str) -> bool:
        """Detecta peticiones de buscar repositorios en GitHub.

        Requiere mencionar GitHub Y una intencion de buscar repositorios, para
        no activarse con cualquier mencion a la palabra github.
        """
        lowered = text.lower()
        mentions_github = "github" in lowered
        wants_search = any(term in lowered for term in (
            "repositorio", "repositorios", "repo ", "repos", "busca", "buscar",
            "encuentra", "encontrar"))
        return mentions_github and wants_search

    def _handle_github_repo_search(self, objective: str) -> AssistantReply:
        """Busqueda REAL en GitHub: cuenta, ordena por relevancia y abre el top-5.

        No pasa por el LLM para evitar invenciones: la fuente de la verdad es
        la API de GitHub. Cada uno de los 5 mas relevantes se abre en una
        ventana independiente de Chrome.
        """
        from igris_os.capabilities.github_search import (
            extract_github_query, format_report, refine_query, search_and_open)
        query = refine_query(extract_github_query(objective))
        if not query:
            return AssistantReply(
                True,
                "No entendi que repositorios buscar en GitHub. "
                "Dime el tema con palabras clave, por ejemplo: "
                "«busca en github repositorios de agentes multiples».",
                "local", 0, "local")
        result, opened = search_and_open(query, top_n=5)
        text = format_report(result, opened)
        self.state.add_conversation_turn("user", objective.strip())
        self.state.add_conversation_turn("assistant", text)
        return AssistantReply(
            result.error == "" and result.total_count > 0,
            text, "github-api", 0, "github",
            data={"github_search": {
                "query": query,
                "total_count": result.total_count,
                "opened": opened,
                "rate_limited": result.rate_limited,
            }})

    # -- consentimiento explicito para pasos de alto calado --------------
    # Palabras que senalan que el encargo toca el nucleo del sistema.
    _CORE_WORDS = (
        "kernel", "nucleo", "núcleo", "bootstrap", "arranque",
        "fallbackchain", "fallback chain", "asistente real", "consent",
    )
    # Verbos de integracion fuerte: modifican codigo existente del nucleo.
    _INTEGRATION_VERBS = (
        "cablear", "cablea", "integrar", "integra", "implementar en",
        "implementa en", "modificar el", "modifica el", "tocar el",
    )

    def _maybe_request_consent(self, objective: str,
                               lower: str) -> Optional[AssistantReply]:
        """Si el encargo toca el nucleo, pregunta antes de actuar.

        Dispara si el texto menciona una pieza del nucleo (kernel, nucleo,
        bootstrap, arranque, FallbackChain...) o un verbo de integracion
        fuerte sobre el asistente. Devuelve el ``AssistantReply`` con la
        pregunta, o ``None`` si debe seguir el flujo normal.
        """
        touches_core = any(term in lower for term in self._CORE_WORDS)
        strong_verb = any(term in lower for term in self._INTEGRATION_VERBS)
        if not (touches_core or strong_verb):
            return None
        text = self._consent_gate().propose(
            "Quieres que cablee esto dentro del asistente real?",
            "Encargo de alto calado: " + objective.strip()[:160],
            risk="high", action_id="consent.high-impact")
        self.state.add_conversation_turn("user", objective.strip())
        self.state.add_conversation_turn("assistant", text)
        return AssistantReply(
            True, text, "", 0, "local",
            data={"consent": {"decision": "pending",
                              "action_id": "consent.high-impact"}})

    def _conversation_model(self) -> str:
        """Treat the configured model as a preference subject to local limits."""
        configured = os.environ.get("IGRIS_CONVERSATION_MODEL", "").strip()
        route = self._orchestrator().route(
            ModelPurpose.GENERAL, preferred_model=configured)
        self.last_model_route = route
        return route.model

    def _conversation_context(self, context: Tuple[str, ...]) -> Tuple[str, ...]:
        """Combina memoria externa con los turnos estructurados de esta instancia."""
        internal = tuple(
            f"{turn.role}: {turn.text}"
            for turn in self.state.turns
            if turn.role in {"user", "assistant"}
        )
        return (internal + tuple(context))[-12:]

    @staticmethod
    def _conversation_prompt(objective: str, context: Tuple[str, ...]) -> str:
        recent = "\n".join(context[-8:])
        return (
            PERSONALITY + "\n" +
            "Eres IGRIS en una conversacion real, no un agente de soporte ni un folleto. "
            "Responde al ultimo mensaje con lenguaje natural, claro y conciso. "
            "No te presentes ni enumeres funciones salvo que el usuario pregunte por tu identidad, "
            "proposito, habilidades o capacidades; en ese caso responde directamente y con ejemplos reales. "
            "No termines cada respuesta con '¿En que puedo ayudarte?' ni cambies de tema. "
            "Tu identidad es IGRIS OS, no la del fabricante o nombre del modelo. "
            "No digas que eres Alibaba, Qwen, una empresa ni un chatbot genérico. "
            "No afirmes que solo puedes conversar: IGRIS puede usar herramientas locales "
            "cuando el usuario lo solicite mediante el flujo seguro. "
            "IGRIS OS es un asistente local multiproposito para conversar, ayudar con programacion y "
            "revision de proyectos/archivos, juegos Godot y algunas tareas locales de Windows y multimedia. "
            "No inventes capacidades disponibles en este equipo. "
            "Si detectas un encargo operativo, indica que debe pasar al flujo local de misión. "
            "No prometas entregas completas ni afirmes que hay herramientas o modelos disponibles "
            "sin evidencia de una comprobacion real. "
            "Si el usuario saluda, saluda y continua la charla; si pregunta por ti, responde sobre ti. "
            "Si comenta una respuesta anterior, contesta a ese comentario de forma directa. "
            "No inventes hechos: si no sabes algo, dilo; si falta contexto, pregunta una sola cosa concreta. "
            "No inventes listas de repositorios, enlaces ni proyectos concretos: si el usuario pide repos reales "
            "de GitHub, indica que necesitas su confirmacion para buscarlos con la API, sin inventarlos. "
            "Redacta en frases completas con verbo; evita enumerar nombres sueltos o fragmentos de una o dos "
            "palabras, que la voz no puede pronunciar. "
            "Si el usuario critica tu respuesta, responde a la critica y cambia tu forma de responder. "
            "Si el usuario critica tu respuesta, responde a la critica y cambia tu forma de responder. "
            "No ejecutes herramientas ni planifiques proyectos en esta respuesta.\n"
            + ("HISTORIAL RECIENTE:\n" + recent + "\n" if recent else "")
            + "ULTIMO MENSAJE DEL USUARIO:\n" + objective)

    def respond_agentic(self, objective: str,
                        context: Tuple[str, ...] = ()) -> AssistantReply:
        if not objective.strip():
            return AssistantReply(False, "Escribe una orden.", "", 0)
        self.state.add_turn("user", objective)
        self._summarize_if_needed()
        plan = self.director.plan(Mission(objective))
        model = self.choose_model(plan.branch, objective)
        if not model:
            return AssistantReply(False, "Servidor LLM no disponible.", "", 0)
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
        tool_outputs: list[str] = []
        for round_idx in range(self.state.max_tool_rounds):
            full_prompt = prompt + "\nRespuesta de IGRIS:"
            if tool_outputs:
                full_prompt += "\n" + "\n".join(tool_outputs)
            reply = self.client.generate(full_prompt, model)
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
            tool_outputs.append(f"[HERRAMIENTA {tool_name} resultado]: {output}\nObserva el resultado y continua.")
        if not final_text:
            final_text = current_text or "Sin respuesta."
        self.state.add_turn("assistant", final_text)
        self._summarize_if_needed()
        tokens = self.compressor.estimate_tokens(final_text)
        return AssistantReply(ok=True, text=final_text, model=model, tokens=tokens,
                              backend=getattr(reply, "backend", ""),
                              reasoning=getattr(reply, "reasoning", ""))
