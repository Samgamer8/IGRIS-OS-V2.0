"""Reconoce encargos operativos y recupera su proyecto sin perder la correccion actual."""
from pathlib import Path
import re

from .mission_router import (RoutedAction, _normalize_intent,
                             _existing_directory_sources)
from .intent_classifier import classify_intent

WORK_CAPABILITY = 'programming.mission'
PROJECT_CAPABILITIES = {'games.godot.scaffold', 'games.godot.resume', 'repository.develop',
    'repository.apply_verified', 'project.stage', 'project.deliver', 'project.lead',
    'programming.autonomous.develop', 'programming.python.multifile.develop',
    'programming.node.develop', WORK_CAPABILITY, 'programming.deliver'}
CHANGE = r'(?:mejora(?:r|lo|rlo)?|mejores|arregla(?:r|lo)?|repara(?:r|lo)?|corrige|corregir|modifica(?:r|lo)?|implementa(?:r)?|anade|agrega|refactoriza|actualiza(?:r|lo)?|optimiza(?:r|lo)?|remasteriza(?:r|lo)?|integra(?:r|lo)?|renueva(?:r|lo)?)'
CREATE = r'(?:crea(?:r|me|s)?|cree(?:s)?|construye|construir|construyas|contrullas|contruye|genera(?:r|me|s)?|desarrolla(?:r|s)?|programa(?:r|ndo|s)?|hazme|haz)'
CONTINUE = r'(?:continua(?:r)?|sigue|seguir|reanuda|reanudar|retoma|retomar)'
PROJECT_WORDS = ('proyecto', 'prollecto', 'projecto', 'juego', 'videojuego', 'ajedrez', 'ajedres', 'chess', 'chees',
    'codigo', 'programa', 'aplicacion', 'app', 'repositorio', 'script', 'python', 'godot',
    'web', 'pagina', 'servidor', 'fivem', 'lua', 'bot', 'calculadora', 'inventario',
    'javascript', 'typescript', 'html', 'api')


def is_improvement_request(text):
    normalized = _normalize_intent(text)
    explicit_new_project = bool(re.search(
        r'\b' + CREATE + r'\b.{0,240}\b(?:programa|aplicacion|software|proyecto|'
        r'juego|videojuego|web|pagina|app|bot|servidor)\b', normalized))
    decision = classify_intent(text)
    return (decision.kind == "programming" and
            decision.subtype in {"continue", "modify", "repair", "followup"} and
            not explicit_new_project)


def is_programming_request(objective):
    decision = classify_intent(objective)
    return (decision.kind == "programming" and
            decision.subtype in {"create", "continue", "modify", "repair", "followup"})


def programming_action(objective, attachments=(), jobs=(), runtime=None):
    sources = _existing_directory_sources(objective, attachments)
    source = sources[0] if sources else ''
    decision = classify_intent(objective)
    improvement = is_improvement_request(objective)

    # Auditorias con una carpeta concreta usan repository.analyze, que se
    # resuelve despues en MissionRouter. Sin carpeta, programming.mission debe
    # hacer intake y pedir el proyecto en vez de degradar la orden a chat.
    if decision.kind == "programming" and decision.subtype == "audit":
        if source:
            return None
        return RoutedAction(
            'capability', WORK_CAPABILITY,
            {'objective': objective, 'requires_existing': True}, True)

    # Las pruebas de juegos tienen un playtest especializado. Para software y
    # proyectos generales, la prueba pertenece al flujo de programacion.
    if decision.kind == "programming" and decision.subtype == "test":
        words = set(_normalize_intent(objective).split())
        if words.intersection({'juego', 'videojuego', 'ajedrez', 'chess', 'chees', 'godot'}):
            return None
        return RoutedAction(
            'capability', WORK_CAPABILITY,
            {'objective': objective, 'requires_existing': True,
             **({'root': source} if source else {})}, True)

    if not is_programming_request(objective) and not (source and improvement):
        return None
    payload = {'objective': objective, 'requires_existing': improvement}
    from .delivery_request import requested_delivery
    contract = requested_delivery(objective)
    if contract:
        payload['delivery_contract'] = contract
        if contract.get('destination'):
            payload['destination'] = contract['destination']
    # An explicit invalid path must not silently select a different project.
    explicit = re.findall(r'["“]([^"”]+)["”]', objective)
    explicit_paths = [p for p in explicit if Path(p).is_absolute() or re.match(r'^[A-Za-z]:[\\/]', p)]
    if not source and explicit_paths:
        payload['requested_root'] = explicit_paths[-1]
        return RoutedAction('capability', WORK_CAPABILITY, payload, True)
    if source:
        payload.update(root=source, requires_existing=True)
        if len(sources) > 1:
            payload['resource_roots'] = sources[1:5]
    elif improvement:
        # Los remasters que citan una biblioteca grafica externa son ambiguos
        # por naturaleza: puede haber varias copias del mismo juego. No
        # reutilices silenciosamente un proyecto historico porque eso puede
        # convertir la primera ruta que responde el usuario en una carpeta de
        # assets y trabajar sobre una copia equivocada. Exigimos primero la
        # ruta del proyecto; despues la capacidad pedira la biblioteca grafica.
        if requires_external_graphic_resources(objective):
            return RoutedAction('capability', WORK_CAPABILITY, payload, True)
        relevant = [j for j in jobs if j.capability in PROJECT_CAPABILITIES]
        chess = any(w in _normalize_intent(objective).split() for w in ('ajedrez', 'chess', 'chees'))
        if chess:
            relevant = [j for j in relevant if any(w in _normalize_intent(j.objective)
                                                 for w in ('ajedrez', 'chess', 'chees'))]
        candidates = {}
        for job in reversed(relevant):
            for raw in (job.payload.get('root'), job.payload.get('source_root'),
                        job.result.get('project'), job.result.get('delivered_project'),
                        job.result.get('partial_project'), job.payload.get('resume_destination'),
                        job.payload.get('resume_project')):
                if not raw:
                    continue
                path = Path(str(raw)).expanduser()
                if path.is_dir():
                    resolved = str(path.resolve())
                    candidates.setdefault(resolved, job)
                    break
        # Prefer delivered originals to retained temporary copies of the same project.
        external = {p: j for p, j in candidates.items()
                    if runtime is None or not Path(p).is_relative_to(Path(runtime).resolve())}
        if external:
            candidates = external
        if len(candidates) == 1:
            path, job = next(iter(candidates.items()))
            if job.state in {'pending', 'running', 'awaiting_supervision'}:
                payload['active_project_job'] = job.id
            payload.update(root=path, original_objective=job.payload.get('original_objective') or job.objective)
        elif len(candidates) > 1:
            payload['project_candidates'] = list(candidates)[:5]
        elif chess and runtime:
            from .game_resume import resolve_game_resume
            try:
                original, recovered = resolve_game_resume(objective, relevant[0] if relevant else None, runtime)
                payload.update(root=recovered.get('resume_destination') or recovered['resume_project'],
                               original_objective=original)
            except (OSError, ValueError):
                pass
    return RoutedAction('capability', WORK_CAPABILITY, payload, True)


def requires_external_graphic_resources(objective: str) -> bool:
    """Detecta encargos que no pueden arrancar sin la biblioteca grafica citada."""
    text = _normalize_intent(objective)
    phrases = (
        'recursos graficos', 'recurso grafico', 'piezas de esta carpeta',
        'contenido de las piezas', 'modelos 3d', 'modelos de esta carpeta',
        'biblioteca de recursos', 'assets de esta carpeta', 'usar las piezas',
        'utilizando los recursos', 'usar los recursos', 'integrar las piezas',
    )
    return any(phrase in text for phrase in phrases)
