"""Recover the coordinator cursor only from a verified workspace checkpoint."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from .mission_technology import verification_technology
from .mission_workspace import digest, safe_relative


DOWNLOAD_ACTIONS = {'install_python_packages', 'install_node_packages',
                    'ensure_godot', 'build_windows_executable'}


def new_cursor():
    return {'phase': 'planning', 'tests': [], 'history': [], 'review_attempts': 0,
            'seen': {}, 'pending_action': None, 'locked_tests': {}, 'read_hashes': {}}


def read_evidence(path: Path):
    if path.is_symlink() or path.stat().st_size > 16 * 1024**2:
        raise ValueError('Evidencia no valida o demasiado grande: ' + str(path))
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('La evidencia debe contener un objeto JSON: ' + str(path))
    return data


def _legacy_test_lock(files, path, content):
    """Match only bytes that the historical writer could actually produce.

    Do not normalize the file, trim whitespace, or trust a fresh hash merely
    because it is in the snapshot. The check is anchored to the tester reply.
    Modern checkpoints retain their original strict byte hashes unchanged.
    """
    if not isinstance(content, str):
        raise ValueError('El comprobador no conservo el contenido de la prueba: ' + path)
    actual = files.path(path).read_bytes()
    candidates = [('utf8_exact', content.encode('utf-8')),
                  ('windows_text_writer', content.replace('\n', '\r\n').encode('utf-8'))]
    for encoding, expected in candidates:
        if actual == expected:
            sha256 = digest(expected)
            return sha256, {'format': encoding, 'sha256': sha256,
                            'tester_content_sha256': digest(content.encode('utf-8'))}
    raise ValueError('Prueba inmutable alterada desde su creacion: ' + path)


def recover_resume_origin(report, state, verify):
    """Recover through rc8 copies that failed before any model/tool work.

    Every hop must still have the same original and exact working snapshot.
    Keep the latest mission as the continuation parent; only the cursor and
    environment come from the verified origin. No report or test is rewritten.
    """
    report = Path(report).resolve()
    missions = report.parent.parent.parent
    visited, skipped = set(), []
    while True:
        cursor = state.get('cursor')
        if not (state.get('schema') == 2 and state.get('state') == 'blocked'
                and state.get('calls') == [] and not state.get('plan')
                and isinstance(cursor, dict) and cursor.get('phase') == 'planning'
                and cursor.get('history') == [] and state.get('resumed_from')):
            break
        if report in visited or len(visited) >= 16:
            raise ValueError('Cadena de recuperacion ciclica o demasiado larga')
        visited.add(report)
        previous = Path(state['resumed_from'])
        if (previous.is_symlink() or previous.parent.is_symlink() or previous.parent.parent.is_symlink()
                or previous.resolve().parent.parent.parent != missions):
            raise ValueError('La recuperacion debe permanecer en las mismas misiones')
        previous = previous.resolve()
        if previous in visited:
            raise ValueError('Cadena de recuperacion ciclica')
        parent, _ = verify(previous)
        if (parent.get('answers', []) != state.get('answers', [])
                or parent.get('delivery_contract', {}) != state.get('delivery_contract', {})
                or parent.get('original_objective', '') != state.get('original_objective', '')):
            break  # New product answers belong to the current planning attempt.
        if parent.get('snapshot') != state.get('snapshot'):
            raise ValueError('La copia intermedia no coincide con el avance anterior; se conservan ambas')
        if (report.parent / 'tool_environment.json').exists() or (report.parent / 'tool_runs.json').exists():
            raise ValueError('La copia intermedia contiene actividad de herramientas; no se descartara')
        skipped.append(str(report))
        report, state = previous, parent
    return report, state, skipped


def recover_cursor(files, state, report, answers, contract, validate_plan, check_test):
    """Called AFTER the original and the previous working snapshot were checked.

    New product answers require planning again. A simple retry/approval reuses
    the existing contract. Old checkpoints need the tester's original response
    to recover immutable acceptance hashes, not just the current test contents.
    """
    if (state.get('state') not in {'blocked', 'needs_download_approval'}
            or state.get('answers', []) != answers
            or state.get('delivery_contract', {}) != contract):
        return None
    plan = copy.deepcopy(state.get('plan'))
    modern = state.get('schema') == 2
    cursor = copy.deepcopy(state.get('cursor')) if modern else new_cursor()
    if modern:
        if not isinstance(cursor, dict) or cursor.get('phase') not in {'planning', 'tests', 'programming'}:
            raise ValueError('El checkpoint no conserva una fase de trabajo valida')
        if cursor['phase'] == 'planning':
            return None
    if not isinstance(plan, dict) or plan.get('questions'):
        return None
    validate_plan(plan)
    technology = verification_technology(plan.get('technology'))
    plan.setdefault('technology_requested', plan['technology'])
    plan['technology'] = technology
    tests = list(dict.fromkeys(r['test_path'] for r in plan['requirements']
                              if r['validation'] == 'automated'))
    if not modern:
        previous = Path(report).parent
        if not all(files.path(p).is_file() for p in tests):
            return None
        locked = dict(files.locked)
        # rc7 saved tester responses even though it did not save its cursor.
        for call in reversed(state.get('calls', [])):
            if call.get('role') != 'comprobador' or call.get('ok') is not True:
                continue
            number = int(call['number'])
            from igris_os.utils.json_parser import StrictJSONParser
            package = StrictJSONParser.extract(read_evidence(
                previous / f'model_call_{number:03}.json')['response'])
            supplied = package.get('files', [])
            if {f.get('path') for f in supplied} == set(tests) and len(supplied) == len(tests):
                serialization = {}
                for item in supplied:
                    path = safe_relative(item['path'])
                    locked[path], serialization[path] = _legacy_test_lock(files, path, item['content'])
                cursor['legacy_test_serialization'] = serialization
                break
        if not all(p in locked for p in tests):
            return None  # No immutable tester evidence: do not invent it.
        cursor.update(phase='programming', tests=tests, locked_tests=locked)
        dialogue = previous / 'tool_dialogue.json'
        if dialogue.is_file():
            cursor['history'] = read_evidence(dialogue).get('steps', [])
        cursor['review_attempts'] = len(list(previous.glob('review_*.json')))
        if state.get('state') == 'needs_download_approval':
            for call in reversed(state.get('calls', [])):
                if call.get('role') == 'programador' and call.get('ok') is True:
                    action = StrictJSONParser.extract(read_evidence(
                        previous / f'model_call_{int(call["number"]):03}.json')['response'])
                    if action.get('tool') in DOWNLOAD_ACTIONS:
                        cursor['pending_action'] = action
                    break
        cursor['migrated_from'] = 'legacy_tester_evidence'
    if (not isinstance(cursor.get('history'), list) or not isinstance(cursor.get('seen'), dict)
            or type(cursor.get('review_attempts')) is not int or cursor['review_attempts'] < 0
            or not isinstance(cursor.get('locked_tests'), dict)
            or not isinstance(cursor.get('read_hashes'), dict)
            or (cursor.get('pending_action') is not None and not isinstance(cursor['pending_action'], dict))):
        raise ValueError('El checkpoint contiene un cursor incompleto')
    if cursor['phase'] == 'programming':
        if cursor.get('tests') != tests or any(p not in cursor['locked_tests'] for p in tests):
            raise ValueError('El checkpoint no protege todas las pruebas del contrato')
        if any(cursor['locked_tests'].get(p) != h for p, h in files.locked.items()):
            raise ValueError('El checkpoint no conserva las pruebas originales')
        for path, expected in cursor['locked_tests'].items():
            if digest(files.path(path).read_bytes()) != expected:
                raise ValueError('Prueba inmutable alterada desde su creacion: ' + path)
        for path in tests:
            check_test(technology, files.path(path).read_text(encoding='utf-8'))
    return plan, cursor
