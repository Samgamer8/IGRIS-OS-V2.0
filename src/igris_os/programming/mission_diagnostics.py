"""Export saved evidence locally; never execute generated code or contact a model."""
from __future__ import annotations

import json
from pathlib import Path
import re
from uuid import uuid4
import zipfile

from .mission_checkpoint import read_evidence


def export_mission_diagnostics(runtime: Path, *, mission='', objective='') -> Path:
    runtime = Path(runtime).resolve()
    missions = runtime / 'missions'
    if missions.is_symlink() or not missions.is_dir():
        raise ValueError('No hay misiones guardadas en ' + str(missions))
    if mission and not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', mission):
        raise ValueError('Identificador de mision no valido')
    candidates = []
    for folder in missions.iterdir():
        report = folder / 'output/mission_progress.json'
        if (folder.is_symlink() or (folder / 'output').is_symlink() or report.is_symlink()
                or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', folder.name) or not report.is_file()):
            continue
        if mission and not folder.name.startswith(mission):
            continue
        candidates.append(report)
    if mission and len(candidates) > 1:
        raise ValueError('El identificador coincide con varias misiones; utiliza el identificador completo')
    selected = None
    for report in sorted(candidates, key=lambda p: p.stat().st_mtime_ns, reverse=True):
        state = read_evidence(report)
        if not objective or objective.casefold() in state.get('objective', '').casefold():
            selected = report
            selected_objective = state.get('objective')
            break
    if selected is None:
        raise ValueError('No hay evidencia guardada de ese encargo')
    output = runtime / 'audit/diagnostics'
    output.mkdir(parents=True, exist_ok=True)
    target = output / f'IGRIS_ENCARGO_{selected.parent.parent.name[:8]}_{uuid4().hex[:8]}.zip'
    temporary = target.with_suffix('.zip.tmp')
    manifest = {'schema': 1, 'selected_mission': selected.parent.parent.name,
                'missions': [], 'omitted': [], 'files': [], 'uploaded': False,
                'contents': 'Pedidos, respuestas de modelos, rutas y salidas guardadas. No ejecuta el proyecto.'}
    total, visited = 0, set()
    try:
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
            report = selected
            while report:
                if (report.is_symlink() or report.parent.is_symlink() or report.parent.parent.is_symlink()
                        or report.resolve().parent.parent.parent != missions
                        or report.parent.name != 'output' or report.name != 'mission_progress.json'):
                    raise ValueError('La cadena de continuacion sale de las misiones locales')
                if report in visited:
                    raise ValueError('La cadena de continuacion contiene un ciclo')
                if len(visited) >= 10:
                    manifest['omitted'].append('Historia anterior a las ultimas 10 misiones')
                    break
                visited.add(report)
                state = read_evidence(report)
                if state.get('objective') != selected_objective:
                    raise ValueError('La cadena de continuacion cambia de encargo')
                identifier = report.parent.parent.name
                manifest['missions'].append({'id': identifier, 'state': state.get('state'),
                    'objective': state.get('objective'), 'message': state.get('message', ''),
                    'calls': len(state.get('calls', [])), 'budget': state.get('budget', {})})
                for path in sorted(report.parent.iterdir()):
                    if not re.fullmatch(r'[A-Za-z0-9_.-]+\.(?:json|xml|txt|diff|log)', path.name):
                        continue
                    if path.is_symlink() or not path.is_file():
                        manifest['omitted'].append(identifier + '/' + path.name + ': enlace o directorio')
                        continue
                    size = path.stat().st_size
                    if size > 16 * 1024**2 or total + size > 64 * 1024**2:
                        manifest['omitted'].append(identifier + '/' + path.name + ': limite de tamano')
                        continue
                    name = identifier + '/output/' + path.name
                    archive.write(path, name)
                    manifest['files'].append(name)
                    total += size
                previous = state.get('resumed_from')
                report = Path(previous) if previous else None
            manifest['complete'] = not manifest['omitted']
            archive.writestr('DIAGNOSTICO.json', json.dumps(manifest, ensure_ascii=False, indent=2))
        temporary.replace(target)
        return target
    except (OSError, ValueError, TypeError, KeyError):
        temporary.unlink(missing_ok=True)
        raise
