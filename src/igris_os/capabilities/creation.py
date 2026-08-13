from pathlib import Path

from igris_os.ai import OllamaClient
from igris_os.application import CapabilityRegistry
from igris_os.domain import ActionRisk, CapabilitySpec, ExecutionResult
from igris_os.games import GodotProjectFactory
from igris_os.multimedia import MediaEngine
from igris_os.programming import LanguageVerifier, PythonProjectDeveloper


def register_creation_capabilities(registry: CapabilityRegistry) -> None:
    registry.register(
        CapabilitySpec("programming.languages", "Lenguajes y compiladores",
                       ActionRisk.READ_ONLY), _languages)
    registry.register(
        CapabilitySpec("programming.python.develop",
                       "Genera, prueba y entrega un proyecto Python",
                       ActionRisk.WRITE_WORKSPACE, True), _develop_python)
    registry.register(
        CapabilitySpec("games.godot.scaffold",
                       "Crea una base de proyecto Godot",
                       ActionRisk.WRITE_WORKSPACE, True), _godot)
    registry.register(
        CapabilitySpec("multimedia.status",
                       "Comprueba FFmpeg y FFprobe",
                       ActionRisk.READ_ONLY), _media_status)


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


def _godot(payload):
    name = str(payload.get("name", "Juego IGRIS"))
    project = GodotProjectFactory(Path(payload["workspace"])).create(
        name, confirmed=True)
    return ExecutionResult.success("Proyecto Godot creado", project=str(project))


def _media_status(payload):
    engine = MediaEngine(Path(payload["workspace"]))
    return ExecutionResult.success("Multimedia inspeccionada",
                                   available=engine.available)
