import hashlib
import mimetypes
from pathlib import Path

from igris_os.ai import OllamaClient
from igris_os.application import CapabilityRegistry
from igris_os.domain import ActionRisk, CapabilitySpec, ExecutionResult
from igris_os.games import GodotProjectFactory
from igris_os.files import RepositoryAnalyzer, RepositoryStager
from igris_os.multimedia import ImageEngine, MediaEngine, MediaPipeline
from igris_os.programming import (
    LanguageVerifier, MultiLanguageDeveloper, PythonProjectDeveloper,
    RepositoryDeveloper,
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
    registry.register(
        CapabilitySpec("repository.analyze",
                       "Mapea símbolos, dependencias y pruebas de un repositorio",
                       ActionRisk.WRITE_WORKSPACE, True), _repository_analyze)
    registry.register(
        CapabilitySpec("repository.stage",
                       "Crea una copia aislada y verificada de un repositorio",
                       ActionRisk.WRITE_WORKSPACE, True), _repository_stage)
    registry.register(
        CapabilitySpec("repository.develop",
                       "Propone cambios verificados sobre una copia aislada",
                       ActionRisk.WRITE_WORKSPACE, True), _repository_develop)
    for name, description, handler in (
        ("image.resize", "Redimensiona una imagen", _resize_image),
        ("multimedia.extract_audio", "Extrae audio de un archivo", _extract_audio),
        ("multimedia.thumbnail", "Extrae una miniatura de video", _thumbnail),
        ("multimedia.transcode", "Convierte video a MP4", _transcode),
        ("multimedia.pipeline", "Ejecuta un plan multimedia con rollback",
         _media_pipeline),
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


def _repository_analyze(payload):
    try:
        report = RepositoryAnalyzer(Path(payload["workspace"])).analyze(
            Path(payload["root"]), str(payload.get("query", "")))
    except ValueError as exc:
        return ExecutionResult.failure(str(exc), "REPOSITORY_INVALID")
    return ExecutionResult.success(
        "Repositorio analizado y mapeado", repository={
            "files": report.files, "bytes_read": report.bytes_read,
            "languages": report.languages, "symbols": len(report.symbols),
            "imports": len(report.imports), "tests": len(report.tests),
            "matches": report.matches, "manifest": report.manifest,
            "truncated": report.truncated})


def _repository_stage(payload):
    try:
        result = RepositoryStager(Path(payload["workspace"])).stage(
            Path(payload["root"]), confirmed=True)
    except (ValueError, OSError, PermissionError) as exc:
        return ExecutionResult.failure(str(exc), "REPOSITORY_STAGE_FAILED")
    return ExecutionResult.success(
        "Copia aislada del repositorio creada y verificada",
        staged_repository={"root": result.root, "files": result.files,
                           "total_bytes": result.total_bytes,
                           "manifest": result.manifest,
                           "verified": result.verified,
                           "truncated": result.truncated})


def _repository_develop(payload):
    client = OllamaClient(timeout=float(payload.get("timeout", 240)))
    result = RepositoryDeveloper(
        client, Path(payload["workspace"]),
        str(payload.get("model", "qwen2.5-coder:7b"))).propose(
            Path(payload["root"]), str(payload.get("objective", "")),
            confirmed=True)
    if not result.ok:
        return ExecutionResult.failure(result.message, "REPOSITORY_DEVELOP_FAILED")
    return ExecutionResult.success(
        result.message, repository_changes={
            "staged_root": result.staged_root, "report": result.report,
            "changed_files": result.changed_files,
            "original_modified": False})


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


def _media_pipeline(payload):
    operations = payload.get("operations", [])
    if not isinstance(operations, list):
        return ExecutionResult.failure("Plan multimedia invalido", "MEDIA_FAILED")
    result = MediaPipeline(Path(payload["workspace"])).execute(
        Path(payload["source"]), operations, confirmed=True)
    if not result.ok:
        return ExecutionResult(
            False,
            result.message + ("; rollback aplicado" if result.rolled_back else ""),
            "MEDIA_PIPELINE_FAILED",
            {"report": result.report, "rolled_back": result.rolled_back})
    return ExecutionResult.success(
        result.message, outputs=result.outputs, report=result.report)
