import hashlib
import mimetypes
from pathlib import Path

from igris_os.ai import OllamaClient
from igris_os.application import CapabilityRegistry
from igris_os.domain import ActionRisk, CapabilitySpec, ExecutionResult
from igris_os.games import GodotProjectFactory
from igris_os.multimedia import ImageEngine, MediaEngine
from igris_os.programming import (
    LanguageVerifier, MultiLanguageDeveloper, PythonProjectDeveloper,
)


def register_creation_capabilities(registry: CapabilityRegistry) -> None:
    registry.register(
        CapabilitySpec("programming.languages", "Lenguajes y compiladores",
                       ActionRisk.READ_ONLY), _languages)
    registry.register(
        CapabilitySpec("programming.python.develop",
                       "Genera, prueba y entrega un proyecto Python",
                       ActionRisk.WRITE_WORKSPACE, True), _develop_python)
    registry.register(
        CapabilitySpec("programming.multilang.develop",
                       "Genera y verifica un proyecto en varios lenguajes",
                       ActionRisk.WRITE_WORKSPACE, True), _develop_multilang)
    registry.register(
        CapabilitySpec("games.godot.scaffold",
                       "Crea una base de proyecto Godot",
                       ActionRisk.WRITE_WORKSPACE, True), _godot)
    registry.register(
        CapabilitySpec("multimedia.status",
                       "Comprueba FFmpeg y FFprobe",
                       ActionRisk.READ_ONLY), _media_status)
    registry.register(
        CapabilitySpec("files.inspect", "Inspecciona archivos adjuntos",
                       ActionRisk.READ_ONLY), _inspect_files)
    for name, description, handler in (
        ("image.resize", "Redimensiona una imagen", _resize_image),
        ("multimedia.extract_audio", "Extrae audio de un archivo", _extract_audio),
        ("multimedia.thumbnail", "Extrae una miniatura de video", _thumbnail),
        ("multimedia.transcode", "Convierte video a MP4", _transcode),
    ):
        registry.register(CapabilitySpec(
            name, description, ActionRisk.WRITE_WORKSPACE, True), handler)


def _languages(_):
    verifier = LanguageVerifier()
    return ExecutionResult.success(
        "Lenguajes registrados",
        languages=[{"name": profile.name, "extensions": profile.extensions}
                   for profile in verifier.profiles()])


def _develop_python(payload):
    objective = str(payload.get("objective", "")).strip()
    model = str(payload.get("model", "qwen2.5-coder:7b"))
    client = OllamaClient(timeout=float(payload.get("timeout", 180)))
    result = PythonProjectDeveloper(
        client, Path(payload["workspace"]), model).develop(
            objective, confirmed=True)
    if not result.ok:
        return ExecutionResult.failure(result.message, "DEVELOPMENT_FAILED")
    return ExecutionResult.success(result.message, project=result.project,
                                   attempts=result.attempts)


def _develop_multilang(payload):
    objective = str(payload.get("objective", "")).strip()
    language = str(payload.get("language", "")).strip()
    model = str(payload.get("model", "qwen2.5-coder:7b"))
    client = OllamaClient(timeout=float(payload.get("timeout", 180)))
    result = MultiLanguageDeveloper(
        client, Path(payload["workspace"]), model).develop(
            objective, language, confirmed=True)
    if not result.ok:
        return ExecutionResult.failure(result.message, "DEVELOPMENT_FAILED")
    return ExecutionResult.success(result.message, project=result.project,
                                   attempts=result.attempts, language=language)


def _godot(payload):
    name = str(payload.get("name", "Juego IGRIS"))
    project = GodotProjectFactory(Path(payload["workspace"])).create(
        name, confirmed=True)
    return ExecutionResult.success("Proyecto Godot creado", project=str(project))


def _media_status(payload):
    engine = MediaEngine(Path(payload["workspace"]))
    return ExecutionResult.success("Multimedia inspeccionada",
                                   available=engine.available)


def _inspect_files(payload):
    inspected = []
    total_read = 0
    max_total = 32 * 1024 * 1024
    for raw in list(payload.get("sources", []))[:50]:
        path = Path(str(raw)).resolve()
        if not path.is_file() or path.is_symlink():
            continue
        size = path.stat().st_size
        item = {"name": path.name, "path": str(path), "size": size,
                "mime": mimetypes.guess_type(path.name)[0] or
                        "application/octet-stream"}
        if size <= 16 * 1024 * 1024 and total_read + size <= max_total:
            data = path.read_bytes()
            total_read += size
            item["sha256"] = hashlib.sha256(data).hexdigest()
            if item["mime"].startswith("text/") or path.suffix.casefold() in {
                    ".py", ".js", ".ts", ".json", ".md", ".txt", ".csv"}:
                item["preview"] = data.decode("utf-8", errors="replace")[:4000]
        inspected.append(item)
    if not inspected:
        return ExecutionResult.failure("No hay archivos validos", "NO_FILES")
    return ExecutionResult.success(
        f"{len(inspected)} archivo(s) inspeccionado(s)", files=inspected)


def _media_result(result):
    if not result.ok:
        return ExecutionResult.failure(result.message, "MEDIA_FAILED")
    return ExecutionResult.success(result.message, output=result.output)


def _resize_image(payload):
    result = ImageEngine(Path(payload["workspace"])).resize(
        Path(payload["source"]), str(payload.get("output", "imagen.png")),
        int(payload.get("width", 1280)), int(payload.get("height", 720)),
        confirmed=True)
    return _media_result(result)


def _extract_audio(payload):
    result = MediaEngine(Path(payload["workspace"])).extract_audio(
        Path(payload["source"]), str(payload.get("output", "audio.mp3")),
        confirmed=True)
    return _media_result(result)


def _thumbnail(payload):
    result = MediaEngine(Path(payload["workspace"])).thumbnail(
        Path(payload["source"]), str(payload.get("output", "miniatura.png")),
        float(payload.get("second", 0)), confirmed=True)
    return _media_result(result)


def _transcode(payload):
    result = MediaEngine(Path(payload["workspace"])).transcode(
        Path(payload["source"]), str(payload.get("output", "video.mp4")),
        confirmed=True)
    return _media_result(result)
