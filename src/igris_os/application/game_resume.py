"""Recupera el encargo y sus archivos; nunca convierte reanudar en charla."""
from pathlib import Path
import json
import re
import time

from igris_os.application.mission_router import _normalize_intent

GAME_CAPABILITIES = {"games.godot.scaffold", "games.godot.resume"}


def is_resume_request(objective):
    text = _normalize_intent(objective)
    command = re.match(
        r"^(?:(?:ok|vale|bien|si|por favor|igris)\s+)*"
        r"(?:(?:puedes|podrias|quiero que|necesito que)\s+)?"
        r"(retoma(?:rlo|r|lo)?|reanuda(?:rlo|r|lo)?|continua(?:rlo|r|lo)?|"
        r"sigue|termina(?:rlo|r|lo)?|retomes|reanudes|"
        r"continues|sigas|termines)\b", text)
    if not command or any(word in text.split() for word in ("explicacion", "explicando", "historia", "frase", "charla", "conversacion")):
        return False
    return command.group(1).startswith(("retom", "reanud")) or any(
        word in text.split() for word in (
            "proyecto", "projecto", "prollecto", "juego", "ajedrez",
            "codigo", "programa", "aplicacion", "carpeta"))


def requested_project(objective):
    path = re.search(r'([A-Za-z]:[\\/][^\r\n"<>|]+)', objective)
    if path:
        return path.group(1).strip().rstrip('. ')
    quoted = re.findall(r'"([^"\r\n]+)"', objective)
    if quoted:
        return quoted[-1]
    folder = re.search(r'\bcarpeta\s+(?:llamada\s+|con (?:el )?nombre\s+)?(.+)', objective, re.I)
    return folder.group(1).strip().rstrip('. ') if folder else ""


def _key(value):
    return _normalize_intent(str(value)).replace("_", " ").replace(" ", "")


def matching_game_jobs(objective, jobs):
    games = [j for j in jobs if j.capability in GAME_CAPABILITIES]
    if any(word in _normalize_intent(objective).split() for word in ("python", "calculadora", "web", "fivem")):
        return []
    reference = requested_project(objective)
    if reference:
        key = _key(Path(reference).name)
        return [j for j in games if key == _key(j.payload.get("name", ""))
                or any(key == _key(Path(str(j.result.get(k, ""))).name)
                       for k in ("partial_project", "project", "staged_project"))]
    if any(word in _normalize_intent(objective) for word in ("ajedrez", "chess", "chees")):
        return [j for j in games if any(word in _normalize_intent(j.objective) for word in ("ajedrez", "chess", "chees"))]
    return games


def _json(path):
    try:
        if path.stat().st_size > 512000:
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def resolve_game_resume(objective, job, runtime):
    """Devuelve un contrato concreto o un error, sin consumir una llamada LLM."""
    runtime = Path(runtime).resolve()
    reference = requested_project(objective)
    candidates = []
    payload = dict(job.payload) if job else {}
    original = job.objective if job else ""
    if reference and Path(reference).is_absolute():
        if not (Path(reference) / "project.godot").is_file():
            raise ValueError("La carpeta indicada no contiene project.godot: " + reference)
        candidates.append((Path(reference), {}))
    if job:
        # New executions use the queue id as workspace id, including interrupted jobs.
        for project_file in (runtime / "missions" / job.id).glob("*/project.godot"):
            candidates.append((project_file.parent, {}))
        for key in ("partial_project", "staged_project", "project"):
            if job.result.get(key):
                candidates.append((Path(job.result[key]), {}))
        if job.result.get("diagnostic_report"):
            report = _json(Path(job.result["diagnostic_report"]))
            if report.get("partial_project"):
                candidates.append((Path(report["partial_project"]), report))
        if payload.get("resume_project"):
            candidates.append((Path(payload["resume_project"]), {}))
        if payload.get("delivery_root") and payload.get("name"):
            for name in (payload["name"], payload["name"].replace(" ", "_")):
                candidates.append((Path(payload["delivery_root"]) / name, {}))
    # Revision 4 queues did not retain the partial path; recover it from their reports.
    reports = []
    deadline = time.monotonic() + 3
    for index, report_path in enumerate((runtime / "missions").glob("*/ERROR_JUEGO_*.json")):
        if index >= 500 or time.monotonic() > deadline:
            break
        report = _json(report_path)
        partial = report.get("partial_project")
        if not partial:
            continue
        same_order = bool(original and str(report.get("objective", "")).startswith(original))
        expected_name = reference or payload.get("name", "")
        same_name = bool(expected_name and _key(Path(partial).name) == _key(Path(expected_name).name))
        if same_order or same_name or (not job and not reference and
                any(word in _normalize_intent(objective) for word in ("ajedrez", "chess")) and
                any(word in _normalize_intent(report.get("objective", "")) for word in ("ajedrez", "chess"))):
            reports.append((report_path.stat().st_mtime_ns, Path(partial), report))
    for index, contract_file in enumerate((runtime / "missions").glob("*/*/IGRIS_TASK.json")):
        if index >= 500 or time.monotonic() > deadline:
            break
        contract = _json(contract_file)
        expected_name = reference or payload.get("name", "")
        if ((original and contract.get("objective") == original) or
                (expected_name and _key(contract_file.parent.name) == _key(Path(expected_name).name))):
            reports.append((contract_file.stat().st_mtime_ns, contract_file.parent, contract))
    candidates.extend((p, report) for _, p, report in sorted(reports, key=lambda row: row[0], reverse=True))
    seen = set()
    for candidate, report in candidates:
        candidate = candidate.expanduser().resolve()
        if candidate in seen or not (candidate / "project.godot").is_file():
            continue
        seen.add(candidate)
        contract = _json(candidate / "IGRIS_TASK.json")
        saved_payload = contract.get("payload", {})
        if isinstance(saved_payload, dict):
            payload = {**saved_payload, **payload}
        original = original or contract.get("objective") or report.get("objective")
        if not original:
            original = objective
        if not (payload.get("genre") == "chess_3d" or (candidate / "chess_state.gd").is_file() or
                any(word in _normalize_intent(original) for word in ("ajedrez", "chess", "chees"))):
            raise ValueError("El proyecto encontrado no es el ajedrez del encargo. No se ha iniciado ninguna generacion.")
        payload = {k: v for k, v in payload.items() if not k.startswith("__")
                   and k not in {"workspace", "on_progress", "mission_id"}}
        payload.update(resume_project=str(candidate), resume=True, generate_full_code=True,
                       objective=original, genre="chess_3d")
        payload.setdefault("name", candidate.name)
        if reference and not Path(reference).is_absolute() and _key(reference) == _key(candidate.name):
            payload["name"] = reference
        payload.setdefault("delivery_type", "source")
        if not candidate.is_relative_to(runtime):
            payload["resume_destination"] = str(candidate)
        return original, payload
    raise ValueError("No se encontro project.godot para este encargo. No se ha llamado al modelo ni creado otro proyecto. "
                     "Indica la ruta completa de la carpeta existente: reanuda en \"C:\\ruta\\igris chees\".")
