"""Clasificacion central de intenciones de IGRIS OS.

La regla principal es conservadora: una posible orden operativa nunca debe caer
silenciosamente en el chat. Las entradas ambiguas se envian al planificador o al
flujo de mision, mientras que solo la charla de alta confianza llega al LLM de
conversacion.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata


@dataclass(frozen=True, slots=True)
class IntentDecision:
    kind: str
    subtype: str = ""
    confidence: float = 0.0
    reasons: tuple[str, ...] = ()
    normalized: str = ""

    @property
    def is_conversation(self) -> bool:
        return self.kind == "conversation"

    @property
    def is_capability(self) -> bool:
        return self.kind == "capability"

    @property
    def is_programming(self) -> bool:
        return self.kind == "programming"


_TYPO_MAP = {
    "saves": "sabes",
    "save": "sabe",
    "prollecto": "proyecto",
    "prollectos": "proyectos",
    "projecto": "proyecto",
    "projectos": "proyectos",
    "ajedres": "ajedrez",
    "chees": "chess",
    "programcion": "programacion",
    "programacionn": "programacion",
    "aplicasion": "aplicacion",
}


def normalize_intent(text: str) -> str:
    normalized = unicodedata.normalize("NFD", (text or "").casefold())
    normalized = "".join(
        char for char in normalized if unicodedata.category(char) != "Mn")
    normalized = re.sub(r"[^a-z0-9_:+./\\-]+", " ", normalized)
    tokens = [_TYPO_MAP.get(token, token) for token in normalized.split()]
    return " ".join(tokens)


_PROGRAMMING_OBJECTS = frozenset({
    "programa", "software", "aplicacion", "app", "codigo", "script",
    "proyecto", "repositorio", "web", "pagina", "api", "bot", "servidor",
    "juego", "videojuego", "ajedrez", "chess", "godot", "python", "lua",
    "javascript", "typescript", "html", "css", "inventario", "calculadora",
    "optimizer", "optimizador", "igris", "prototipo", "muestra", "demo",
    "maqueta", "entregable",
})

_CREATE_RE = re.compile(
    r"\b(?:crea|crear|creame|crees|haz|hazme|hagas|construye|construir|genera|generar|generes|"
    r"desarrolla|desarrollar|programa|programar|implementa|implementar|realiza|realizar)\b")
_CHANGE_RE = re.compile(
    r"\b(?:mejora(?:r|lo|la|rlo|rla|me|ad|en|e)?|"
    r"arregla(?:r|lo|la|rlo|rla)?|repara(?:r|lo|la|rlo|rla)?|"
    r"corrige|corregir|corrija|corrijan|corrigiendo|"
    r"modifica(?:r|lo|la|rlo|rla)?|actualiza(?:r|lo|la|rlo|rla)?|"
    r"refactoriza(?:r|lo|la|rlo|rla)?|optimiza(?:r|lo|la|rlo|rla)?|"
    r"remasteriza(?:r|lo|la|rlo|rla)?|integra(?:r|lo|la|rlo|rla)?|"
    r"renueva(?:r|lo|la|rlo|rla)?|renova(?:r|lo|la|rlo|rla)?)\b")
_CONTINUE_RE = re.compile(
    r"\b(?:continua|continuar|sigue|seguir|reanuda|reanudar|retoma(?:rlo|r|lo)?|retomes)\b")
_RESUME_ONLY_RE = re.compile(
    r"^(?:(?:ok|vale|bien|por favor)\s+)*(?:retoma(?:rlo|r|lo)?|reanuda(?:rlo|r|lo)?)\b")
_TEST_RE = re.compile(
    r"\b(?:testea|testear|prueba|probar|verifica|verificar|valida|validar|"
    r"compila|compilar|ejecuta|ejecutar|depura|depurar|debug)\b")
_AUDIT_RE = re.compile(
    r"\b(?:audita|auditar|analiza|analizar|inspecciona|inspeccionar|diagnostica|"
    r"diagnosticar|revisa|revisar)\b")
_FOLLOWUP_RE = re.compile(
    r"\b(?:reintenta|reintentar|intenta de nuevo|vuelve a intentar|retry|hazlo|sigue con ello)\b")

_REQUEST_FRAGMENTS = (
    "quiero que", "necesito que", "te pido que", "hazme", "creame",
    "me puedes hacer", "puedes hacerme", "puedes crearme", "me puedes crear",
    "podrias hacerme", "podrias crearme",
    "encargate de", "quiero un programa", "quiero una aplicacion",
    "quiero un juego", "quiero un proyecto",
)

_ADVICE_PREFIXES = (
    "como ", "por que ", "porque ", "que es ", "que significa ",
    "explica ", "explicame ", "cual es ", "cuales son ", "dime como ",
    "me explicas ", "puedes explicarme ",
)

_GREETING_RE = re.compile(
    r"^(?:(?:hola|buenas|buenos dias|buenas tardes|buenas noches|que tal|"
    r"gracias|muchas gracias|vale|ok|perfecto|de acuerdo|entendido)"
    r"(?:\s+(?:igris|amigo))?[.!? ]*)+$")

_CAPABILITY_PROGRAMMING_RE = re.compile(
    r"(?:\b(?:puedes|sabes|eres capaz de|estas preparado para|estas listo para|"
    r"estas preparado|estas listo|todavia no sabes|ya sabes)\b.{0,55}"
    r"\b(?:programar|programacion|crear software|crear programas|hacer programas|"
    r"desarrollar software|crear juegos|hacer juegos)\b)"
)

_CAPABILITY_GENERAL_RE = re.compile(
    r"\b(?:que|cuales)\s+(?:funciones|capacidades)(?:\s+de\s+programacion)?\s+(?:tienes|posees)\b|"
    r"\b(?:que|cuales)\s+(?:son\s+)?tus\s+(?:funciones|capacidades)(?:\s+de\s+programacion)?\b|"
    r"\b(?:funciones|capacidades)\s+de\s+programacion\b|"
    r"\bque puedes hacer\b"
)

_LOCAL_PATH_RE = re.compile(r"(?<![\w])[a-z]:[\\/]")


def _is_standalone_local_path(text: str) -> bool:
    """Only a turn consisting of a path is a path answer, not a path-bearing task."""
    raw = str(text or "").strip().strip('`').strip('"').strip("'").strip("“”")
    if not raw or "\n" in raw or "\r" in raw:
        return False
    return bool(
        re.fullmatch(r"[A-Za-z]:[\\/].+", raw)
        or (raw.startswith("\\\\") and len(raw) > 3)
        or (raw.startswith("/") and len(raw) > 1)
    )

_POLITE_EXECUTION_RE = re.compile(
    r"\b(?:puedes|podrias)\s+(?:programar|crear(?:me)?|hacer(?:me)?|desarrollar)\s+"
    r"(?:un|una|el|la|este|esta|mi|nuestro|nuestra)\s+[a-z0-9_]+")

_ADVICE_CHANGE_RE = re.compile(
    r"\b(?:como puedo|como podria|como|explicame como|dime como|quiero saber como)\b"
    r".{0,80}\b(?:mejorar|arreglar|reparar|corregir|programar|crear|desarrollar|"
    r"actualizar|optimizar|refactorizar)\b")

_RESEARCH_RE = re.compile(
    r"\b(?:busca|buscar|investiga|investigar|averigua|averiguar)\b")


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_]+", text))


def _has_programming_object(text: str) -> bool:
    words = _tokens(text)
    if words & _PROGRAMMING_OBJECTS:
        return True
    return any(phrase in text for phrase in (
        "pagina web", "base de datos", "machine learning", "inteligencia artificial",
        "igris os", "igris optimizer", "codigo fuente", "modelo 3d",
    ))


def _has_explicit_request(text: str) -> bool:
    return any(fragment in text for fragment in _REQUEST_FRAGMENTS)


def classify_intent(
    text: str,
    *,
    has_active_programming_context: bool = False,
) -> IntentDecision:
    """Clasifica el turno antes de decidir entre chat y ejecucion.

    ``conversation`` se devuelve solo con evidencia clara de charla. Si hay una
    posible orden tecnica pero falta informacion, se devuelve ``task`` o
    ``programming`` para impedir que el chat la absorba.
    """
    normalized = normalize_intent(text)
    if not normalized:
        return IntentDecision("conversation", "empty", 1.0, ("empty",), normalized)

    if _RESUME_ONLY_RE.match(normalized):
        return IntentDecision("task", "resume", 0.99, ("resume_command",), normalized)

    # Una ruta sola completa una aclaración; una ruta dentro de una orden
    # aporta contexto y no debe ocultar la acción solicitada.
    if _is_standalone_local_path(text):
        return IntentDecision("task", "local_path", 0.99, ("local_path",), normalized)

    # Preguntas sobre capacidad se resuelven por el catalogo real, no por el LLM.
    if (_CAPABILITY_PROGRAMMING_RE.search(normalized) and
            not _POLITE_EXECUTION_RE.search(normalized)):
        return IntentDecision(
            "capability", "programming", 0.99,
            ("programming_capability_question",), normalized)
    if _CAPABILITY_GENERAL_RE.search(normalized):
        return IntentDecision(
            "capability", "general", 0.98,
            ("general_capability_question",), normalized)

    project = _has_programming_object(normalized)
    project_context = bool(project and re.search(r"\b(?:tengo|tenemos|estoy con|estamos con|trabajo en|trabajamos en|hay)\b", normalized))
    explicit = _has_explicit_request(normalized)
    create = bool(_CREATE_RE.search(normalized))
    change = bool(_CHANGE_RE.search(normalized))
    continuation = bool(_CONTINUE_RE.search(normalized))
    testing = bool(_TEST_RE.search(normalized))
    audit = bool(_AUDIT_RE.search(normalized))
    followup = bool(_FOLLOWUP_RE.search(normalized))

    # Preguntar COMO hacer/mejorar algo es asesoria, no permiso para editarlo.
    # Si ademas pide buscar/investigar, sigue siendo una tarea de investigacion,
    # pero nunca una orden de modificar el proyecto.
    if _ADVICE_CHANGE_RE.search(normalized):
        if _RESEARCH_RE.search(normalized):
            return IntentDecision(
                "task", "research", 0.94,
                ("research_request", "advice_form"), normalized)
        return IntentDecision(
            "conversation", "technical_advice", 0.96,
            ("advice_how_to",), normalized)

    # Una pregunta de aprendizaje/asesoria no es una orden solo por mencionar codigo.
    if (create or explicit or _POLITE_EXECUTION_RE.search(normalized)) and re.search(
            r'\b(?:imagen|imagenes|fotografia|ilustracion|dibujo|video|audio|musica)\b', normalized):
        return IntentDecision('task', 'media_creation', 0.99,
                              ('media_object', 'creation_request'), normalized)

    advice = normalized.startswith(_ADVICE_PREFIXES)
    if advice and not explicit and not continuation:
        return IntentDecision(
            "conversation", "technical_advice", 0.94,
            ("advice_question",), normalized)

    if project and continuation:
        return IntentDecision(
            "programming", "continue", 0.99,
            ("project_object", "continue_action"), normalized)
    if project and change:
        repair = any(word in _tokens(normalized) for word in {
            "arregla", "arreglar", "repara", "reparar", "corrige", "corregir",
            "depura", "depurar",
        })
        return IntentDecision(
            "programming", "repair" if repair else "modify", 0.99,
            ("project_object", "change_action"), normalized)
    # Instrucciones compuestas pueden pedir que se construya algo y, además,
    # que se inspeccione o verifique. La creación es la entrega principal;
    # test/audit son criterios de aceptación, no una sustitución de la tarea.
    if project and create:
        return IntentDecision(
            "programming", "create", 0.99,
            ("project_object", "creation_request"), normalized)
    if project and testing:
        return IntentDecision(
            "programming", "test", 0.98,
            ("project_object", "test_action"), normalized)
    if project and audit:
        return IntentDecision(
            "programming", "audit", 0.97,
            ("project_object", "audit_action"), normalized)
    if project and (create or explicit):
        return IntentDecision(
            "programming", "create", 0.99,
            ("project_object", "creation_request"), normalized)

    # Introducir un proyecto existente sin dar todavía una orden concreta no es
    # charla casual: establece el sujeto operativo de la conversación. El
    # Cognitive Core pedirá la mínima aclaración necesaria (normalmente la ruta)
    # sin iniciar escritura.
    if project_context:
        return IntentDecision(
            "programming", "context", 0.93,
            ("project_object", "operational_subject"), normalized)

    # Continuaciones cortas pertenecen al flujo de mision si existe contexto.
    if has_active_programming_context and (continuation or change or testing or followup):
        return IntentDecision(
            "programming", "followup", 0.95,
            ("active_programming_context",), normalized)

    # Seguimientos desnudos ("continua", "reintenta") solo son orden cuando
    # existe una mision activa. La UI resuelve ese contexto antes de llegar aqui.
    if (continuation or followup) and not project and not has_active_programming_context:
        return IntentDecision(
            "conversation", "contextual_followup", 0.90,
            ("followup_without_active_context",), normalized)

    # Imperativos operativos sin objeto suficiente NO se mandan al chat: el
    # planificador debe resolverlos o pedir contexto.
    if create or change or continuation or testing or audit or followup or explicit:
        return IntentDecision(
            "task", "operational", 0.82,
            ("operational_language",), normalized)

    if _GREETING_RE.fullmatch(normalized):
        return IntentDecision(
            "conversation", "social", 0.99,
            ("greeting_or_ack",), normalized)

    # Comentarios, criticas y preguntas no operativas son charla. Si incluyen
    # vocabulario de proyecto sin un verbo de accion, siguen siendo conversacion;
    # los seguimientos de una mision se resuelven antes por programming_followup.
    return IntentDecision(
        "conversation", "general", 0.88,
        ("no_operational_signal",), normalized)


def is_capability_query(text: str) -> bool:
    return classify_intent(text).is_capability


def is_programming_intent(text: str, *, has_active_context: bool = False) -> bool:
    return classify_intent(
        text, has_active_programming_context=has_active_context).is_programming


def is_conversation_intent(text: str) -> bool:
    return classify_intent(text).is_conversation
