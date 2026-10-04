"""Seguimiento vinculado a la cola, sin afirmaciones generadas por un LLM."""
from dataclasses import dataclass
import re
import unicodedata


@dataclass(frozen=True)
class MissionFollowup:
    intent: str
    job: object | None
    message: str


def task_switch_question(objective, mission_queue):
    from .intent_classifier import classify_intent, normalize_intent
    from .programming_followup import is_standalone_local_path
    if mission_queue is None or is_standalone_local_path(objective):
        return None
    decision = classify_intent(objective)
    if decision.kind not in {'task', 'programming'} or decision.subtype in {'resume', 'continue', 'followup'}:
        return None
    jobs = [job for job in mission_queue.recent(1000)
            if job.kind == 'capability' and not job.result.get('continued_by')
            and (job.state in {'pending', 'running', 'awaiting_input', 'awaiting_review',
                              'awaiting_downloads', 'awaiting_supervision'}
                 or job.state == 'failed' and job.result.get('work_status') == 'blocked')]
    if not jobs:
        return None
    job = next((item for item in jobs if item.state in {'running', 'pending'}), jobs[-1])
    old = normalize_intent(job.objective)
    new = decision.normalized
    subjects = {'ajedrez', 'chess', 'calculadora', 'inventario'}
    same_subject = bool(subjects & set(old.split()) & set(new.split()))
    if normalize_intent(objective) == old or (same_subject and not re.search(r'\b(?:nuevo|nueva|otro|otra)\b', new)):
        return None
    title = ' '.join(job.objective.split())[:240]
    return MissionFollowup('switch', job,
        f'Hay un encargo pendiente ({job.id[:8]}): {title}\n'
        '¿Quiere dejarlo pendiente y empezar la nueva tarea, señor?')


def mission_followup(objective, mission_queue):
    from igris_os.application.mission_router import is_creation_request
    from igris_os.application.game_resume import is_resume_request, matching_game_jobs, GAME_CAPABILITIES
    resume = is_resume_request(objective)
    if is_creation_request(objective) and not resume:
        return None
    text = "".join(c for c in unicodedata.normalize("NFD", objective.casefold())
                   if unicodedata.category(c) != "Mn")
    text = " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())
    notify = any(p in text for p in ("me avisas", "avisame", "notificame", "cuando termines", "cuando lo tengas"))
    retry = any(p in text for p in ("reintenta", "reintentalo", "vuelve a intentarlo", "quiero que lo crees tu", "hazlo tu"))
    status = any(p in text for p in ("como vas", "ya terminaste", "has terminado", "estado de la mision", "estado del proyecto", "como va el juego", "ya lo tienes"))
    if not (notify or retry or status or resume):
        return None
    jobs = mission_queue.recent(1000) if mission_queue is not None else []
    # Retries refer to the actual creation order, never the short follow-up sentence.
    if resume:
        jobs = matching_game_jobs(objective, jobs)
    elif retry:
        jobs = [j for j in jobs if j.capability in GAME_CAPABILITIES | {"project.stage", "repository.develop"}]
    elif status and any(word in text for word in ("juego", "ajedrez")):
        jobs = matching_game_jobs(objective, jobs)
    job = next((j for j in reversed(jobs) if j.state in {"running", "pending", "awaiting_supervision"}),
               jobs[-1] if jobs else None)
    if job is None:
        if resume:
            return MissionFollowup("resume", None, "Buscando los archivos del proyecto solicitado.")
        return MissionFollowup("status", None, "No hay una mision registrada a la que asociar ese mensaje. Indica el encargo completo.")
    states = {"pending": "en cola", "running": "en ejecucion", "completed": "finalizada",
              "failed": "fallida", "cancelled": "cancelada", "awaiting_supervision": "esperando autorizacion",
              'awaiting_input': 'esperando tu respuesta', 'awaiting_review': 'esperando tu revision',
              'awaiting_downloads': 'esperando autorizacion de descarga', 'continued': 'continuada en otra mision'}
    message = "Mision " + job.id[:8] + ": " + states.get(job.state, job.state) + ".\n" + job.objective
    if job.message:
        message += "\nUltimo resultado: " + job.message[:1000]
    for key, value in job.result.items():
        message += "\n" + key + ": " + str(value)
    if resume and job.state not in {"running", "pending", "awaiting_supervision"}:
        return MissionFollowup("resume", job,
            "Recuperando el avance de la mision anterior " + job.id[:8] + ".\n" + job.objective)
    if retry and job.state in {"failed", "cancelled"}:
        if job.capability in GAME_CAPABILITIES:
            return MissionFollowup("resume", job,
                "Recuperando el avance de la mision anterior " + job.id[:8] + ".\n" + job.objective)
        return MissionFollowup("retry", job, message)
    if notify and job.state in {"pending", "running", "awaiting_supervision"}:
        return MissionFollowup("notify", job, message + "\nTe avisare aqui al finalizar, tambien si falla. Mantén IGRIS abierto.")
    return MissionFollowup("status", job, message)
