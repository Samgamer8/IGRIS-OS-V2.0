import hashlib
import json
import mimetypes
import shutil
from pathlib import Path

from igris_os.ai import OllamaClient
from igris_os.ai.model_selection import coding_model_candidates
from igris_os.application import (CapabilityRegistry, ProjectIntake,
                                  ProjectOffice, SalesOffice,
                                  SpecialistCoordinator)
from igris_os.application.project_lead import ProjectLead
from igris_os.delegation import (DelegatedSpecialist, DelegatedTask,
                                  OllamaSpecialist,
                                  build_resilient_specialist)
from igris_os.domain import ActionRisk, CapabilitySpec, ExecutionResult
from igris_os.evaluation import (IndependentVerifier, approved_models, is_model_approved,
                                 run_local_benchmark)
from igris_os.games import (
    GodotExporter, GodotGameDeveloper, GodotProjectFactory, GameVerifier,
)
from igris_os.files import (RepositoryAnalyzer, RepositoryChangeApplier,
                            RepositoryStager)
from igris_os.multimedia import (ImageEngine, MediaEngine, MediaPipeline,
                                 VisualVerifier)
from igris_os.programming import (
    AutonomousProgrammingCoordinator, MultiLanguageCoordinator,
    MultiLanguageVerifier, PythonProjectDeveloper,
    EngineeringAssessor, EngineeringWorkflow, ProgrammingPreflight,
    ChangeProposalBuilder, RepositoryDeveloper, LocalProgrammingTeam,
)


def register_creation_capabilities(registry: CapabilityRegistry) -> None:
    from igris_os.capabilities.neural_image import register_neural_image
    register_neural_image(registry)
    from igris_os.capabilities.programming_mission import register_programming_mission
    register_programming_mission(registry)
    registry.register(
        CapabilitySpec("games.godot.templates.find", "Busca plantillas Godot compatibles en carpetas locales",
                       ActionRisk.READ_ONLY, timeout_seconds=60), _find_godot_templates)
    registry.register(
        CapabilitySpec("games.godot.templates.install", "Descarga y verifica las plantillas oficiales de Godot",
                       ActionRisk.EXTERNAL, True, timeout_seconds=1200), _install_godot_templates)
    registry.register(
        CapabilitySpec("programming.preflight",
                       "Inspeccion tecnica de solo lectura con evidencia",
                       ActionRisk.READ_ONLY), _programming_preflight)
    registry.register(
        CapabilitySpec("programming.assess",
                       "Diagnostico tecnico con riesgos y pruebas propuestas",
                       ActionRisk.READ_ONLY), _programming_assess)
    registry.register(
        CapabilitySpec("programming.propose",
                       "Propone cambios con riesgos y pruebas requeridas",
                       ActionRisk.READ_ONLY), _programming_propose)
    registry.register(
        CapabilitySpec("programming.benchmark",
                       "Evalua localmente seguridad y ejecucion de programacion",
                       ActionRisk.READ_ONLY), _programming_benchmark)
    registry.register(
        CapabilitySpec("programming.execute_verified",
                       "Ejecuta un comando permitido dentro del sandbox",
                       ActionRisk.EXTERNAL, True, timeout_seconds=120),
        _programming_execute_verified)
    registry.register(
        CapabilitySpec("programming.languages", "Lenguajes y compiladores",
                       ActionRisk.READ_ONLY), _languages)
    registry.register(
        CapabilitySpec("programming.python.develop",
                       "Intenta generar un proyecto Python y entrega solo si pasa pruebas",
                       ActionRisk.WRITE_WORKSPACE, True), _develop_python)
    registry.register(
        CapabilitySpec("programming.python.multifile.develop",
                       "Genera un proyecto Python multiarchivo y entrega solo con pruebas",
                       ActionRisk.WRITE_WORKSPACE, True, timeout_seconds=900),
        _develop_python_multifile)
    registry.register(
        CapabilitySpec("project.lead",
                       "Recoge contrato, desarrolla y entrega con evidencia",
                       ActionRisk.WRITE_WORKSPACE, True), _project_lead)
    registry.register(
        CapabilitySpec("project.stage",
                       "Genera solo dentro de staging tras verificar el modelo",
                       ActionRisk.WRITE_WORKSPACE, True), _project_stage)
    registry.register(
        CapabilitySpec("project.deliver",
                       "Copia un staging verificado a la carpeta autorizada",
                       ActionRisk.WRITE_WORKSPACE, True), _project_deliver)
    registry.register(
        CapabilitySpec("project.plan",
                       "Planifica fases, riesgos y puertas de aceptación",
                       ActionRisk.READ_ONLY), _project_plan)
    registry.register(
        CapabilitySpec("sales.plan",
                       "Prepara un plan comercial y punto de equilibrio",
                       ActionRisk.READ_ONLY), _sales_plan)
    registry.register(
        CapabilitySpec("programming.autonomous.develop",
                       "Desarrolla proyectos multiarchivo y exige pruebas antes de entregar",
                       ActionRisk.WRITE_WORKSPACE, True, timeout_seconds=900), _develop_autonomous)
    registry.register(
        CapabilitySpec("programming.multilang.develop",
                       "Flujo experimental multilenguaje; entrega solo con verificación",
                       ActionRisk.WRITE_WORKSPACE, True), _develop_multilang)
    registry.register(
        CapabilitySpec("games.godot.scaffold",
                       "Crea una base de proyecto Godot",
                       ActionRisk.WRITE_WORKSPACE, True, timeout_seconds=3600), _godot)
    registry.register(
        CapabilitySpec("games.godot.resume", "Reanuda archivos Godot existentes con presupuesto y respaldo",
                       ActionRisk.EXTERNAL, True, timeout_seconds=3600), _resume_godot)
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
        CapabilitySpec("repository.repair",
                       "Repara un staging y acepta solo tests aprobados",
                       ActionRisk.WRITE_WORKSPACE, True), _repository_repair)
    registry.register(
        CapabilitySpec("repository.apply_verified",
                       "Aplica cambios verificados al original con respaldo y rollback",
                       ActionRisk.EXTERNAL, True), _repository_apply_verified)
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
    registry.register(
        CapabilitySpec("programming.team.execute",
                       "Director local, programador Ollama y validador independiente en secuencia",
                       ActionRisk.WRITE_WORKSPACE, True, timeout_seconds=1200),
        _programming_team_execute)
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


def _programming_preflight(payload):
    root = Path(str(payload.get("root", ""))).resolve()
    try:
        report = ProgrammingPreflight().inspect(root)
    except ValueError as exc:
        return ExecutionResult.failure(str(exc), "PREFLIGHT_INVALID")
    return ExecutionResult.success(
        "Preflight tecnico completado",
        root=report.root,
        files=report.files,
        python_files=report.python_files,
        test_files=report.test_files,
        truncated=report.truncated,
        ok=report.ok,
        findings=[{
            "severity": item.severity,
            "category": item.category,
            "path": item.path,
            "message": item.message,
            "evidence": item.evidence,
        } for item in report.findings],
    )


def _programming_assess(payload):
    try:
        assessment = EngineeringAssessor().assess(
            Path(str(payload.get("root", ""))),
            str(payload.get("objective", "")))
    except ValueError as exc:
        return ExecutionResult.failure(str(exc), "ASSESSMENT_INVALID")
    return ExecutionResult.success(
        "Evaluacion tecnica completada",
        root=assessment.root,
        facts=list(assessment.facts),
        risks=[{
            "severity": item.severity,
            "category": item.category,
            "path": item.path,
            "message": item.message,
            "evidence": item.evidence,
        } for item in assessment.risks],
        doubts=list(assessment.doubts),
        proposal=list(assessment.proposal),
        required_tests=list(assessment.required_tests),
        can_proceed=assessment.can_proceed,
    )


def _programming_propose(payload):
    try:
        proposal = ChangeProposalBuilder().build(
            Path(str(payload.get("root", ""))),
            str(payload.get("objective", "")))
    except ValueError as exc:
        return ExecutionResult.failure(str(exc), "PROPOSAL_INVALID")
    return ExecutionResult.success(
        "Propuesta tecnica preparada",
        objective=proposal.objective,
        affected_files=list(proposal.affected_files),
        changes=list(proposal.changes),
        risks=list(proposal.risks),
        tests=list(proposal.tests),
        requires_confirmation=proposal.requires_confirmation,
        can_apply=proposal.can_apply,
    )


def _programming_benchmark(_payload):
    result = run_local_benchmark()
    return ExecutionResult.success(
        "Benchmark local completado",
        passed=result["passed"],
        total=result["total"],
        passed_count=result["passed_count"],
        results=result["results"],
    )


def _programming_execute_verified(payload):
    workflow = EngineeringWorkflow()
    workspace = Path(str(payload.get("workspace", "."))).resolve()
    result = workflow.run(
        workspace, payload.get("command", ()), confirmed=True,
        timeout=int(payload.get("timeout", 30)))
    if not result.allowed:
        code = "PREFLIGHT_BLOCKED" if result.preflight and not result.preflight.ok else (
            "COMMAND_INVALID" if "lista" in result.reason else "COMMAND_NOT_ALLOWED")
        return ExecutionResult.failure(result.reason, code)
    run = result.run
    if run is None:
        return ExecutionResult.failure("No se ejecuto el comando", "EXECUTION_FAILED")
    return ExecutionResult.success(
        "Comando ejecutado en sandbox",
        command=list(payload.get("command", ())),
        returncode=run.returncode,
        stdout=run.stdout[:8000],
        stderr=run.stderr[:8000],
        timed_out=run.timed_out,
        sandboxed=run.sandboxed,
        ok=run.returncode == 0 and not run.timed_out,
        preflight_findings=[{
            "severity": item.severity,
            "category": item.category,
            "path": item.path,
            "message": item.message,
            "evidence": item.evidence,
        } for item in result.preflight.findings],
    )


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
    client = OllamaClient(timeout=float(payload.get("timeout", 180)))
    try:
        model, _fallbacks = _installed_programming_models(client, payload)
    except ValueError as exc:
        return ExecutionResult.failure(str(exc), "PROGRAMMING_MODEL_UNAVAILABLE")
    result = PythonProjectDeveloper(
        client, Path(payload["workspace"]), model).develop(
            objective, confirmed=True,
            on_progress=payload.get("on_progress"))
    if not result.ok:
        return ExecutionResult.failure(
            result.message, "DEVELOPMENT_FAILED",
            data={"diagnostics": list(result.diagnostics),
                  "models_tried": list(getattr(result, 'models_tried', []))},
        )
    staged_project = Path(result.project)
    delivered_project = staged_project
    destination = str(payload.get("delivery_root", "")).strip()
    if destination:
        delivery_root = Path(destination).expanduser().resolve()
        if not delivery_root.is_dir():
            return ExecutionResult.failure(
                "La carpeta de entrega no existe", "DELIVERY_PATH_INVALID")
        target = delivery_root / staged_project.name
        if target.exists():
            return ExecutionResult.failure(
                "Ya existe una entrega con ese nombre", "DELIVERY_PATH_EXISTS")
        shutil.copytree(staged_project, target)
        delivered_project = target
    readme = delivered_project / "README.md"
    deliverable = (readme.read_text(encoding="utf-8")
                   if readme.is_file() else result.message)
    verdict = IndependentVerifier(client).verify(
        deliverable, objective,
        acceptance=("codigo ejecutable sin efectos destructivos",
                    "pruebas que pasan", "uso documentado"),
        generator_model=model)
    if verdict.skipped:
        return ExecutionResult.success(
            result.message, project=str(delivered_project),
            staged_project=str(staged_project),
            attempts=result.attempts, independent_review="omitted")
    if not verdict.approved:
        return ExecutionResult(
            ok=False, code="INDEPENDENT_VERIFICATION_FAILED",
            message=(f"Verificador independiente rechazo la entrega "
                     f"({verdict.score:.0f}/100): {verdict.reason}"),
            data={"project": str(delivered_project), "score": verdict.score,
                  "verifier_model": verdict.verifier_model})
    return ExecutionResult.success(
        result.message, project=str(delivered_project),
        staged_project=str(staged_project), attempts=result.attempts,
        independent_score=verdict.score,
        verifier_model=verdict.verifier_model)


def _develop_python_multifile(payload):
    from igris_os.programming import PythonMultiFileDeveloper

    objective = str(payload.get("objective", "")).strip()
    if not objective:
        return ExecutionResult.failure("Falta el objetivo", "OBJECTIVE_REQUIRED")
    if "optimiz" in objective.casefold():
        objective += (
            " Usa datos reales del equipo mediante psutil si esta disponible y "
            "fallbacks de plataforma estandar; no hardcodees metricas ni procesos. "
            "La simulacion debe ser dry-run sin mutar archivos, la limpieza real "
            "solo puede mover temporales propios a un backup para rollback, debe "
            "registrar JSON y exigir confirmacion. Incluye pruebas de estas propiedades."
        )
    workspace = Path(payload["workspace"])
    domain_validator = None
    if "optimiz" in objective.casefold():
        def domain_validator(project: Path) -> str:
            diagnostics = _pc_optimizer_diagnostics(project)
            if not diagnostics["missing"] and not diagnostics["forbidden"]:
                return ""
            return json.dumps(diagnostics, ensure_ascii=False)
    client = OllamaClient(timeout=float(payload.get("timeout", 300)))
    try:
        model, automatic_fallbacks = _installed_programming_models(
            client, payload)
    except ValueError as exc:
        return ExecutionResult.failure(
            str(exc), "PROGRAMMING_MODEL_UNAVAILABLE",
            data={"models_tried": []})
    requested_fallbacks = payload.get("fallback_models")
    if isinstance(requested_fallbacks, (list, tuple)):
        requested = tuple(str(item) for item in requested_fallbacks)
        fallback_models = tuple(
            candidate for candidate in automatic_fallbacks
            if candidate in requested)
    else:
        fallback_models = automatic_fallbacks
    result = PythonMultiFileDeveloper(client, workspace, model).develop(
        objective, confirmed=True, attempts=min(5, max(1, int(payload.get("attempts", 3)))),
        componentized=bool(payload.get("componentized", False)),
        domain_validator=domain_validator,
        fallback_models=fallback_models,
    )
    if not result.ok or result.project is None:
        return ExecutionResult.failure(
            result.message, "DEVELOPMENT_FAILED",
            data={"diagnostics": list(result.diagnostics),
                  "models_tried": list(getattr(result, 'models_tried', [])),
                  "selected_model": model,
                  "fallback_models": list(fallback_models)},
        )
    # No implicit delivery to cwd; the verified staging is a usable result.
    target = result.project
    destination_text = str(payload.get("delivery_root", "")).strip()
    if destination_text:
        destination = Path(destination_text).expanduser().resolve()
        if not destination.is_dir():
            return ExecutionResult.failure("La carpeta de entrega no existe", "DELIVERY_PATH_INVALID")
        name = str(payload.get("delivery_name", result.project.name)).strip()
        if (not name or name in {".", ".."} or any(c in name for c in '/\\:')
                or name.endswith((".", " "))):
            return ExecutionResult.failure("Nombre de entrega invalido", "DELIVERY_PATH_INVALID")
        target = (destination / name).resolve()
        if target.parent != destination:
            return ExecutionResult.failure("Entrega fuera del destino autorizado", "DELIVERY_PATH_INVALID")
        if target.exists():
            return ExecutionResult.failure("Ya existe una entrega con ese nombre", "DELIVERY_PATH_EXISTS")
        shutil.copytree(result.project, target)
    return ExecutionResult.success(
        "Proyecto Python multiarchivo generado y verificado",
        project=str(target), staged_project=str(result.project),
        generated_files=list(result.files), attempts=getattr(result, "attempts", 0),
        models_tried=list(getattr(result, "models_tried", [])),
        selected_model=model, fallback_models=list(fallback_models),
        verified=True,
    )


def _installed_programming_models(client, payload) -> tuple[str, tuple[str, ...]]:
    """Elige únicamente modelos anunciados por los backends conectados."""

    installed = tuple(client.models())
    requested = str(payload.get("model", "")).strip()
    candidates = coding_model_candidates(installed, requested)
    if not candidates:
        raise ValueError(
            "No hay modelos de programacion locales utilizables. "
            "Modelos anunciados: " + (", ".join(installed) or "ninguno"))
    return candidates[0], candidates[1:]


def _validate_pc_optimizer(project: Path) -> bool:
    diagnostics = _pc_optimizer_diagnostics(project)
    return not diagnostics["missing"] and not diagnostics["forbidden"]


def _pc_optimizer_diagnostics(project: Path) -> dict[str, list[str]]:
    source = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in project.glob("*.py")
    ).casefold()
    required_signals = (
        "platform", "disk_usage", "process", "simulate", "rollback",
        "confirm", "audit",
    )
    forbidden_signals = ("simulated system", "usage': 20", "process1", "todo", "placeholder")
    return {
        "missing": [signal for signal in required_signals if signal not in source],
        "forbidden": [signal for signal in forbidden_signals if signal in source],
    }


def _project_lead(payload):
    objective = str(payload.get("objective", "")).strip()
    answers = payload.get("answers", {})
    if not isinstance(answers, dict):
        return ExecutionResult.failure("Contrato de proyecto invalido", "PROJECT_CONTRACT_INVALID")
    workspace = Path(payload["workspace"])
    audit_root = workspace.parent.parent / "audit"
    model = _approved_project_model(payload, audit_root)
    if not model:
        return ExecutionResult(
            ok=False, code="PROJECT_MODEL_NOT_QUALIFIED",
            message="No hay un modelo calificado para entregar proyectos",
            data={"requested_model": str(payload.get("model", "")),
                  "audit_root": str(audit_root)},
        )
    lead = ProjectLead(
        OllamaClient(timeout=float(payload.get("timeout", 300))),
        workspace, model,
    )
    result = lead.execute(objective, answers)
    contract = result.contract
    if not result.ok:
        return ExecutionResult(
            ok=False, code="PROJECT_NOT_DELIVERED", message=result.message,
            data={"questions": [question.prompt for question in contract.questions],
                  "technology": contract.technology},
        )
    return ExecutionResult.success(
        result.message, project=str(result.project),
        technology=contract.technology, delivery=contract.delivery,
        acceptance=list(contract.acceptance), verified=True)


def _project_stage(payload):
    objective = str(payload.get("objective", "")).strip()
    answers = payload.get("answers", {})
    if not isinstance(answers, dict):
        return ExecutionResult.failure("Contrato de proyecto invalido", "PROJECT_CONTRACT_INVALID")
    workspace = Path(payload["workspace"])
    audit_root = workspace.parent.parent / "audit"
    model = _approved_project_model(payload, audit_root)
    if not model:
        return ExecutionResult(
            ok=False, code="PROJECT_MODEL_NOT_QUALIFIED",
            message="No hay un modelo calificado para staging",
            data={"requested_model": str(payload.get("model", "")),
                  "audit_root": str(audit_root)},
        )
    result = ProjectLead(
        OllamaClient(timeout=float(payload.get("timeout", 300))), workspace, model,
    ).stage(objective, answers)
    if not result.ok or result.staged_project is None:
        return ExecutionResult(
            ok=False, code="PROJECT_STAGE_FAILED", message=result.message,
            data={"questions": [question.prompt for question in result.contract.questions]},
        )
    return ExecutionResult.success(
        result.message, staged_project=str(result.staged_project),
        model=model, technology=result.contract.technology,
        acceptance=list(result.contract.acceptance), verified=True)


def _approved_project_model(payload, audit_root: Path) -> str:
    requested = str(payload.get("model", "")).strip()
    if requested:
        return requested if is_model_approved(audit_root, requested) else ""
    models = approved_models(audit_root)
    return models[0] if models else ""


def _project_deliver(payload):
    objective = str(payload.get("objective", "")).strip()
    answers = payload.get("answers", {})
    staged = payload.get("staged_project", "")
    if not isinstance(answers, dict) or not staged:
        return ExecutionResult.failure("Datos de entrega invalidos", "PROJECT_DELIVERY_INVALID")
    workspace = Path(payload["workspace"])
    result = ProjectLead(None, workspace, "").deliver(
        objective, answers, Path(str(staged)))
    if not result.ok or result.project is None:
        return ExecutionResult.failure(result.message, "PROJECT_DELIVERY_FAILED")
    return ExecutionResult.success(
        result.message, project=str(result.project),
        staged_project=str(result.staged_project),
        technology=result.contract.technology,
        acceptance=list(result.contract.acceptance), verified=True)


def _project_plan(payload):
    answers = payload.get("answers", {})
    if not isinstance(answers, dict):
        return ExecutionResult.failure("Contrato de proyecto invalido", "PROJECT_CONTRACT_INVALID")
    try:
        contract = ProjectIntake().build(str(payload.get("objective", "")), answers)
    except ValueError as exc:
        return ExecutionResult.failure(str(exc), "PROJECT_CONTRACT_INVALID")
    if not contract.ready:
        return ExecutionResult.success(
            "Faltan decisiones para planificar",
            questions=[question.prompt for question in contract.questions])
    plan = ProjectOffice().plan(contract)
    return ExecutionResult.success(
        "Plan de proyecto preparado",
        project_plan={
            "project": plan.project_name,
            "phases": [{"name": phase.name, "outcome": phase.outcome,
                        "gate": phase.acceptance_gate} for phase in plan.phases],
            "risks": list(plan.risks), "dependencies": list(plan.dependencies),
        })


def _sales_plan(payload):
    answers = payload.get("answers", {})
    if not isinstance(answers, dict):
        return ExecutionResult.failure("Datos comerciales invalidos", "SALES_INPUT_INVALID")
    try:
        plan = SalesOffice().build(answers)
    except ValueError as exc:
        return ExecutionResult.failure(str(exc), "SALES_INPUT_INVALID")
    if not plan.ready:
        return ExecutionResult.success(
            "Faltan datos comerciales",
            questions=[question.prompt for question in plan.questions])
    return ExecutionResult.success(
        "Plan comercial preparado",
        sales_plan={
            "product": plan.product, "audience": plan.audience,
            "channel": plan.channel, "price": plan.price,
            "variable_cost": plan.variable_cost, "fixed_cost": plan.fixed_cost,
            "acquisition_budget": plan.acquisition_budget,
            "contribution_margin": plan.contribution_margin,
            "break_even_sales": plan.break_even_sales,
            "actions": list(plan.actions), "assumptions": list(plan.assumptions),
        })


def _develop_autonomous(payload):
    """Ruta principal: repositorio existente o proyecto multiarchivo verificable."""
    if str(payload.get("root", "")).strip():
        return _repository_develop(payload)
    language = str(payload.get("language", "python")).strip().casefold()
    if language != "python":
        return _develop_multilang(payload)
    return _develop_python_multifile(payload)


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


def _programming_team_execute(payload):
    """Orquesta los tres roles locales con verificación objetiva obligatoria."""
    from igris_os.delegation import DelegatedTask

    objective = str(payload.get("objective", "")).strip()
    if not objective or not str(payload.get("workspace", "")).strip():
        return ExecutionResult.failure(
            "Faltan objective o workspace", "INVALID_TEAM_TASK")
    verify_command = _as_tuple(payload.get("verify_command"))
    if not verify_command:
        return ExecutionResult.failure(
            "Indica verify_command; el equipo no acepta entregas sin pruebas",
            "VERIFICATION_REQUIRED")
    try:
        task = DelegatedTask(
            objective=objective,
            workspace=Path(payload["workspace"]),
            acceptance=_as_tuple(payload.get("acceptance")),
            constraints=_as_tuple(payload.get("constraints")),
            timeout_seconds=int(payload.get("timeout", 600)),
            target_files=_as_tuple(payload.get("target_files")),
            verify_command=verify_command,
            canaries=tuple(Path(item) for item in _as_tuple(payload.get("canaries"))),
        )
        team = LocalProgrammingTeam(
            director_model=str(payload.get("director_model", "deepseek-r1:8b")),
            programmer_model=str(payload.get("programmer_model", "qwen2.5-coder:7b")),
        )
        result = team.run(task, max_attempts=max(1, int(payload.get("max_attempts", 3))))
    except (KeyError, TypeError, ValueError) as exc:
        return ExecutionResult.failure(str(exc), "INVALID_TEAM_TASK")
    evidence = {
        "plan": result.plan,
        "changed_files": result.programmer.changed_files if result.programmer else (),
        "programmer_verified": result.programmer.verified if result.programmer else False,
        "validation_exit_code": result.validation.returncode if result.validation else None,
        "validation_sandboxed": result.validation.sandboxed if result.validation else False,
    }
    if not result.success:
        return ExecutionResult.failure(result.message, "TEAM_FAILED", data=evidence)
    return ExecutionResult.success(result.message, **evidence)


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
    if language.casefold() in {"javascript", "typescript", "web"}:
        from igris_os.production_bootstrap_release import _develop_node
        return _develop_node({**payload, "technology": language.casefold()})

    client = OllamaClient(timeout=float(payload.get("timeout", 120)))
    try:
        model, _fallbacks = _installed_programming_models(client, payload)
    except ValueError as exc:
        return ExecutionResult.failure(str(exc), "PROGRAMMING_MODEL_UNAVAILABLE")
    result = MultiLanguageCoordinator(
        client, Path(payload["workspace"]), default_model=model).develop(
            objective, language=language, confirmed=True,
            on_progress=payload.get("on_progress"))
    if not result.ok:
        return ExecutionResult.failure(
            result.message, "DEVELOPMENT_FAILED",
            data={"diagnostics": list(result.diagnostics),
                  "models_tried": list(getattr(result, 'models_tried', []))},
        )
    return ExecutionResult.success(result.message, language=language, project=result.project,
                                   generated_files=list(result.artifacts), verified=True)


def _find_godot_templates(payload):
    root = Path(payload["root"]).expanduser() if payload.get("root") else Path(__file__).resolve().parents[3]
    status = GodotExporter(search_root=root).template_status()
    lines = list(status["diagnostics"])
    if status["truncated"]:
        lines.append("Se alcanzo el limite de busqueda; indica una carpeta mas concreta.")
    status["diagnostics"] = lines
    return ExecutionResult.success(
        "Busqueda local terminada: plantillas compatibles encontradas" if status["ready"]
        else "Busqueda local terminada: no se encontraron plantillas compatibles. "
             "Puedes escribir: instala las plantillas de Godot.", template_search=status)


def _install_godot_templates(payload):
    from igris_os.games.template_install import install_templates
    from igris_os.games.runtime import GodotRuntime
    root = Path(payload["root"]).expanduser() if payload.get("root") else Path(__file__).resolve().parents[3]
    try:
        result = install_templates(GodotRuntime(), root, on_progress=payload.get("on_progress"))
        return ExecutionResult.success("Plantillas compatibles preparadas para IGRIS", **result)
    except (OSError, ValueError) as exc:
        return ExecutionResult(ok=False, code="GODOT_TEMPLATES_INSTALL_FAILED",
                               message="No se pudieron instalar las plantillas",
                               data={"diagnostics": [str(exc)]})


def _resume_godot(payload):
    if not payload.get("resume_project"):
        from igris_os.application.game_resume import resolve_game_resume, matching_game_jobs
        from igris_os.application.mission_queue import QueuedMission
        runtime = Path(payload["workspace"]).parent.parent
        try:
            rows = json.loads((runtime / "missions_queue.json").read_text(encoding="utf-8"))
            jobs = [QueuedMission(**row) for row in rows if isinstance(row, dict) and not row.get("payload", {}).get("request")]
        except (OSError, TypeError, ValueError):
            jobs = []
        objective = str(payload.get("request") or payload.get("objective", ""))
        matches = matching_game_jobs(objective, jobs)
        try:
            _, recovered = resolve_game_resume(objective, matches[-1] if matches else None, runtime)
        except (OSError, ValueError) as exc:
            return ExecutionResult.failure(str(exc), "GAME_RESUME_NOT_FOUND")
        payload = {**payload, **recovered}
    return _godot({**payload, "resume": True, "generate_full_code": True})


def _godot(payload):
    name = str(payload.get("name", "Juego IGRIS"))
    workspace = Path(payload["workspace"])
    resumed = bool(payload.get("resume"))
    resume_source = Path(str(payload.get("resume_project", ""))).expanduser().resolve() if resumed else None
    if resumed and (not payload.get("resume_project") or not (resume_source / "project.godot").is_file()):
        return ExecutionResult.failure("Falta la carpeta del proyecto existente; no se inicia otro", "GAME_RESUME_NOT_FOUND")
    expected_delivery = None
    resume_destination = None
    if resumed:
        from igris_os.games.resume_files import snapshot
        destination = payload.get("resume_destination")
        if destination:
            resume_destination = Path(destination).expanduser().resolve()
        elif payload.get("delivery_root"):
            delivery_root = Path(payload["delivery_root"]).expanduser().resolve()
            resume_destination = delivery_root / name
            legacy_destination = delivery_root / name.replace(" ", "_")
            if not resume_destination.exists() and legacy_destination.exists():
                resume_destination = legacy_destination
        if resume_destination and resume_destination.exists():
            if not (resume_destination / "project.godot").is_file():
                return ExecutionResult.failure("El destino existente no es un proyecto Godot", "GAME_RESUME_DESTINATION_INVALID")
            expected_delivery = snapshot(resume_destination)
    delivery_type = str(payload.get("delivery_type", "source"))
    if delivery_type not in {"source", "source_and_exe", "exe"}:
        return ExecutionResult.failure("Formato de entrega no soportado", "GAME_DELIVERY_INVALID")
    needs_exe = delivery_type in {"source_and_exe", "exe"}
    if needs_exe and not GodotExporter().templates_available():
        return ExecutionResult(
            ok=False, code="GAME_EXPORT_TEMPLATES_MISSING",
            message="Faltan las plantillas de Godot para entregar el ejecutable Windows",
            data={"diagnostics": ["Escribe 'busca las plantillas de Godot' para buscar archivos locales, "
                                  "o 'instala las plantillas de Godot' para descargar la version oficial exacta. "
                                  "Tambien puedes seleccionar Codigo fuente Godot."]})
    result_message = "Base de proyecto Godot creada; contiene una plantilla inicial"
    if payload.get("generate_full_code"):
        objective = str(payload.get("objective", ""))
        acceptance = str(payload.get("acceptance", ""))
        if acceptance:
            objective += "\nCRITERIOS DEL USUARIO: " + acceptance
        genre = str(payload.get("genre", "top_down"))
        is_chess = any(word in objective.casefold() for word in ("ajedrez", "chess"))
        chess_route = genre == "chess_3d" or (is_chess and "3d" in objective.casefold())
        bundled = chess_route and payload.get("generation_strategy", "bundled") != "model"
        client, model = None, ""
        if not bundled:
            client = OllamaClient(timeout=float(payload.get("timeout", 240)))
            from igris_os.ai.model_selection import select_coding_model
            try:
                model = select_coding_model(client.models(), str(payload.get("model") or ""))
            except ValueError as exc:
                return ExecutionResult.failure(str(exc), "GAME_MODEL_UNAVAILABLE")
            if not model:
                return ExecutionResult.failure("No hay un modelo local de generacion disponible", "GAME_MODEL_UNAVAILABLE")
        if chess_route:
            if bundled:
                from igris_os.games.bundled_chess import BundledChessDeveloper
                developer = BundledChessDeveloper(workspace, on_progress=payload.get("on_progress"))
            else:
                from igris_os.games.sequential_developer import SequentialGodotGameDeveloper
                developer = SequentialGodotGameDeveloper(client, workspace, model, on_progress=payload.get("on_progress"))
            developer.task_payload = {k: v for k, v in payload.items()
                                      if k not in {"workspace", "on_progress", "mission_id"} and not k.startswith("__")}
            if resumed:
                from igris_os.games.resume_files import clone_project
                try:
                    clone_project(resume_source, developer._project_path(name))
                except (OSError, ValueError) as exc:
                    return ExecutionResult.failure(str(exc), "GAME_RESUME_COPY_FAILED")
            result = developer.develop_chess_3d(objective, name, confirmed=True, **({"resume": True} if resumed else {}))
        else:
            result = GodotGameDeveloper(client, workspace, model).develop(
                objective, name, genre=genre, confirmed=True)
        if not result.ok or result.project is None:
            diagnostics = list(result.diagnostics) or [result.message]
            report_path = ""
            try:
                from uuid import uuid4
                workspace.mkdir(parents=True, exist_ok=True)
                report = workspace / ("ERROR_JUEGO_" + uuid4().hex[:12] + ".json")
                report.write_text(json.dumps({
                    "ok": False, "objective": objective, "model": model,
                    "message": result.message, "diagnostics": diagnostics,
                    "partial_project": str(result.project) if result.project else None,
                    "delivered": False,
                }, ensure_ascii=False, indent=2), encoding="utf-8")
                report_path = str(report)
            except OSError as exc:
                diagnostics.append("No se pudo guardar el informe: " + str(exc))
            return ExecutionResult(
                ok=False, code="GAME_CODE_GENERATION_FAILED",
                message=result.message,
                data={"diagnostics": diagnostics, "diagnostic_report": report_path,
                  "partial_project": str(result.project) if result.project else "",
                  "checkpoint": str(result.project / "IGRIS_PROGRESS.json") if result.project else "",
                  "models_tried": list(getattr(result, 'models_tried', []))},
            )
        project = result.project
        generated_files = getattr(result, "changed_files", getattr(result, "files", ()))
        result_message = result.message
    else:
        project = GodotProjectFactory(workspace).create(
            name, genre=str(payload.get("genre", "top_down")), confirmed=True)
        generated_files = ()
    if needs_exe:
        exported = GodotExporter().export(
            project, project / "build" / "juego.exe", confirmed=True)
        if not exported.ok:
            return ExecutionResult(
                ok=False, code="GAME_EXPORT_UNVERIFIED", message=exported.message,
                data={"diagnostics": [exported.verification or exported.message],
                      "partial_project": str(project)})
        if (project / "IGRIS_BASELINE.json").is_file():
            (project / "JUGAR.cmd").write_bytes(b'@echo off\r\nsetlocal DisableDelayedExpansion\r\ncd /d "%~dp0"\r\nstart "" "build\\juego.exe"\r\n')
    brief = payload.get("brief")
    if isinstance(brief, dict):
        (project / "PROJECT_BRIEF.json").write_text(
            json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8")
    delivered = project
    destination = str(payload.get("delivery_root", "")).strip()
    backup = ""
    applied_files = tuple(generated_files)
    if resumed and resume_destination is not None and expected_delivery is not None:
        from igris_os.games.resume_files import publish_changes
        try:
            backup = str(workspace / "before_resume_delivery")
            applied_files = tuple(publish_changes(project, resume_destination, expected_delivery, backup))
        except (OSError, ValueError) as exc:
            return ExecutionResult(False, "GAME_RESUME_DELIVERY_CONFLICT", str(exc),
                                   data={"partial_project": str(project), "diagnostics": [str(exc)]})
        delivered = resume_destination
    elif destination:
        delivery_root = Path(destination).expanduser().resolve()
        if not delivery_root.is_dir():
            return ExecutionResult.failure(
                "La carpeta de entrega no existe", "DELIVERY_PATH_INVALID")
        delivery_name = str(payload.get("name", project.name)).strip()
        if not delivery_name or delivery_name in {".", ".."} or any(c in delivery_name for c in '/\\:') or delivery_name.endswith((".", " ")):
            return ExecutionResult.failure("Nombre de entrega invalido", "DELIVERY_PATH_INVALID")
        target = delivery_root / delivery_name
        if target.exists():
            return ExecutionResult.failure(
                "Ya existe una entrega con ese nombre", "DELIVERY_PATH_EXISTS")
        shutil.copytree(project, target)
        delivered = target
    return ExecutionResult.success(
        result_message,
        project=str(delivered), staged_project=str(project),
        delivery_type=delivery_type,
        executable=str(delivered / "build" / "juego.exe") if needs_exe else "",
        acceptance_verified=False,
        updated_existing=bool(backup and applied_files), backup=backup,
        generated_files=generated_files, changed_files=applied_files,
        report=str(next((delivered / filename for filename in
                         ('IGRIS_VERIFICATION.json', 'CODE_DELIVERY.json')
                         if (delivered / filename).is_file()), '')))


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
    try:
        model, fallback_models = _installed_programming_models(client, payload)
    except ValueError as exc:
        return ExecutionResult.failure(str(exc), "PROGRAMMING_MODEL_UNAVAILABLE")
    developer = RepositoryDeveloper(
        client, Path(payload["workspace"]), model,
        fallback_models=fallback_models)
    objective = str(payload.get("objective", ""))
    result = developer.propose(Path(payload["root"]), objective, confirmed=True,
                               on_progress=payload.get("on_progress"))
    if not result.ok:
        return ExecutionResult.failure(result.message, "REPOSITORY_DEVELOP_FAILED")
    checked = developer.verify_staged(Path(result.staged_root))
    if not checked.ok:
        diagnostics = (Path(checked.report).read_text(encoding="utf-8")
                       if checked.report else checked.message)
        checked = developer.repair_until_verified(Path(result.staged_root), objective,
                                                   diagnostics, max_attempts=3,
                                                   on_progress=payload.get("on_progress"))
    if not checked.ok:
        return ExecutionResult.failure(checked.message, "REPOSITORY_NOT_VERIFIED", data={
            "staged_root": result.staged_root, "diagnostics": list(checked.diagnostics),
            "verified": False})
    return ExecutionResult.success(
        "Cambios del repositorio verificados en copia aislada", project=result.staged_root,
        verified=True, repository_changes={
            "staged_root": result.staged_root, "report": result.report,
            "staging_manifest": str(
                Path(payload["workspace"]).resolve() /
                "output" / "staging_manifest.json"),
            "verification_report": checked.report,
            "changed_files": tuple(dict.fromkeys((*result.changed_files, *checked.changed_files))),
            "original_modified": False})


def _repository_repair(payload):
    client = OllamaClient(timeout=float(payload.get("timeout", 120)))
    try:
        model, fallback_models = _installed_programming_models(client, payload)
    except ValueError as exc:
        return ExecutionResult.failure(str(exc), "PROGRAMMING_MODEL_UNAVAILABLE")
    developer = RepositoryDeveloper(
        client, Path(payload["workspace"]), model,
        fallback_models=fallback_models)
    result = developer.repair_until_verified(
        Path(payload["staged_root"]),
        str(payload.get("objective", "Corrige los tests")),
        str(payload.get("diagnostics", "")),
        max_attempts=min(3, max(1, int(payload.get("max_attempts", 3)))),
        timeout=min(120, max(1, int(payload.get("timeout", 60)))),
        on_progress=payload.get("on_progress"),
    )
    if not result.ok:
        return ExecutionResult.failure(result.message, "REPAIR_NOT_VERIFIED")
    return ExecutionResult.success(
        result.message,
        staged_root=result.staged_root,
        report=result.report,
        changed_files=result.changed_files,
        attempts=result.attempts,
        diagnostics=result.diagnostics,
        verified=True,
    )


def _repository_apply_verified(payload):
    workspace = Path(payload["workspace"]).resolve()
    staged_root = Path(payload["staged_root"]).resolve()
    verification = RepositoryDeveloper(
        None, workspace, "verification-only").verify_staged(
            staged_root,
            timeout=min(120, max(1, int(payload.get("timeout", 60)))))
    if not verification.ok:
        return ExecutionResult.failure(
            "El staging ya no supera sus pruebas; no se aplicó al original",
            "REPOSITORY_STAGING_NOT_VERIFIED",
            data={"diagnostics": verification.diagnostics,
                  "verification_report": verification.report})
    try:
        result = RepositoryChangeApplier(workspace).apply(
            Path(payload["source_root"]), staged_root,
            list(payload.get("changed_files", ())),
            Path(payload["staging_manifest"]), confirmed=True)
    except (ValueError, OSError, PermissionError, json.JSONDecodeError) as exc:
        return ExecutionResult.failure(str(exc), "REPOSITORY_APPLY_FAILED")
    return ExecutionResult.success(
        "Cambios verificados aplicados al repositorio original",
        updated_existing=True,
        verified=True,
        project=result.source_root,
        backup=result.backup_root,
        report=result.report,
        changed_files=result.changed_files,
    )


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
