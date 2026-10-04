"""Ejecuta pruebas de dominio propias y conserva el codigo y la evidencia."""
from __future__ import annotations

import ast
import json
from pathlib import Path
import re

from igris_os.programming.mission_workspace import MissionFiles, digest, is_test, project_files, save_json
from igris_os.programming.mission_tools import MissionTools
from .acceptance_cases import CONTRACTS, oracle_source


def source_hashes(root):
    return {p: digest(b) for p, b in project_files(Path(root)).items()}


def verify_candidate(project, case, workspace):
    project, workspace = Path(project).resolve(), Path(workspace).resolve()
    evidence = {'schema': 2, 'case': case, 'ok': False, 'project': str(project)}
    try:
        if case not in CONTRACTS:
            raise ValueError('No existe un criterio independiente para este caso')
        before = source_hashes(project)
        if not before:
            raise ValueError('Proyecto vacio')
        if case.endswith('_components'):
            for name in ('service.py', 'app.py'):
                if name not in before or not (project / name).read_text(encoding='utf-8-sig').strip():
                    raise ValueError('Falta el componente requerido: ' + name)
            tree = ast.parse((project / 'app.py').read_text(encoding='utf-8-sig'))
            if not any((isinstance(n, ast.ImportFrom) and n.module == 'service') or
                (isinstance(n, ast.Import) and any(a.name == 'service' for a in n.names)) for n in ast.walk(tree)):
                raise ValueError('La entrada no usa el componente service')
        files = MissionFiles(workspace)
        files.prepare(project)
        tools = MissionTools(files)
        paths = [p for p in before if is_test(p) and p.endswith('.py')]
        regression = tools.verify('python', paths)
        # Written after the project's tests, outside the editable repository.
        script = files.output / 'external_acceptance.py'
        script.write_text(oracle_source(case), encoding='utf-8')
        check = tools._run([tools.python_executable(), '-I', '-B', str(script), str(files.root)],
                           'external_acceptance', timeout=45, cwd=files.output)
        lines = re.findall(r'^IGRIS_EXTERNAL_RESULT=(.+)$', check['output'], re.M)
        verdict = json.loads(lines[0]) if len(lines) == 1 else {}
        accepted = (check['ok'] and verdict.get('ok') is True
                    and type(verdict.get('tests')) is int and verdict['tests'] >= 3
                    and all(verdict.get(k) == 0 for k in ('failures', 'errors', 'skipped')))
        unchanged = before == source_hashes(project) == source_hashes(files.root)
        evidence.update(ok=bool(regression['ok'] and accepted and unchanged),
            source_hashes=before, source_unchanged=unchanged, regression=regression,
            external={'process': check, 'result': verdict, 'oracle_sha256': digest(script.read_bytes())})
    except (OSError, ValueError, SyntaxError, TypeError, KeyError) as exc:
        evidence.update(ok=False, error=str(exc))
    target = workspace / 'output/external_verification.json'
    evidence['report'] = str(target)
    save_json(target, evidence)
    return evidence


def retained_verification_is_valid(value):
    try:
        if (not isinstance(value, dict) or value.get('schema') != 2 or value.get('ok') is not True
                or value.get('case') not in CONTRACTS or not value.get('source_unchanged')
                or not isinstance(value.get('regression'), dict)
                or not value['regression'].get('ok') or not value.get('source_hashes')):
            return False
        if json.loads(Path(value['report']).read_text(encoding='utf-8')) != value:
            return False
        result = value['external']['result']
        return (value['external']['process']['ok'] is True and result.get('ok') is True
                and type(result.get('tests')) is int and result['tests'] >= 3
                and all(result.get(k) == 0 for k in ('failures', 'errors', 'skipped'))
                and source_hashes(value['project']) == value['source_hashes'])
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return False
