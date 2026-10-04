"""Compilacion y comprobacion del .exe solicitado, ejecutadas en Windows."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
from uuid import uuid4

from igris_os.security.sandbox import JobObjectSandbox
from .mission_workspace import digest, project_files, safe_relative, save_json

PYINSTALLER_PACKAGE = 'pyinstaller==6.22.3'


def is_windows():
    return os.name == 'nt'


def _source_hashes(files, executable_name):
    return {p: digest(b) for p, b in project_files(files.root).items() if p != executable_name}


def _is_pe(path):
    with path.open('rb') as stream:
        header = stream.read(64)
        if len(header) != 64 or header[:2] != b'MZ':
            return False
        offset = int.from_bytes(header[60:64], 'little')
        if not 64 <= offset <= path.stat().st_size - 4:
            return False
        stream.seek(offset)
        return stream.read(4) == b'PE\0\0'


def _self_test(tools, executable):
    report = tools.files.output / ('executable_self_test_' + uuid4().hex + '.json')
    run = tools._run([str(executable), '--igris-self-test', str(report)], 'executable_self_test', timeout=90)
    try:
        if report.stat().st_size > 100000:
            raise ValueError('Informe excesivo')
        results = json.loads(report.read_text(encoding='utf-8'))
        checks = results.get('checks', [])
        ok = (run['ok'] and results.get('ok') is True and isinstance(checks, list) and bool(checks)
              and all(isinstance(c, dict) and c.get('ok') is True and
                      isinstance(c.get('name'), str) and c['name'].strip() for c in checks))
        return {'ok': bool(ok), 'process': run, 'report': str(report), 'checks': checks}
    except (OSError, ValueError, TypeError):
        return {'ok': False, 'process': run, 'error': 'El ejecutable no produjo un autodiagnostico valido'}


def build_python_executable(tools, entrypoint, name, data_files=()):
    if not is_windows():
        return {'ok': False, 'error': 'El .exe debe compilarse y comprobarse en Windows; no se ha creado'}
    entry = tools.files.path(entrypoint)
    if entry.suffix != '.py' or not entry.is_file():
        raise ValueError('Indica el archivo .py de entrada existente')
    name = safe_relative(str(name))
    if '/' in name or len(name) > 80 or name.startswith('-'):
        raise ValueError('Nombre de ejecutable no valido')
    if name.lower().endswith('.exe'):
        name = name[:-4]
    executable_name = name + '.exe'
    python = tools.python_executable()
    probe = tools._run([python, '-m', 'PyInstaller', '--version'], 'pyinstaller_version')
    if not probe['ok']:
        installed = tools.install_python([PYINSTALLER_PACKAGE])
        if not installed.get('ok'):
            return installed
        python = str(tools.python)
    source = _source_hashes(tools.files, executable_name)
    work = tools.files.workspace / 'packaging' / uuid4().hex
    work.mkdir(parents=True)
    command = [python, '-m', 'PyInstaller', '--noconfirm', '--onefile', '--windowed', '--noupx',
        '--name', name, '--distpath', str(work / 'dist'), '--workpath', str(work / 'build'),
        '--specpath', str(work), '--paths', str(tools.files.root / 'src')]
    if not isinstance(data_files, (list, tuple)) or len(data_files) > 40:
        raise ValueError('Lista de recursos no valida')
    for relative in data_files:
        relative = safe_relative(relative)
        path = tools.files.path(relative)
        if not path.is_file():
            raise ValueError('No existe el recurso: ' + relative)
        command += ['--add-data', str(path) + ':' + Path(relative).parent.as_posix()]
    command.append(str(entry))
    built = tools._run(command, 'build_windows_executable', timeout=600,
        sandbox=JobObjectSandbox(memory_limit_mb=4096, cpu_seconds=600, max_processes=16))
    executable = work / 'dist' / executable_name
    if not built['ok'] or not executable.is_file() or not _is_pe(executable):
        return {'ok': False, 'error': 'No se produjo un ejecutable Windows valido', 'build': built}
    if executable.stat().st_size > 64 * 1024**2:
        return {'ok': False, 'error': 'El ejecutable excede el limite de archivo de esta entrega'}
    tested = _self_test(tools, executable)
    if not tested['ok']:
        return {'ok': False, 'error': 'Fallo la comprobacion del ejecutable', 'self_test': tested}
    if _source_hashes(tools.files, executable_name) != source:
        return {'ok': False, 'error': 'La compilacion o el autodiagnostico alteraron el codigo'}
    target = tools.files.path(executable_name)
    shutil.copy2(executable, target)
    receipt = {'ok': True, 'executable_name': executable_name, 'sha256': digest(target.read_bytes()),
               'source_hashes': source, 'entrypoint': entrypoint, 'build': built, 'self_test': tested}
    save_json(tools.files.output / 'windows_executable.json', receipt)
    return {**receipt, 'path': str(target)}


def verify_windows_executable(tools, contract, *, execute=False):
    if not contract.get('requires_executable'):
        return {'ok': True, 'required': False}
    try:
        receipt = json.loads((tools.files.output / 'windows_executable.json').read_text(encoding='utf-8'))
        name = safe_relative(receipt['executable_name'])
        if '/' in name or (contract.get('executable_name') and name != contract['executable_name']):
            raise ValueError('El nombre del ejecutable no es el solicitado')
        target = tools.files.path(name)
        if (receipt.get('ok') is not True or not receipt.get('self_test', {}).get('ok')
                or not target.is_file() or not _is_pe(target) or digest(target.read_bytes()) != receipt['sha256']
                or _source_hashes(tools.files, name) != receipt['source_hashes']):
            raise ValueError('El .exe falta, cambio o no corresponde al codigo comprobado; vuelve a compilarlo')
        final_test = {}
        if execute:
            if not is_windows():
                raise ValueError('La comprobacion final del .exe requiere Windows')
            tested = _self_test(tools, target)
            if not tested['ok'] or digest(target.read_bytes()) != receipt['sha256']:
                raise ValueError('El ejecutable no supera su comprobacion final')
            final_test = tested
        return {'ok': True, 'required': True, 'path': str(target), 'receipt': receipt,
                'final_self_test': final_test}
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return {'ok': False, 'required': True,
                'error': 'Falta el ejecutable solicitado y comprobado: ' + str(exc)}
