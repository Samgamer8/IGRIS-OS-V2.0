"""Respuestas de producto vinculadas a una mision, antes de cualquier chat."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re

from .mission_router import _normalize_intent, _existing_directory_sources


def is_correction(text):
    text = _normalize_intent(text)
    return bool(re.search(r'\b(?:te (?:he|e) pedido|no (?:te )?(?:he|e) pedido|'
        r'eso no|no era eso|quien(?:te)? (?:te )?(?:ha|a) dicho)\b', text))


def is_standalone_local_path(text):
    """Detecta una ruta local aislada sin tocar el sistema de archivos.

    Se usa para distinguir una respuesta estructural (por ejemplo, la ruta que
    completa una aclaración pendiente) de una orden conversacional. Acepta
    rutas Windows absolutas, UNC y rutas POSIX absolutas.
    """
    raw = str(text or "").strip().strip('\"').strip("'")
    if not raw or "\n" in raw or "\r" in raw:
        return False
    if re.fullmatch(r"[A-Za-z]:[\\/].+", raw):
        return True
    if raw.startswith('\\\\') and len(raw) > 3:
        return True
    return raw.startswith('/') and len(raw) > 1


def refresh_continuation_approval(job, payload, issue_approval):
    """Renueva un token de un solo uso sin ampliar objetivo ni capacidad.

    Sólo se admite continuar la misma misión ``programming.mission``. El
    llamador inyecta ``IgrisKernel.issue_approval``; no se aceptan capacidades
    nuevas ni objetivos distintos.
    """
    if getattr(job, 'capability', '') != 'programming.mission':
        raise ValueError('La continuacion no corresponde a programming.mission')
    objective = str(getattr(job, 'objective', '') or '').strip()
    if not objective:
        raise ValueError('La mision original no tiene objetivo valido')
    result = dict(payload or {})
    payload_objective = str(result.get('objective', objective) or '').strip()
    if payload_objective != objective:
        raise ValueError('La continuacion intento cambiar el objetivo original')
    result['objective'] = objective
    result['__approval'] = issue_approval(objective, 'programming.mission')
    return result


def recovered_input(job, runtime):
    if job.result.get('work_status') == 'needs_input' and job.result.get('questions'):
        return dict(job.result)
    # A canonical path from the queue's mission id; never search another
    # project's history or accept an unrelated report path from the model.
    if not re.fullmatch(r'[0-9a-f]{32}', job.id):
        return None
    report = Path(runtime) / 'missions' / job.id / 'output/mission_progress.json'
    try:
        if report.is_symlink() or report.stat().st_size > 1024 * 1024:
            return None
        state = json.loads(report.read_text(encoding='utf-8'))
        questions = state.get('questions') or state.get('plan', {}).get('questions')
        if (state.get('state') == 'needs_input' and state.get('objective') == job.objective
                and isinstance(questions, list) and 1 <= len(questions) <= 2
                and all(isinstance(q, str) and q.strip() for q in questions)):
            return {'work_status': 'needs_input', 'questions': questions,
                    'report': str(report), 'project': str(report.parent.parent / 'working/repository'),
                    'understanding': state.get('plan', {}).get('understanding', '')}
    except (OSError, ValueError, TypeError):
        pass
    return None


@dataclass(frozen=True)
class ProgrammingFollowup:
    job: object
    payload: dict
    message: str
    ready: bool = True
    mode: str = 'answer'


_UNSET_FOCUS = object()


def programming_followup(text, mission_queue, runtime=None, *, active_job_id=_UNSET_FOCUS):
    if mission_queue is None or not text.strip():
        return None
    from .programming_intent import is_programming_request
    from .host_routing import host_action
    normalized = _normalize_intent(text)
    if re.fullmatch(r'(?:solo|solamente) (?:eso|esto)(?: (?:de|por) momento)?[.!]*', normalized):
        return None
    correction = is_correction(text)
    resume = bool(re.match(r'^(?:ok |vale )?(?:continua|continuar|sigue|reanuda|retoma|reintenta|reintentalo)\b', normalized))
    jobs = mission_queue.recent(1000)
    confirmation = bool(re.match(r'^(?:si|sí|ok|vale|confirmado|confirmar|acepto|acepte)\b', normalized))
    commitment_question = bool(re.match(
        r'^(?:(?:entonces|y|vale|ok)\s+)*(?:vas|puedes|piensas|quieres)\s+'
        r'(?:a\s+)?(?:hacerlo|realizarlo|continuarlo|seguir|continuar)\b', normalized))
    confirmation = confirmation or commitment_question
    candidates = [j for j in jobs if j.capability == 'programming.mission'
                  and (j.state in {'awaiting_input', 'awaiting_review', 'awaiting_downloads'}
                       or (resume and j.state in {'failed', 'deferred'})
                       or (j.state == 'failed' and (confirmation or correction)
                           and (not j.result or j.result.get('work_status') in {
                           'needs_input', 'blocked', 'ready_for_review'})))
                  and not j.result.get('continued_by') and not is_correction(j.objective)]
    if not resume and active_job_id is not _UNSET_FOCUS:
        if active_job_id is None and is_standalone_local_path(text):
            # After a restart the UI may have lost its in-memory programming
            # focus while the durable mission queue still has one unanswered
            # path question. Reattach only when exactly one mission is waiting
            # for a path; never guess between multiple pending projects.
            path_candidates = [job for job in candidates
                               if job.state == 'awaiting_input'
                               and job.result.get('input_kind') in {
                                   'destination', 'project_path', 'resource_path'}]
            if len(path_candidates) == 1:
                candidates = path_candidates
            elif len(path_candidates) > 1:
                ids = ', '.join(job.id[:8] for job in path_candidates[-5:])
                return ProgrammingFollowup(
                    path_candidates[-1], {},
                    'Hay varias misiones esperando una ruta (' + ids + '). '
                    'Indica cuál quieres reanudar antes de enviar la carpeta.',
                    False, mode='questions')
            else:
                candidates = []
        else:
            candidates = [job for job in candidates if job.id == active_job_id]

    # Las preguntas sobre pruebas/evidencia pertenecen a la misión reciente;
    # no deben convertirse en una nueva misión de programación.
    evidence_question = bool('?' in text and re.search(
        r'\b(?:has|lo has|esta|esta) (?:comprobado|verificado|probado)|'
        r'\b(?:pruebas|evidencia|evidencias|verificacion|verificado)\b', normalized))
    if evidence_question:
        recent = [j for j in jobs if j.capability in {'programming.mission', 'programming.deliver'}]
        if recent:
            job = recent[-1]
            data = dict(job.result or {})
            lines = [f'Misión {job.id[:8]} · estado: {job.state}.', job.message or 'Sin mensaje final.']
            report = ''
            work = data.get('work_delivery')
            if isinstance(work, dict):
                report = str(work.get('report', '') or '')
            report = report or str(data.get('report', '') or '')
            if report:
                path = Path(report)
                try:
                    if path.is_file() and not path.is_symlink() and path.stat().st_size <= 2 * 1024 * 1024:
                        evidence = json.loads(path.read_text(encoding='utf-8'))
                        verification = evidence.get('verification', {})
                        checks = verification.get('checks', []) if isinstance(verification, dict) else []
                        if checks:
                            passed = sum(1 for c in checks if isinstance(c, dict) and c.get('ok') is True)
                            lines.append(f'Pruebas registradas: {passed}/{len(checks)} correctas.')
                        changed = evidence.get('changed_files', [])
                        if isinstance(changed, list):
                            lines.append('Archivos cambiados: ' + (', '.join(map(str, changed[:12])) if changed else 'ninguno registrado.'))
                        lines.append('Informe: ' + str(path))
                except (OSError, ValueError, TypeError, json.JSONDecodeError):
                    lines.append('Informe registrado: ' + report)
            elif data.get('last_failure'):
                lines.append('Último fallo: ' + str(data['last_failure']))
            return ProgrammingFollowup(job, {}, '\n'.join(lines), False, mode='evidence')

    new_programming = is_programming_request(text)
    # New orders and explicit host operations do not answer an old form. While
    # waiting for a project path, a sentence that clearly continues the same
    # project remains attached to that mission instead of spawning a duplicate.
    if not correction and not resume and host_action(text):
        return None
    if not correction and not resume and new_programming:
        if not candidates:
            return None
        pending = candidates[-1]
        project_terms = {'ajedrez', 'ajedres', 'chess', 'chees', 'juego', 'videojuego',
                         'proyecto', 'prollecto', 'projecto'}
        old_terms = set(_normalize_intent(pending.objective).split())
        same_context = (bool(project_terms & old_terms & set(normalized.split()))
                        or any(phrase in normalized for phrase in (
                            'esta es la carpeta', 'carpeta del juego', 'juego creado',
                            'proyecto creado', 'prollecto creado')))
        if pending.result.get('input_kind') != 'project_path' or not same_context:
            return None
    if re.match(r'^(?:hola|buenos dias|buenas tardes|gracias|adios|cancelar|cancela|'
                r'para|detente|olvida|como vas|como va|estado|ya terminaste|ya lo tienes|has terminado|'
                r'cuando|avisame|notificame|me avisas|que hora|que tiempo|que puedes)\b', normalized):
        return None
    if '?' in text and not correction and not commitment_question:
        return None
    if not candidates and confirmation:
        candidates = [j for j in jobs if j.capability == 'programming.mission'
                      and j.state == 'failed' and not j.result.get('continued_by')
                      and not is_correction(j.objective)]
        if active_job_id is not _UNSET_FOCUS:
            candidates = [job for job in candidates if job.id == active_job_id]
    if not candidates:
        if resume:
            reference = re.sub(r'^(?:ok |vale )?(?:continua|continuar|sigue|reanuda|retoma|reintentalo|reintenta)\s*', '', normalized)
            known = [j for j in jobs if j.capability in {'programming.mission', 'programming.deliver'}
                     and reference and reference in _normalize_intent(j.objective)]
            if known:
                job = known[-1]
                return ProgrammingFollowup(job, {},
                    'El encargo ' + job.id[:8] + ' corresponde a ' + job.objective +
                    '\nEstado: ' + job.state + '. ' + job.message, False)
        return None
    job = candidates[-1]
    if resume:
        reference = re.sub(r'^(?:ok |vale )?(?:continua|continuar|sigue|reanuda|retoma|reintentalo|reintenta)\s*', '', normalized)
        if reference and reference not in {'el encargo', 'el proyecto', 'la mision', 'con el proyecto'}:
            matches = [j for j in candidates if reference in _normalize_intent(j.objective)
                       or re.fullmatch(r'[0-9a-f]{8,32}', reference) and j.id.startswith(reference)]
            if len(matches) != 1:
                return None
            job = matches[0]
    if job.state == 'deferred':
        job = mission_queue.restore_deferred(job.id)
    # A later genuine programming order owns the focus. Do not attach a bare
    # "yes" to an older project when its successor is already running.
    later = jobs[jobs.index(job)+1:]
    if not resume and any(j.capability == 'programming.mission' and not is_correction(j.objective)
           and j.state not in {'cancelled', 'continued'} for j in later):
        return None
    data = job.result
    if job.state in {'awaiting_review', 'awaiting_downloads'}:
        return ProgrammingFollowup(job, {},
            'Recupero la revision pendiente de la mision ' + job.id[:8] + ': ' + job.objective, mode='dialog')
    if resume and job.state == 'awaiting_input' and data.get('questions'):
        return ProgrammingFollowup(job, {},
            'Retomo el encargo ' + job.id[:8] + '. Sigue esperando su respuesta:\n'
            + '\n'.join(data['questions']), False, mode='questions')
    payload = {k: v for k, v in job.payload.items() if not k.startswith('__')}
    payload.update(objective=job.objective, continuation_of=job.id)
    payload.pop('active_project_job', None)
    questions = data.get('questions', [])[:2]
    if confirmation and job.state == 'failed':
        if data.get('report'):
            payload['resume_report'] = data['report']
        return ProgrammingFollowup(job, payload,
            'Continuo la mision ' + job.id[:8] + ': ' + job.objective)
    if job.state == 'failed':
        if not data.get('report') or data.get('work_status') != 'blocked':
            return ProgrammingFollowup(job, payload,
                'La mision de ' + job.objective + ' quedo interrumpida sin checkpoint verificable. '
                'Conservo los archivos; no voy a reanudar otro proyecto. ' + job.message, False)
        payload['resume_report'] = data['report']
        return ProgrammingFollowup(job, payload,
            'Reintento la mision ' + job.id[:8] + ' conservando sus archivos: ' + job.objective)
    if data.get('input_kind') == 'destination':
        raw_path = text.strip().strip('"').strip("'")
        folder = Path(raw_path).expanduser()
        question_text = '\n'.join(questions)
        reference_roots = _existing_directory_sources(job.objective)
        if folder.is_symlink():
            return ProgrammingFollowup(job, payload,
                'Esa ruta es un enlace. Indica una carpeta local normal.', False)
        if folder.is_dir():
            payload['root'] = str(folder.resolve())
            payload['requires_existing'] = True
            payload.pop('destination', None)
            # The original checkpoint was made without this project root.
            # Start a fresh staging copy so the existing files are inventoried first.
            payload.pop('resume_report', None)
        elif folder.exists() or not folder.parent.is_dir() or folder.parent.is_symlink():
            return ProgrammingFollowup(job, payload,
                'No puedo usar esa ruta. Indica una carpeta de proyecto existente o una carpeta nueva '
                'cuyo directorio padre ya exista.', False)
        else:
            payload['destination'] = str(folder.resolve())
            payload.pop('root', None)
        target_key = str(folder.resolve()).casefold()
        references = [path for path in reference_roots
                      if str(Path(path).resolve()).casefold() != target_key]
        if references:
            payload['resource_roots'] = references[:4]
        payload['clarifications'] = list(payload.get('clarifications', [])) + [{
            'question': question_text, 'answer': text.strip(), 'mission_id': job.id}]
        if data.get('report') and 'root' not in payload:
            payload['resume_report'] = data['report']
    elif data.get('input_kind') == 'project_path':
        folder = Path(text.strip().strip('"')).expanduser()
        if not folder.is_dir():
            return ProgrammingFollowup(job, payload,
                'Sigo con ' + job.objective + '\nIndica la ruta completa de una carpeta existente.', False)
        payload['root'] = str(folder.resolve())
        payload.pop('requested_root', None)
    elif data.get('input_kind') == 'resource_path':
        folder = Path(text.strip().strip('"')).expanduser()
        if (not folder.is_dir() or folder.is_symlink()) and re.search(r'(?:recursos?|assets?|modelos?|piezas?)\s*[:\n]', text, flags=re.I):
            candidate = text.strip().splitlines()[-1].strip()
            folder = Path(candidate.strip('"')).expanduser()
        if (folder.is_dir() and not folder.is_symlink() and (folder / 'project.godot').is_file()):
            payload['root'] = str(folder.resolve())
            payload.pop('resource_roots', None)
            if data.get('report'):
                payload['resume_report'] = data['report']
            return ProgrammingFollowup(job, payload,
                'Continuo la mision ' + job.id[:8] + ': ' + job.objective)
        if not folder.is_dir() or folder.is_symlink():
            return ProgrammingFollowup(job, payload,
                'Sigo con ' + job.objective + '\nIndica una carpeta de recursos existente y local.', False)
        roots = list(payload.get('resource_roots', []))
        resolved = str(folder.resolve())
        if resolved not in roots:
            roots.append(resolved)
        payload['resource_roots'] = roots[:4]
    elif job.state == 'failed' and data.get('work_status') == 'blocked' and bool(re.search(r'(?:recursos?|assets?|modelos?|piezas?)', _normalize_intent(text))):
        candidate = text.strip().splitlines()[-1].strip()
        if is_standalone_local_path(candidate):
            folder = Path(candidate.strip('"')).expanduser()
            if folder.is_dir() and not folder.is_symlink():
                roots = list(payload.get('resource_roots', []))
                resolved = str(folder.resolve())
                if resolved not in roots:
                    roots.append(resolved)
                payload['resource_roots'] = roots[:4]
                if data.get('report'):
                    payload['resume_report'] = data['report']
                return ProgrammingFollowup(job, payload,
                    'Continuo la mision ' + job.id[:8] + ': ' + job.objective)
    else:
        answer_text = text.strip()
        question_text = '\n'.join(questions)
        bare_path = answer_text.splitlines()[-1].strip() if answer_text else ''
        if is_standalone_local_path(bare_path):
            folder = Path(bare_path.strip('"')).expanduser()
            if folder.is_dir() and not folder.is_symlink():
                if (folder / 'project.godot').is_file():
                    payload['root'] = str(folder.resolve())
                    payload.pop('resource_roots', None)
                    if data.get('report'):
                        payload['resume_report'] = data['report']
                    return ProgrammingFollowup(job, payload,
                        'Continuo la mision ' + job.id[:8] + ': ' + job.objective)
                roots = list(payload.get('resource_roots', []))
                resolved = str(folder.resolve())
                if resolved not in roots:
                    roots.append(resolved)
                payload['resource_roots'] = roots[:4]
                if data.get('report'):
                    payload['resume_report'] = data['report']
                return ProgrammingFollowup(job, payload,
                    'Continuo la mision ' + job.id[:8] + ': ' + job.objective)
        payload['clarifications'] = list(payload.get('clarifications', [])) + [{
            'question': question_text, 'answer': answer_text,
            'mission_id': job.id}]
        folder = Path(answer_text.strip('"')).expanduser()
        resource_question = any(word in _normalize_intent(question_text) for word in (
            'recurso', 'recursos', 'asset', 'assets', 'pieza', 'piezas',
            'modelo', 'modelos', 'textura', 'texturas', 'grafico', 'graficos'))
        if resource_question and folder.is_dir() and not folder.is_symlink():
            roots = list(payload.get('resource_roots', []))
            resolved = str(folder.resolve())
            if resolved not in roots:
                roots.append(resolved)
            payload['resource_roots'] = roots[:4]
    if data.get('report') and not (
            data.get('input_kind') == 'destination' and payload.get('root')):
        payload['resume_report'] = data['report']
    # Product choices are not permission to download, publish or run an updater.
    return ProgrammingFollowup(job, payload,
        'Continuo la mision ' + job.id[:8] + ': ' + job.objective)
