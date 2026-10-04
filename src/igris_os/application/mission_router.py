from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence
import re
import unicodedata

from igris_os.application.director import LLMMissionDirector, MissionDirector
from igris_os.application.intent_classifier import is_capability_query as is_capability_intent
from igris_os.domain import Mission, MissionBranch


@dataclass(frozen=True, slots=True)
class RoutedAction:
    kind: str
    capability: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    requires_confirmation: bool = False


def _normalize_intent(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text.casefold())
    normalized = "".join(
        char for char in normalized if unicodedata.category(char) != "Mn")
    return " ".join(re.sub(r"[^a-z0-9_]+", " ", normalized).split())


def _has_creation_signal(text: str, object_markers: tuple[str, ...]) -> bool:
    """Exige intención de producir algo; una pregunta de capacidad no basta."""
    has_object = any(marker in text for marker in object_markers)
    if not has_object:
        return False
    action = re.search(
        r"\b(crea|crear|creame|construye|construir|contruye|contrullas|"
        r"genera|generar|desarrolla|desarrollar|programa|haz|hazme|implementa)\b",
        text)
    explicit_request = any(phrase in text for phrase in (
        "quiero que", "necesito que", "quiero un ", "quiero una ",
        "me puedes hacer", "puedes hacerme", "puedes crearme",
        "podrias hacerme", "podrias crearme"))
    delivery_detail = any(phrase in text for phrase in (
        "en el escritorio", "en una carpeta", "en la carpeta",
        "guardalo en", "guarda en", "nombre ", "llamado ", "llamada "))
    noun_follow_up = text.startswith(("un juego", "una aplicacion", "un programa",
                                      "un videojuego", "una app"))
    return bool(action or explicit_request or (delivery_detail and noun_follow_up))


def godot_templates_action(objective: str) -> RoutedAction | None:
    """Handle installation files locally before invoking any language model."""
    text = _normalize_intent(objective)
    if "plantillas" not in text and "templates" not in text:
        return None
    path = re.search(r'([A-Za-z]:[\\/][^\r\n"<>|]+)', objective)
    if not any(word in text for word in ("godot", "exportacion", "exportar", "ejecutable")) and path is None:
        return None
    if not any(word in text.split() for word in ("busca", "buscar", "localiza", "comprueba", "revisa", "genera", "instala", "descarga")):
        return None
    install = any(word in text.split() for word in ("instala", "descarga"))
    payload = {"root": path.group(1).strip().rstrip('"') if path else ""}
    return RoutedAction("capability", "games.godot.templates.install" if install
                        else "games.godot.templates.find", payload, install)


def neural_image_action(objective: str) -> RoutedAction | None:
    from .intent_classifier import classify_intent
    decision = classify_intent(objective)
    if decision.kind not in {'task', 'programming'}:
        return None
    words = set(decision.normalized.split())
    if not words & {'esfera', 'esferas'} or not words & {
            'neuronal', 'neuronales', 'neural', 'pensamiento', 'jarvis', 'ultron', 'utron'}:
        return None
    if not _has_creation_signal(_normalize_intent(objective), ('esfera',)) and not re.search(
            r'\b(?:hagas|crees|generes)\b', decision.normalized):
        return None
    count = 2 if words & {'dos', '2', 'otra', 'ultron', 'utron'} else 1
    return RoutedAction('capability', 'image.neural_sphere',
                        {'count': count, 'width': 1920, 'height': 1080}, True)


def is_game_creation_request(objective: str) -> bool:
    """Reconoce encargos de juego sin depender de una clasificación del LLM."""
    text = _normalize_intent(objective)
    return _has_creation_signal(
        text, ("juego", "videojuego", "ajedrez", "chess", "godot", "pygame"))


def is_programming_creation_request(objective: str) -> bool:
    """Detecta encargos de software antes de delegar la decisión al LLM."""
    text = _normalize_intent(objective)
    software_markers = (
        "aplicacion", "app", "programa", "herramienta",
        "script", "calculadora", "tablero", "pagina web",
        "web", "bot", "editor", "gestor", "utilidad",
    )
    return _has_creation_signal(text, software_markers)


def is_creation_request(objective: str) -> bool:
    """Clasificador determinista común para separar charla de encargos."""
    return (is_game_creation_request(objective)
            or is_programming_creation_request(objective))


def is_sales_request(objective: str) -> bool:
    text = objective.casefold()
    markers = (
        "venta", "ventas", "vender", "promociona", "promocionar",
        "marketing", "rentabilidad", "rentable", "clientes", "comercial",
        "precio", "punto de equilibrio",
    )
    return any(marker in text for marker in markers)


def _existing_directory_sources(
        objective: str, attachments: Sequence[str] = ()) -> list[str]:
    """Resuelve carpetas existentes mencionadas por el usuario, conservando orden.

    Acepta adjuntos, rutas entre comillas y rutas Windows/POSIX escritas en el
    mensaje. Una ruta puede ocupar todo el turno: esto permite usarla como
    respuesta a una pregunta de una misión sin enviarla al chatbot.
    """
    candidates: list[str] = [str(item) for item in attachments]
    candidates.extend(re.findall(r'["“”]([^"“”]+)["“”]', objective))

    # Rutas Windows no entrecomilladas. Se prefieren separadores claros y el
    # final de linea; no se interpreta texto normal como ruta.
    for match in re.finditer(r'(?<![\w])([A-Za-z]:[\\/][^\r\n"<>|]+?)(?=(?:\s+[A-Za-zÁÉÍÓÚáéíóúÑñ]{3,}\s*:)|$)', objective):
        candidates.append(match.group(1))
    windows_tail = re.search(r'(?<![\w])([A-Za-z]:[\\/][^\r\n"<>|]+)\s*$', objective)
    if windows_tail:
        candidates.append(windows_tail.group(1))

    candidates.extend(re.findall(
        r'(?<![\w])(/(?:[^/\s]+/)*[^/\s,;!?]+)', objective))

    result: list[str] = []
    seen = set()
    for raw in candidates:
        value = raw.strip().strip("'.,;!?")
        if not value:
            continue
        path = Path(value).expanduser()
        try:
            if path.is_dir() and not path.is_symlink():
                resolved = str(path.resolve())
                key = resolved.casefold()
                if key not in seen:
                    seen.add(key)
                    result.append(resolved)
        except OSError:
            continue
    return result


def _existing_directory_source(
        objective: str, attachments: Sequence[str] = ()) -> str:
    sources = _existing_directory_sources(objective, attachments)
    return sources[0] if sources else ""


def repository_action(
        objective: str, attachments: Sequence[str] = ()) -> RoutedAction | None:
    """Prioriza trabajo sobre un repositorio existente frente a crear otro."""
    source = _existing_directory_source(objective, attachments)
    if not source:
        return None
    low = objective.casefold()
    if any(phrase in low for phrase in (
            "audita", "auditoria", "autodiagnostico del proyecto",
            "autodiagnóstico del proyecto", "preflight", "diagnostico tecnico",
            "diagnóstico técnico")):
        return RoutedAction(
            "capability", "programming.assess",
            {"root": source, "objective": objective})
    if any(phrase in low for phrase in (
            "propone cambios", "propón cambios", "proponer cambios",
            "plan de cambios", "que cambiarias", "qué cambiarías")):
        return RoutedAction(
            "capability", "programming.propose",
            {"root": source, "objective": objective})
    intent_words = set(_normalize_intent(objective).split())
    if any(word in intent_words for word in (
            "modifica", "arregla", "implementa", "corrige", "programa",
            "repara", "continua", "continúa", "mejora", "refactoriza")):
        return RoutedAction(
            "capability", "repository.develop",
            {"root": source, "objective": objective}, True)
    if any(phrase in low for phrase in (
            "copia aislada", "prepara este proyecto", "trabaja en este proyecto",
            "prepara el repositorio")):
        return RoutedAction(
            "capability", "repository.stage", {"root": source}, True)
    if any(word in low for word in (
            "analiza", "revisa", "inspecciona", "repositorio",
            "proyecto", "código", "codigo", "carpeta")):
        return RoutedAction(
            "capability", "repository.analyze",
            {"root": source, "query": objective}, True)
    return None


class MissionRouter:
    def __init__(self, *, use_llm_director: bool = True) -> None:
        self.use_llm_director = use_llm_director
        self.director = LLMMissionDirector() if use_llm_director else MissionDirector()
        self._plan_cache = {}

    def route(self, objective: str,
              attachments: Sequence[str] = ()) -> RoutedAction:
        neural = neural_image_action(objective)
        if neural:
            return neural
        templates = godot_templates_action(objective)
        if templates:
            return templates
        from igris_os.application.programming_intent import programming_action
        work = programming_action(objective, attachments)
        from igris_os.application.game_resume import is_resume_request
        normalized = _normalize_intent(objective)
        game_context = any(word in normalized.split() for word in (
            "ajedrez", "chess", "chees", "juego", "videojuego", "godot"))
        if is_resume_request(objective) and (not work or game_context):
            return RoutedAction("capability", "games.godot.resume", {"request": objective}, True)
        from igris_os.application.host_routing import host_action
        local = host_action(objective)
        if local:
            return local
        if work:
            return work
        if _existing_directory_source(objective, attachments) and any(
                word in _normalize_intent(objective).split() for word in ("continua", "continúa", "reanuda", "sigue")) and "repositorio" in _normalize_intent(objective):
            return RoutedAction("capability", "programming.mission",
                                {"objective": objective,
                                 "root": _existing_directory_source(objective, attachments),
                                 "requires_existing": True}, True)
        low = objective.casefold()
        if is_capability_intent(objective):
            return RoutedAction("capability", "system.capabilities",
                                {"objective": objective})
        repository = repository_action(objective, attachments)
        if repository:
            return repository
        if is_sales_request(objective):
            return RoutedAction("capability", "sales.plan", {"objective": objective})
        if is_game_creation_request(objective):
            return RoutedAction(
                "capability", "games.godot.scaffold",
                {"objective": objective, "name": _project_name(objective),
                 "genre": _game_genre(objective.casefold())}, True)
        if (is_programming_creation_request(objective) and
            _programming_language(objective.casefold()) == "python"):
            return RoutedAction(
                "capability", "project.stage",
                {"objective": objective}, True)
        if len(objective.split()) < 5:
            cache_key = hash(objective) % 10000
            if cache_key in self._plan_cache:
                return self._plan_cache[cache_key]
            low = objective.casefold()
            if is_capability_intent(objective):
                result = RoutedAction("capability", "system.capabilities",
                                      {"objective": objective})
                self._plan_cache[cache_key] = result
                return result
            if any(phrase in low for phrase in ("herramientas", "programas instalados")):
                result = RoutedAction("capability", "system.tools")
                self._plan_cache[cache_key] = result
                return result
        plan = self.director.plan(Mission(objective))
        if is_capability_intent(objective):
            return RoutedAction("capability", "system.capabilities",
                                {"objective": objective})
        if any(phrase in low for phrase in (
                "herramientas disponibles", "herramientas tienes",
                "programas instalados")):
            return RoutedAction("capability", "system.tools")
        source = str(Path(attachments[0]).resolve()) if attachments else ""
        if any(phrase in low for phrase in (
                "coordina especialistas", "revisi\u00f3n cruzada",
                "revision cruzada", "equipo de especialistas")):
            return RoutedAction(
                "capability", "mission.coordinate",
                {"objective": objective}, True)
        if source and any(word in low for word in ("redimensiona", "resize", "escala")):
            width, height = _dimensions(low)
            return RoutedAction(
                "capability", "image.resize",
                {"source": source, "output": "imagen_redimensionada.png",
                 "width": width, "height": height}, True)
        if source and any(word in low for word in ("extrae audio", "extraer audio", "a mp3")):
            return RoutedAction(
                "capability", "multimedia.extract_audio",
                {"source": source, "output": "audio_extraido.mp3"}, True)
        if source and any(word in low for word in ("miniatura", "fotograma", "thumbnail")):
            return RoutedAction(
                "capability", "multimedia.thumbnail",
                {"source": source, "output": "miniatura.png"}, True)
        if source and any(word in low for word in ("convierte", "transcodifica", "a mp4")):
            return RoutedAction(
                "capability", "multimedia.transcode",
                {"source": source, "output": "video_convertido.mp4"}, True)
        if source and any(phrase in low for phrase in (
                "edita este video", "procesa este video", "prepara este video",
                "edita el video", "procesa el video")):
            return RoutedAction(
                "capability", "multimedia.pipeline",
                {"source": source, "operations": [
                    {"kind": "thumbnail", "output": "preview.png", "second": 0},
                    {"kind": "transcode", "output": "video_final.mp4"},
                ]}, True)
        if source and any(word in low for word in (
                "verifica", "valida", "comprueba", "revisa visualmente")):
            return RoutedAction(
                "capability", "multimedia.verify", {"source": source})
        if attachments and any(word in low for word in (
                "analiza", "revisa", "inspecciona", "resume", "archivos")):
            return RoutedAction(
                "capability", "files.inspect",
                {"sources": [str(Path(item).resolve()) for item in attachments]})
        if plan.branch is MissionBranch.PROGRAMMING and "python" in low:
            return RoutedAction(
                "capability", "programming.python.develop",
                {"objective": objective}, True)
        if plan.branch is MissionBranch.PROGRAMMING:
            language = _programming_language(low)
            return RoutedAction(
                "capability", "programming.autonomous.develop",
                {"objective": objective, "language": language}, True)
        if plan.branch is MissionBranch.GAMES and any(
                word in low for word in ("exporta", "compila", "ejecutable",
                                         "exe", "build", "empaqueta")):
            return RoutedAction(
                "capability", "games.godot.export", {}, True)
        if plan.branch is MissionBranch.GAMES and any(
            word in low for word in ("crea", "construye", "genera")):
            return RoutedAction(
                "capability", "games.godot.scaffold",
                {"name": _project_name(objective),
                 "genre": _game_genre(low)}, True)
        if plan.branch is MissionBranch.GAMES and any(
                word in low for word in ("prueba", "ejecuta", "corre",
                                         "playtest", "comprueba el juego",
                                         "verifica el juego")):
            return RoutedAction(
                "capability", "games.godot.playtest", {}, True)
        if any(phrase in low for phrase in (
                "di algo", "di ", "pronuncia", "recita", "lee en voz alta",
                "habla ahora", "repite esto", "reproduce este texto",
                "reproduce el texto")):
            return RoutedAction(
                "capability", "voice.set",
                {"objective": objective, "text": objective}, False)
        return RoutedAction("chat")


def _programming_language(text: str) -> str:
    languages = {
        "javascript": ("javascript", "node.js", "nodejs"),
        "typescript": ("typescript",),
        "rust": ("rust",),
        "cpp": ("c++", "cpp"),
        "java": ("java",),
        "go": ("golang", "en go", "go lang", "programa go", "c\u00f3digo go", "codigo go"),
    }
    for language, aliases in languages.items():
        if any(alias in text for alias in aliases):
            return language
    return "python"


def _dimensions(text: str) -> tuple[int, int]:
    import re
    match = re.search(r"(\d{2,5})\s*[x\u00d7]\s*(\d{2,5})", text)
    if not match:
        return 1280, 720
    return min(16384, int(match.group(1))), min(16384, int(match.group(2)))


def _project_name(objective: str) -> str:
    explicit = re.search(r"\bnombre\s*[:;,-]?\s*(.+)$", objective,
                         flags=re.IGNORECASE)
    if explicit:
        name = explicit.group(1).strip(" .,;:!?")
        if name:
            return name[:80]
    words = [word.strip(".,;:!?") for word in objective.split()]
    ignored = {"crea", "construye", "genera", "un", "una", "juego",
               "videojuego", "en", "godot", "puedes", "crearme", "hacerme",
               "quiero", "que", "me", "el", "la", "de"}
    useful = [word for word in words if word.casefold() not in ignored]
    return " ".join(useful[:5]) or "Juego IGRIS"


def _game_genre(text: str) -> str:
    if any(word in text for word in ("plataformas", "platformer")):
        return "platformer"
    if any(word in text for word in ("arcade", "maquinas recreativas")):
        return "arcade"
    return "top_down"
