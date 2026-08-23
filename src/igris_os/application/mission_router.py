from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from igris_os.application.director import LLMMissionDirector, MissionDirector
from igris_os.domain import Mission, MissionBranch


@dataclass(frozen=True, slots=True)
class RoutedAction:
    kind: str
    capability: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    requires_confirmation: bool = False


class MissionRouter:
    def __init__(self, *, use_llm_director: bool = True) -> None:
        self.use_llm_director = use_llm_director
        self.director = LLMMissionDirector() if use_llm_director else MissionDirector()
        self._plan_cache = {}

    def route(self, objective: str,
              attachments: Sequence[str] = ()) -> RoutedAction:
        if len(objective.split()) < 5:
            cache_key = hash(objective) % 10000
            if cache_key in self._plan_cache:
                return self._plan_cache[cache_key]
            low = objective.casefold()
            if any(phrase in low for phrase in ("tus funciones", "tus capacidades", "qué puedes hacer", "que puedes hacer")):
                result = RoutedAction("capability", "system.capabilities")
                self._plan_cache[cache_key] = result
                return result
            if any(phrase in low for phrase in ("herramientas", "programas instalados")):
                result = RoutedAction("capability", "system.tools")
                self._plan_cache[cache_key] = result
                return result
        plan = self.director.plan(Mission(objective))
        low = objective.casefold()
        if any(phrase in low for phrase in (
                "tus funciones", "tus capacidades", "qu\u00e9 puedes hacer",
                "que puedes hacer", "capacidades tienes")):
            return RoutedAction("capability", "system.capabilities")
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
        if source and Path(source).is_dir() and any(word in low for word in (
                "modifica", "arregla", "implementa", "corrige", "programa")):
            return RoutedAction(
                "capability", "repository.develop",
                {"root": source, "objective": objective}, True)
        if source and Path(source).is_dir() and any(phrase in low for phrase in (
                "copia aislada", "prepara este proyecto", "trabaja en este proyecto",
                "prepara el repositorio")):
            return RoutedAction(
                "capability", "repository.stage", {"root": source}, True)
        if source and Path(source).is_dir() and any(word in low for word in (
                "repositorio", "proyecto", "c\u00f3digo", "codigo", "carpeta")):
            return RoutedAction(
                "capability", "repository.analyze",
                {"root": source, "query": objective}, True)
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
    words = [word.strip(".,;:!?") for word in objective.split()]
    ignored = {"crea", "construye", "genera", "un", "una", "juego",
               "videojuego", "en", "godot"}
    useful = [word for word in words if word.casefold() not in ignored]
    return " ".join(useful[:5]) or "Juego IGRIS"


def _game_genre(text: str) -> str:
    if any(word in text for word in ("plataformas", "platformer")):
        return "platformer"
    if any(word in text for word in ("arcade", "maquinas recreativas")):
        return "arcade"
    return "top_down"
