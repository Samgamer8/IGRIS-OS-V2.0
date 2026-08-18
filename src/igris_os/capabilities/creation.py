import hashlib
import mimetypes
from pathlib import Path

from igris_os.ai import OllamaClient
from igris_os.application import CapabilityRegistry, SpecialistCoordinator
from igris_os.delegation import (DelegatedSpecialist, DelegatedTask,
                                  OllamaSpecialist,
                                  build_resilient_specialist)
from igris_os.domain import ActionRisk, CapabilitySpec, ExecutionResult
from igris_os.evaluation import IndependentVerifier
from igris_os.games import GodotExporter, GodotProjectFactory, GameVerifier
from igris_os.files import RepositoryAnalyzer, RepositoryStager
from igris_os.multimedia import (ImageEngine, MediaEngine, MediaPipeline,
                                 VisualVerifier)
from igris_os.programming import (
    AutonomousProgrammingCoordinator, MultiLanguageCoordinator,
    MultiLanguageVerifier, PythonProjectDeveloper,
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
        CapabilitySpec("programming.autonomous.develop",
                       "Desarrollo autonomo con arquitecto, programador y revisor",
                       ActionRisk.WRITE_WORKSPACE, True), _develop_autonomous)
    registry.register(
        CapabilitySpec("programming.multilang.develop",
                       "Genera y verifica un proyecto en varios lenguajes",
                       ActionRisk.WRITE_WORKSPACE, True), _develop_multilang)
    registry.register(
        CapabilitySpec("games.godot.scaffold",
                       "Crea una base de proyecto Godot",
                       ActionRisk.WRITE_WORKSPACE, True), _godot)
    registry.register(
        CapabilitySpec("games.godot.playtest",
                       "Arranca un juego Godot y verifica que renderiza",
                       ActionRisk.WRITE_WORKSPACE, True), _godot_playtest)
    registry.register(
        CapabilitySpec("games.godot.export",
                       "Exporta un proyecto Godot a ejecutable Windows",
                       ActionRisk.WRITE_WORKSPACE, True), _godot_export)
    registry.register(
        CapabilitySpec("multimedia.status",
                       "Comprueba FFmpeg y FFprobe",
                       ActionRisk.READ_ONLY), _media_status)
    registry.register(
        CapabilitySpec("multimedia.verify",
                       "Verifica visualmente una imagen o video",
                       ActionRisk.READ_ONLY), _verify_media)
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
    registry.register(
        CapabilitySpec("mission.coordinate",
                       "Coordina especialistas con revision cruzada",
                       ActionRisk.WRITE_WORKSPACE, True), _coordinate)
    registry.register(
        CapabilitySpec("delivery.verify",
                       "Revision independiente de una entrega con segundo modelo",
                       ActionRisk.READ_ONLY), _verify_delivery)
    registry.register(
        CapabilitySpec("programming.delegate",
                       "Delega una tarea a un especialista externo (Claude Code u Ollama local) con auto-reparacion",
                       ActionRisk.WRITE_WORKSPACE, True), _delegate)
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
    verifier = MultiLanguageVerifier(Path("/"))
    return ExecutionResult.success(
        "Lenguajes registrados",
        languages=[{"name": profile.language.value,
                    "extensions": profile.extensions,
                    "available": True}
                   for profile in verifier.PROFILES.values()])


def _develop_python(payload):
    objective = str(payload.get("objective", "")).strip()
    model = str(payload.get("model", "qwen2.5-coder:7b"))
    client = OllamaClient(timeout=float(payload.get("timeout", 180)))
    result = PythonProjectDeveloper(
        client, Path(payload["workspace"]), model).develop(
            objective, confirmed=True,
            on_progress=payload.get("on_progress"))
    if not result.ok:
        return ExecutionResult.failure(result.message, "DEVELOPMENT_FAILED")
    readme = Path(result.project) / "README.md"
    deliverable = (readme.read_text(encoding="utf-8")
                   if readme.is_file() else result.message)
    verdict = IndependentVerifier(client).verify(
        deliverable, objective,
        acceptance=("codigo ejecutable sin efectos destructivos",
                    "pruebas que pasan", "uso documentado"),
        generator_model=model)
    if verdict.skipped:
        return ExecutionResult.success(
            result.message, project=result.project,
            attempts=result.attempts, independent_review="omitted")
    if not verdict.approved:
        return ExecutionResult(
            ok=False, code="INDEPENDENT_VERIFICATION_FAILED",
            message=(f"Verificador independiente rechazo la entrega "
                     f"({verdict.score:.0f}/100): {verdict.reason}"),
            data={"project": result.project, "score": verdict.score,
                  "verifier_model": verdict.verifier_model})
    return ExecutionResult.success(
        result.message, project=result.project, attempts=result.attempts,
        independent_score=verdict.score,
        verifier_model=verdict.verifier_model)


def _develop_autonomous(payload):
    objective = str(payload.get("objective", "")).strip()
    language = str(payload.get("language", "python")).strip()
    model = str(payload.get("model", "qwen2.5-coder:7b"))
    client = OllamaClient(timeout=float(payload.get("timeout", 120)))
    coordinator = AutonomousProgrammingCoordinator(
        client, Path(payload["workspace"]), default_model=model)
    result = coordinator.execute(
        objective, confirmed=True,
        on_progress=payload.get("on_progress"))
    if not result.ok:
        return ExecutionResult.failure(result.message, "AUTONOMOUS_FAILED")
    return ExecutionResult.success(
        result.message,
        plan=result.plan.plan if result.plan else "",
        deliverables=result.plan.modules if result.plan else (),
        acceptance_criteria=result.plan.acceptance if result.plan else (),
        review_score=result.review.score if result.review else 0.0,
        attempts=result.attempts,
    )


def _as_tuple(value) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value)
    return ()


def _delegate(payload):
    objective = str(payload.get("objective", "")).strip()
    workspace = Path(payload["workspace"])
    backend = str(payload.get("backend", "auto")).strip().lower()
    local_model = str(payload.get("model", "qwen2.5-coder:7b"))

    if backend == "claude":
        try:
            specialist = DelegatedSpecialist()
        except FileNotFoundError as exc:
            return ExecutionResult.failure(str(exc), "CLAUDE_NOT_AVAILABLE")
        task_model = str(payload.get("model", ""))
    elif backend == "ollama":
        specialist = OllamaSpecialist(model=local_model)
        task_model = ""
    else:  # auto: Claude primero, Ollama local como respaldo
        specialist = build_resilient_specialist(local_model=local_model)
        task_model = str(payload.get("model", ""))

    task = DelegatedTask(
        objective=objective,
        workspace=workspace,
        acceptance=_as_tuple(payload.get("acceptance")),
        constraints=_as_tuple(payload.get("constraints")),
        max_turns=int(payload.get("max_turns", 20)),
        timeout_seconds=int(payload.get("timeout", 600)),
        model=task_model,
        verify_command=_as_tuple(payload.get("verify_command")),
        target_files=_as_tuple(payload.get("target_files")),
    )
    result = specialist.run(
        task, max_attempts=max(1, int(payload.get("max_attempts", 3))))
    detail = result.stderr[-500:] if result.stderr else ""
    common = {"changed_files": result.changed_files,
              "sandboxed": result.sandboxed,
              "timed_out": result.timed_out,
              "containment_violations": result.containment_violations,
              "attempts": result.attempts,
              "verification_history": list(result.verification_history)}
    if not result.ok:
        return ExecutionResult(
            ok=False, code="DELEGATION_FAILED",
            message=result.message + (" · " + detail if detail else ""),
            data=common)
    return ExecutionResult.success(
        result.message,
        changed_files=result.changed_files,
        verified=result.verified,
        sandboxed=result.sandboxed,
        containment_violations=result.containment_violations,
        attempts=result.attempts)


def _verify_delivery(payload):
    acceptance = payload.get("acceptance", ())
    if not isinstance(acceptance, (list, tuple)):
        acceptance = ()
    verdict = IndependentVerifier(
        OllamaClient(timeout=float(payload.get("timeout", 180)))).verify(
            str(payload.get("deliverable", "")),
            str(payload.get("objective", "")).strip(),
            tuple(str(item) for item in acceptance),
            str(payload.get("generator_model", "")))
    return ExecutionResult.success(
        "Revision independiente completada",
        approved=verdict.approved,
        score=round(verdict.score, 1),
        reason=verdict.reason,
        generator_model=verdict.generator_model,
        verifier_model=verdict.verifier_model,
        skipped=verdict.skipped)


def _develop_multilang(payload):
    objective = str(payload.get("objective", "")).strip()
    language = str(payload.get("language", "")).strip()
    model = str(payload.get("model", "qwen2.5-coder:7b"))
    client = OllamaClient(timeout=float(payload.get("timeout", 120)))
    result = MultiLanguageCoordinator(
        client, Path(payload["workspace"]), default_model=model).develop(
            objective, language=language, confirmed=True,
            on_progress=payload.get("on_progress"))
    if not result.ok:
        return ExecutionResult.failure(result.message, "DEVELOPMENT_FAILED")
    return ExecutionResult.success(result.message, language=language)


def _godot(payload):
    name = str(payload.get("name", "Juego IGRIS"))
    project = GodotProjectFactory(Path(payload["workspace"])).create(
        name, genre=str(payload.get("genre", "top_down")), confirmed=True)
    return ExecutionResult.success("Proyecto Godot creado", project=str(project))


def _godot_export(payload):
    workspace = Path(payload["workspace"])
    explicit = payload.get("project")
    if explicit:
        project = Path(str(explicit))
    else:
        candidates = sorted(workspace.glob("*/project.godot"))
        project = candidates[0].parent if candidates else workspace
    output = workspace / str(payload.get("output", "build/igris_game.exe"))
    result = GodotExporter().export(project, output, confirmed=True)
    if not result.ok:
        return ExecutionResult(
            ok=False, code="GAME_EXPORT_UNVERIFIED",
            message=result.message + (" · " + result.verification if result.verification else ""),
            data={"executable": result.executable, "size": result.size})
    return ExecutionResult.success(
        result.message, executable=result.executable, size=result.size,
        verification=result.verification)


def _godot_playtest(payload):
    workspace = Path(payload["workspace"])
    explicit = payload.get("project")
    if explicit:
        project = Path(str(explicit))
    else:
        candidates = sorted(workspace.glob("*/project.godot"))
        project = candidates[0].parent if candidates else workspace
    reference = payload.get("reference")
    result = GameVerifier().playtest(
        project, capture_dir=workspace,
        reference=Path(str(reference)) if reference else None)
    return ExecutionResult.success(
        "Playtest completado",
        verified=result.ok,
        detail=result.message,
        boot_ok=result.boot_ok,
        visual_ok=result.visual_ok,
        reference_ok=result.reference_ok,
        similarity=round(result.similarity, 3),
        capture=result.capture_path,
        godot_version=result.version)


def _media_status(payload):
    engine = MediaEngine(Path(payload["workspace"]))
    return ExecutionResult.success("Multimedia inspeccionada",
                                   available=engine.available)


def _verify_media(payload):
    source = payload.get("source")
    if not source:
        return ExecutionResult.failure(
            "Falta el archivo a verificar", "VERIFY_MISSING_SOURCE")
    check = VisualVerifier().verify(Path(str(source)))
    return ExecutionResult.success(
        "Verificacion visual completada",
        verified=check.ok,
        detail=check.message,
        width=check.width,
        height=check.height,
        mean_brightness=round(check.mean_brightness, 2),
        std_brightness=round(check.std_brightness, 2),
        blank=check.blank,
        uniform_borders=list(check.uniform_borders),
        duration=check.duration,
        codec=check.codec)


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
            Path(payload["root"]), str(payload.get("query", "")),
            on_progress=payload.get("on_progress"))
    except ValueError as exc:
        return ExecutionResult.failure(str(exc), "REPOSITORY_INVALID")
    records = [{"path": item["path"], "symbols": item.get("symbols", []),
                "text": item.get("text", "")[:600]}
               for item in report.records]
    return ExecutionResult.success(
        "Repositorio analizado y mapeado", repository={
            "files": report.files, "bytes_read": report.bytes_read,
            "languages": report.languages, "symbols": len(report.symbols),
            "imports": len(report.imports), "tests": len(report.tests),
            "matches": report.matches, "manifest": report.manifest,
            "truncated": report.truncated, "records": records})


def _repository_stage(payload):
    try:
        result = RepositoryStager(Path(payload["workspace"])).stage(
            Path(payload["root"]), confirmed=True,
            on_progress=payload.get("on_progress"))
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
            confirmed=True, on_progress=payload.get("on_progress"))
    if not result.ok:
        return ExecutionResult.failure(result.message, "REPOSITORY_DEVELOP_FAILED")
    return ExecutionResult.success(
        result.message, repository_changes={
            "staged_root": result.staged_root, "report": result.report,
            "changed_files": result.changed_files,
            "original_modified": False})


def _coordinate(payload):
    model = str(payload.get("model", "qwen2.5-coder:7b"))
    result = SpecialistCoordinator(
        OllamaClient(timeout=float(payload.get("timeout", 240))),
        Path(payload["workspace"]) / "evidence").coordinate(
            str(payload.get("objective", "")), model,
            on_progress=payload.get("on_progress"))
    if not result.complete:
        return ExecutionResult.failure(
            "La coordinacion no supero todos los especialistas",
            "COORDINATION_INCOMPLETE")
    return ExecutionResult.success(
        "Coordinacion y revision cruzada completadas",
        coordination={"branch": result.branch,
                      "specialists": len(result.findings),
                      "reviewed": result.review.ok,
                      "evidence": result.evidence_path})


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


from igris_os.voice import WindowsVoice


def _media_pipeline(payload):
    operations = payload.get("operations", [])
    if not isinstance(operations, list):
        return ExecutionResult.failure("Plan multimedia invalido", "MEDIA_FAILED")
    result = MediaPipeline(Path(payload["workspace"])).execute(
        Path(payload["source"]), operations, confirmed=True,
        on_progress=payload.get("on_progress"))
    if not result.ok:
        return ExecutionResult(
            ok=False,
            message=result.message + ("; rollback aplicado" if result.rolled_back else ""),
            code="MEDIA_PIPELINE_FAILED",
            data={"report": result.report, "rolled_back": result.rolled_back})
    return ExecutionResult.success(
        result.message, outputs=result.outputs, report=result.report)
