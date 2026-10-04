"""Publicacion aprobada de un resultado del equipo, comprobada de nuevo."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
from uuid import uuid4

from igris_os.domain import ExecutionResult
from igris_os.files.repository_apply import RepositoryChangeApplier
from igris_os.games.runtime import GodotRuntime
from .mission_team import ProgrammingTeam
from .mission_tools import MissionTools
from .mission_workspace import MissionFiles, digest, project_files, save_json, safe_relative


def deliver_programming(payload, *, tools_factory=MissionTools):
    published = False
    target, backup, report = None, '', None
    try:
        report_path = Path(payload['report']).resolve()
        if report_path.name != 'programming_delivery.json' or report_path.parent.name != 'output':
            raise ValueError('Informe de entrega no valido')
        evidence_workspace = report_path.parent.parent
        document = json.loads(report_path.read_text(encoding='utf-8'))
        files = MissionFiles(evidence_workspace)
        if (document.get('state') != 'ready_for_review' or
                Path(document['staged_root']).resolve() != files.root or
                not document['verification'].get('ok') or
                not ProgrammingTeam._review_ok(document['review'], document['plan']['requirements'])):
            raise ValueError('Falta una revision completa y pruebas aprobadas')
        actual = {p: digest(b) for p, b in project_files(files.root).items()}
        if actual != document.get('snapshot'):
            raise ValueError('La copia cambio despues de ser revisada; debe verificarse y revisarse otra vez')
        files.locked = document['locked_tests']
        files.check_locked()
        source = Path(document['source_root']) if document.get('source_root') else None
        manifest_path = files.output / 'staging_manifest.json'
        if Path(document['staging_manifest']).resolve() != manifest_path:
            raise ValueError('Manifiesto incorrecto')
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if source:
            expected = {r['path']: r['sha256'] for r in manifest['files']}
            if expected != {p: digest(b) for p, b in project_files(source).items()}:
                raise ValueError('El original cambio desde el inicio del encargo')
        tools = tools_factory(files, godot=GodotRuntime(document.get('godot_executable') or None))
        tools.restore_environment(evidence_workspace)
        from igris_os.application.delivery_request import requested_delivery
        from .windows_executable import verify_windows_executable
        contract = document.get('delivery_contract') or requested_delivery(document['objective'])
        artifact = verify_windows_executable(tools, contract, execute=True)
        if not artifact['ok']:
            raise ValueError(artifact['error'])
        checked = tools.verify(document['technology'], document['test_paths'])
        if not checked['ok']:
            raise ValueError('La entrega ya no supera sus pruebas; el original se conserva')
        if {p: digest(b) for p, b in project_files(files.root).items()} != actual:
            raise ValueError('Las pruebas alteraron la copia revisada')
        changed = document['changed_files']
        if not isinstance(changed, list) or not changed:
            raise ValueError('No hay archivos programados para entregar')
        for relative in changed:
            safe_relative(relative)
        workspace = Path(payload['workspace']).resolve()
        backup = ''
        selected_destination = str(payload.get('destination') or document.get('destination') or '').strip()
        if contract.get('destination'):
            actual_target = source or Path(selected_destination)
            if actual_target.resolve() != Path(contract['destination']).resolve():
                raise ValueError('La carpeta de entrega no coincide con el escritorio y nombre solicitados')
        if source:
            result = RepositoryChangeApplier(workspace).apply(
                source, files.root, changed, manifest_path, confirmed=True)
            target, backup = Path(result.source_root), result.backup_root
            published = True
        else:
            destination = selected_destination
            if not destination:
                raise ValueError('Indica la carpeta nueva de entrega')
            target = Path(destination).expanduser().resolve()
            if target.exists() or not target.parent.is_dir():
                raise ValueError('El destino debe ser una carpeta nueva dentro de una carpeta existente')
            if target.is_relative_to(evidence_workspace) or evidence_workspace.is_relative_to(target):
                raise ValueError('La entrega debe estar fuera del workspace del encargo')
            temporary = target.with_name(target.name + '.igris-' + uuid4().hex)
            try:
                temporary.mkdir()
                for relative, data in project_files(files.root).items():
                    output = temporary / relative
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_bytes(data)
                if project_files(temporary) != project_files(files.root):
                    raise ValueError('Fallo de integridad de la entrega')
                temporary.rename(target)
                published = True
            finally:
                if temporary.is_dir():
                    shutil.rmtree(temporary)
        report = workspace / 'output' / 'programming_applied.json'
        if not all(digest((target / p).read_bytes()) == actual[p] for p in changed):
            raise ValueError('El destino cambio durante la comprobacion final; consulta el respaldo')
        save_json(report, {'schema': 1, 'source_report': str(report_path),
            'project': str(target), 'backup': backup, 'changed_files': changed,
            'verification': checked, 'user_accepted': bool(payload.get('user_accepted')),
            'manual_checks': document.get('manual_checks', []),
            'verified_after_copy': True, 'executable_verification': artifact,
            'delivery_contract': contract})
        # Only record a reusable experience after real verification and publication.
        memory = evidence_workspace.parent.parent / 'learning' / 'programming'
        learning_warning = ''
        try:
            save_json(memory / (evidence_workspace.name + '.json'), {
                'objective': document['objective'], 'project': str(target),
                'requirements': document['plan']['requirements'], 'report': str(report),
                'models': sorted({c['model'] for c in document['calls']}),
                'test_verified': True, 'user_accepted': bool(payload.get('user_accepted'))})
        except OSError as exc:
            learning_warning = 'La entrega se completo, pero no se guardo la experiencia: ' + str(exc)
        return ExecutionResult.success('Proyecto programado, comprobado y entregado.',
            project=str(target), updated_existing=bool(source), backup=backup,
            changed_files=changed, report=str(report), verified=True,
            acceptance_verified=bool(payload.get('user_accepted')),
            executable=str(target / Path(artifact['path']).name) if artifact.get('path') else '',
            work_status='delivered', manual_checks=document.get('manual_checks', []),
            learning_warning=learning_warning)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return ExecutionResult.failure(str(exc), 'WORK_DELIVERY_BLOCKED',
            data={'original_modified': published, 'project': str(target or ''),
                  'backup': str(backup), 'report': str(report or ''),
                  'work_status': 'delivery_incomplete' if published else 'blocked'})
