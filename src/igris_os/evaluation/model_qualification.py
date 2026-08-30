from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import tempfile
import time
from typing import Callable

from igris_os.programming import PythonMultiFileDeveloper, PythonProjectDeveloper


@dataclass(frozen=True, slots=True)
class QualificationCase:
    name: str
    objective: str


@dataclass(frozen=True, slots=True)
class QualificationResult:
    name: str
    passed: bool
    message: str
    project_files: tuple[str, ...]
    duration_seconds: float


@dataclass(frozen=True, slots=True)
class ModelQualification:
    model: str
    approved: bool
    results: tuple[QualificationResult, ...]


class ProgrammingModelQualifier:
    """Aprueba un modelo solo si entrega proyectos reales con evidencia local."""

    CASES = (
        QualificationCase(
            "todo_memory",
            "Crea una aplicación Python de consola para gestionar tareas en memoria. "
            "Debe crear, listar y completar tareas. Incluye pruebas unitarias."),
        QualificationCase(
            "text_statistics",
            "Crea una aplicación Python que calcule palabras, líneas y caracteres de un texto. "
            "Incluye una API de funciones y pruebas unitarias."),
    )

    def __init__(self, client, model: str,
                 developer_factory: Callable = PythonProjectDeveloper) -> None:
        self.client = client
        self.model = model
        self.developer_factory = developer_factory

    def run(self, *, attempts: int = 1) -> ModelQualification:
        results = tuple(self._run_case(case, attempts) for case in self.CASES)
        return ModelQualification(self.model, bool(results) and all(
            result.passed for result in results), results)

    def write_report(self, path: Path, *, attempts: int = 1) -> ModelQualification:
        qualification = self.run(attempts=attempts)
        target = path.resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({
            "model": qualification.model,
            "approved": qualification.approved,
            "results": [asdict(item) for item in qualification.results],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        return qualification

    def _run_case(self, case: QualificationCase,
                  attempts: int) -> QualificationResult:
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="igris-model-qualification-") as raw:
            developer = self.developer_factory(self.client, Path(raw), self.model)
            result = developer.develop(
                case.objective, confirmed=True, attempts=max(1, attempts))
            files: tuple[str, ...] = ()
            verified = False
            if result.project:
                project = Path(result.project)
                files = tuple(sorted(
                    path.relative_to(project).as_posix()
                    for path in project.rglob("*") if path.is_file()
                    and not any(part in {".pytest_cache", "__pycache__"}
                                for part in path.relative_to(project).parts)))
                verified = (project / "VERIFICATION.json").is_file()
            message = result.message
            if not result.ok and getattr(result, "diagnostics", ()):
                message += ": " + "; ".join(result.diagnostics)[:1000]
            return QualificationResult(
                case.name, bool(result.ok and verified), message, files,
                round(time.monotonic() - started, 3))


class MultiFileApplicationQualifier(ProgrammingModelQualifier):
    """Califica modelos exclusivamente para aplicaciones Python por componentes."""

    CASES = (
        QualificationCase(
            "inventory_components",
            "Crea una aplicación Python multiarchivo de inventario local. Separa servicio y entrada. "
            "Debe agregar artículos, listarlos y actualizar cantidades. Incluye pruebas pytest."),
        QualificationCase(
            "notes_components",
            "Crea una aplicación Python multiarchivo de notas en memoria. Separa modelo y servicio. "
            "Debe crear notas, buscarlas por texto y eliminarlas. Incluye pruebas pytest."),
        QualificationCase(
            "statistics_components",
            "Crea una aplicación Python multiarchivo de estadísticas de texto. Separa funciones y CLI. "
            "Debe contar líneas, palabras y caracteres. Incluye pruebas pytest."),
    )

    def __init__(self, client, model: str,
                 developer_factory: Callable = PythonMultiFileDeveloper) -> None:
        super().__init__(client, model, developer_factory)

    def _run_case(self, case: QualificationCase,
                  attempts: int) -> QualificationResult:
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="igris-multifile-qualification-") as raw:
            developer = self.developer_factory(self.client, Path(raw), self.model)
            result = developer.develop(
                case.objective, confirmed=True, attempts=max(1, attempts),
                componentized=True)
            files: tuple[str, ...] = ()
            verified = False
            if result.project:
                project = Path(result.project)
                files = tuple(sorted(
                    path.relative_to(project).as_posix()
                    for path in project.rglob("*") if path.is_file()
                    and not any(part in {".pytest_cache", "__pycache__"}
                                for part in path.relative_to(project).parts)))
                verified = (project / "VERIFICATION.json").is_file()
            message = result.message
            if not result.ok and getattr(result, "diagnostics", ()):
                message += ": " + "; ".join(result.diagnostics)[:1000]
            return QualificationResult(
                case.name, bool(result.ok and verified), message, files,
                round(time.monotonic() - started, 3))

    def write_report(self, path: Path, *, attempts: int = 1) -> ModelQualification:
        qualification = self.run(attempts=attempts)
        target = path.resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({
            "kind": "python_multifile_application",
            "model": qualification.model,
            "approved": qualification.approved,
            "results": [asdict(item) for item in qualification.results],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        return qualification


def is_model_approved(audit_root: Path, model: str) -> bool:
    """Lee evidencia persistente; un modelo sin informe aprobado queda bloqueado."""
    return model in approved_models(audit_root)


def approved_models(audit_root: Path) -> tuple[str, ...]:
    """Modelos que superaron todas las misiones de calificación persistidas."""
    root = audit_root.resolve()
    if not root.is_dir():
        return ()
    models = set()
    for path in root.glob("model_qualification_*.json"):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        model = report.get("model")
        if isinstance(model, str) and model and report.get("approved") is True:
            models.add(model)
    return tuple(sorted(models))


def approved_models_for(audit_root: Path, kind: str) -> tuple[str, ...]:
    """Devuelve modelos aprobados para una especialidad de ejecución concreta."""
    root = audit_root.resolve()
    if not root.is_dir():
        return ()
    models = set()
    for path in root.glob("model_qualification_*.json"):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        model = report.get("model")
        report_kind = str(report.get("kind", "python_single_file"))
        if report_kind == kind and isinstance(model, str) and report.get("approved") is True:
            models.add(model)
    return tuple(sorted(models))