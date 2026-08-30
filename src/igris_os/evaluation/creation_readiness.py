from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import tempfile
import time
from typing import Callable

from igris_os.programming import PythonMultiFileDeveloper


@dataclass(frozen=True, slots=True)
class CreationReadinessResult:
    name: str
    passed: bool
    score: int
    duration_seconds: float
    evidence: tuple[str, ...]


class FullApplicationCreationBenchmark:
    """Mide si IGRIS crea y ejecuta una aplicacion Python completa minima."""

    OBJECTIVE = (
        "Crea una aplicacion Python de consola para gestionar tareas. "
        "Separa el modelo de tarea, el servicio de tareas y una CLI ejecutable. "
        "Debe agregar tareas, listarlas y completarlas. Incluye README y pruebas pytest."
    )

    def __init__(self, client, developer_factory: Callable = PythonMultiFileDeveloper,
                 model: str = "benchmark") -> None:
        self.client = client
        self.developer_factory = developer_factory
        self.model = model

    def run(self) -> CreationReadinessResult:
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="igris-creation-readiness-") as raw:
            root = Path(raw)
            developer = self.developer_factory(self.client, root, self.model)
            result = developer.develop(
                self.OBJECTIVE, confirmed=True, attempts=2, componentized=True)
            checks = {
                "development_ok": result.ok,
                "project_created": bool(result.project),
                "readme_present": False,
                "multiple_python_modules": False,
                "tests_present": False,
                "verification_present": False,
                "pytest_passed": False,
            }
            evidence: list[str] = [f"developer_message={result.message}"]
            if result.project:
                project = Path(result.project)
                python_files = tuple(project.rglob("*.py"))
                checks["readme_present"] = (project / "README.md").is_file()
                checks["multiple_python_modules"] = len(
                    tuple(path for path in python_files
                          if not path.name.startswith("test_"))) >= 3
                checks["tests_present"] = any(
                    path.name.startswith("test_") for path in python_files)
                checks["verification_present"] = (project / "VERIFICATION.json").is_file()
                checks["pytest_passed"] = checks["verification_present"] and result.ok
                evidence.extend((
                    f"project_files={','.join(sorted(path.name for path in project.rglob('*') if path.is_file()))}",
                    f"python_file_count={len(python_files)}",
                ))
            score = int(sum(checks.values()) * 100 / len(checks))
            passed = all(checks.values())
            evidence.extend(f"{name}={value}" for name, value in checks.items())
            return CreationReadinessResult(
                "create_python_cli_application", passed, score,
                round(time.monotonic() - started, 3), tuple(evidence))

    def report(self) -> dict[str, object]:
        result = self.run()
        return {
            "kind": "full_application_creation_readiness",
            "passed": result.passed,
            "score": result.score,
            "results": [asdict(result)],
            "limitations": [
                "benchmark uses a controlled objective",
                "does not prove external-project performance or expert-level design",
                "model quality requires a run with a real configured model",
            ],
        }

    def write_report(self, path: Path) -> dict[str, object]:
        report = self.report()
        target = path.resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report