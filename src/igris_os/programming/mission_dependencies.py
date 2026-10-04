"""Prepare a mission interpreter without silently losing its Python test runner."""
from __future__ import annotations

from importlib import metadata
import re


def package_key(name):
    return re.sub(r'[-_.]+', '-', name).lower()


def install_python(tools, packages):
    tools._validate_packages(packages, python=True)
    # A venv created from another venv does not inherit that venv's packages.
    # Retain versions observed for THIS mission, not every package on the PC.
    inspected = tools.inspect_python(tools.python_packages)
    if not inspected['ok']:
        return inspected
    pins = {package_key(p.split('==')[0]): p for p in packages}
    for name in tools.python_packages:
        key = package_key(name)
        if key in pins or key in tools.known_python_versions:
            continue
        try:
            tools.known_python_versions[key] = name + '==' + metadata.version(name)
        except metadata.PackageNotFoundError:
            pass
    if 'pytest' not in pins and 'pytest' not in tools.known_python_versions:
        return {'ok': False, 'error': 'Falta pytest y no hay una version local comprobada; '
                'indica pytest con version exacta en install_python_packages.'}
    for key, pin in tools.known_python_versions.items():
        tools._validate_packages([pin], python=True)
        pins.setdefault(key, pin)
    planned = list(pins.values())
    if not tools.allow_downloads:
        return {'ok': False, 'needs_download_approval': True, 'packages': planned,
                'requested_packages': packages,
                'error': 'Autoriza descargar estas dependencias y el verificador en el encargo'}
    if not tools.python.exists():
        made = tools._run([tools.python_executable(), '-I', '-m', 'venv',
                          '--system-site-packages', str(tools.dependencies)],
                         'create_python_environment', cwd=tools.files.workspace)
        if not made['ok']:
            return made
    # -I also prevents a repository's pip.py/venv.py from replacing the tools.
    run = tools._run([str(tools.python), '-I', '-m', 'pip', '--isolated', 'install',
                     '--disable-pip-version-check', '--only-binary=:all:',
                     '--index-url', 'https://pypi.org/simple', *planned],
                    'install_python_packages', timeout=120, cwd=tools.files.workspace)
    if not run['ok']:
        return {'ok': False, 'packages': planned, 'installation': run,
                'error': run.get('output') or 'Fallo la instalacion de dependencias'}
    actual, environments = {}, []
    names = [p.split('==')[0] for p in planned]
    for start in range(0, len(names), 20):
        environment = tools.inspect_python(names[start:start + 20])
        environments.append(environment)
        if environment['ok']:
            actual.update({package_key(p['name']): p['version']
                           for p in environment['packages'] if p['installed']})
    mismatches = [pin for key, pin in pins.items() if actual.get(key) != pin.split('==')[1]]
    runner = tools._run([str(tools.python), '-I', '-m', 'pytest', '--version'],
                        'verify_python_test_runner', timeout=30, cwd=tools.files.output)
    ok = not mismatches and runner['ok']
    tools._run([str(tools.python), '-I', '-m', 'pip', 'freeze'], 'python_environment',
               cwd=tools.files.workspace)
    error = '' if ok else ('El entorno no quedo preparado: ' + ', '.join(mismatches)
                           if mismatches else 'pytest no puede ejecutarse: ' + runner.get('output', ''))
    return {'ok': ok, 'packages': planned, 'installation': run, 'environments': environments,
            'test_runner': runner, 'mismatches': mismatches,
            'error': error}
