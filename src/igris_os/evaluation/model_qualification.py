"""Calificacion acotada con pruebas externas y evidencia conservada."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import json
import tempfile
import time
from typing import Callable
from uuid import uuid4

from igris_os.ai import OllamaClient
from igris_os.programming import PythonMultiFileDeveloper, PythonProjectDeveloper
from igris_os.programming.mission_workspace import project_files, save_json
from .acceptance_cases import CONTRACTS
from .external_acceptance import verify_candidate, retained_verification_is_valid


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
    verification: dict = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ModelQualification:
    model: str
    approved: bool
    results: tuple[QualificationResult, ...]


class ProgrammingModelQualifier:
    """Aprueba exclusivamente los casos ejecutados; no certifica nivel senior."""
    KIND = 'python_single_file'
    CASE_NAMES = ('todo_memory', 'text_statistics')
    CASES = tuple(QualificationCase(n, CONTRACTS[n]) for n in CASE_NAMES)
    DEVELOPER = PythonProjectDeveloper

    def __init__(self, client, model: str,
                 developer_factory: Callable = PythonProjectDeveloper) -> None:
        self.client, self.model = client, model
        self.developer_factory = developer_factory
        self.evidence_root = None
        self.live = type(client) is OllamaClient and developer_factory is self.DEVELOPER

    def run(self, *, attempts: int = 1) -> ModelQualification:
        if self.evidence_root is None:
            self.evidence_root = Path(tempfile.mkdtemp(prefix='igris-qualification-'))
        run_root = self.evidence_root / uuid4().hex
        results = tuple(self._run_case(case, attempts, run_root / case.name) for case in self.CASES)
        return ModelQualification(self.model, self.live and bool(results) and all(r.passed for r in results), results)

    def write_report(self, path: Path, *, attempts: int = 1) -> ModelQualification:
        target = Path(path).resolve()
        self.evidence_root = target.parent / (target.stem + '_evidence')
        result = self.run(attempts=attempts)
        save_json(target, {
            'schema': 2, 'kind': self.KIND, 'scope': 'Solo los casos funcionales enumerados',
            'execution_mode': 'live_local_backend' if self.live else 'test_fixture',
            'model': result.model, 'approved': result.approved,
            'functional_cases_passed': bool(result.results) and all(r.passed for r in result.results),
            'results': [asdict(r) for r in result.results],
        })
        return result

    def _run_case(self, case, attempts, workspace):
        started, names, evidence = time.monotonic(), (), {}
        try:
            developer = self.developer_factory(self.client, workspace / 'generation', self.model)
            kwargs = {'confirmed': True, 'attempts': min(5, max(1, attempts))}
            if self.KIND == 'python_multifile_application':
                kwargs['componentized'] = True
            result = developer.develop(case.objective, **kwargs)
            message = result.message
            if result.project:
                project = Path(result.project).resolve()
                if not project.is_relative_to(workspace.resolve()):
                    raise ValueError('El generador devolvio una carpeta fuera del examen')
                names = tuple(sorted(project_files(project)))
                evidence = verify_candidate(project, case.name, workspace / 'assessment')
            passed = result.ok and evidence.get('ok') is True
            if not passed:
                message += '; no supera la comprobacion funcional externa'
                if evidence.get('error'):
                    message += ': ' + evidence['error']
            return QualificationResult(case.name, bool(passed), message, names,
                                       round(time.monotonic() - started, 3), evidence)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            return QualificationResult(case.name, False, str(exc), names,
                                       round(time.monotonic() - started, 3), evidence)


class MultiFileApplicationQualifier(ProgrammingModelQualifier):
    KIND = 'python_multifile_application'
    CASE_NAMES = ('inventory_components', 'notes_components', 'statistics_components')
    CASES = tuple(QualificationCase(n, CONTRACTS[n]) for n in CASE_NAMES)
    DEVELOPER = PythonMultiFileDeveloper

    def __init__(self, client, model: str, developer_factory: Callable = PythonMultiFileDeveloper) -> None:
        super().__init__(client, model, developer_factory)


def _valid_report(report):
    if (not isinstance(report, dict) or report.get('schema') != 2
            or report.get('approved') is not True or report.get('execution_mode') != 'live_local_backend'
            or not isinstance(report.get('model'), str) or not report['model']):
        return False
    names = {ProgrammingModelQualifier.KIND: ProgrammingModelQualifier.CASE_NAMES,
             MultiFileApplicationQualifier.KIND: MultiFileApplicationQualifier.CASE_NAMES}.get(report.get('kind'))
    rows = report.get('results')
    if not names or not isinstance(rows, list) or len(rows) != len(names):
        return False
    if {r.get('name') for r in rows if isinstance(r, dict)} != set(names):
        return False
    for row in rows:
        if not isinstance(row, dict) or row.get('passed') is not True:
            return False
        evidence = row.get('verification')
        if (not isinstance(evidence, dict) or evidence.get('case') != row.get('name')
                or not retained_verification_is_valid(evidence)):
            return False
    return True


def _approved_reports(audit_root):
    root = Path(audit_root).resolve()
    if root.is_dir():
        for path in root.glob('model_qualification_*.json'):
            try:
                report = json.loads(path.read_text(encoding='utf-8'))
                if _valid_report(report):
                    yield report
            except (OSError, ValueError, TypeError):
                continue


def is_model_approved(audit_root: Path, model: str) -> bool:
    return model in approved_models(audit_root)


def approved_models(audit_root: Path) -> tuple[str, ...]:
    return tuple(sorted({r['model'] for r in _approved_reports(audit_root)}))


def approved_models_for(audit_root: Path, kind: str) -> tuple[str, ...]:
    return tuple(sorted({r['model'] for r in _approved_reports(audit_root) if r['kind'] == kind}))
