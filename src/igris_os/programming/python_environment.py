"""Inspeccion local de metadatos en el interprete que usara la mision."""
from __future__ import annotations

import json
import re

from .mission_workspace import save_json


# Fixed code plus a JSON argv value: package names never become Python code.
# -I ignores project modules and PYTHONPATH; dependencies are not imported.
PROBE = '''import importlib.metadata as metadata
import json
import sys

packages = []
for name in json.loads(sys.argv[1]):
    try:
        dist = metadata.distribution(name)
        packages.append({"name": name, "installed": True,
                         "version": dist.version,
                         "requires_python": dist.metadata.get("Requires-Python", "")})
    except metadata.PackageNotFoundError:
        packages.append({"name": name, "installed": False, "version": "",
                         "requires_python": ""})
print(json.dumps({"python": {"executable": sys.executable,
    "version": sys.version.split()[0], "version_info": list(sys.version_info[:3]),
    "platform": sys.platform, "virtual_environment": sys.prefix != sys.base_prefix},
    "packages": packages}))
'''


def inspect_python_environment(tools, packages=None) -> dict:
    if packages is None:
        packages = ['pytest']
    if (not isinstance(packages, list) or len(packages) > 20
            or any(not isinstance(p, str) or len(p) > 100 or not re.fullmatch(
                r'[A-Za-z0-9][A-Za-z0-9_.-]*', p) for p in packages)):
        raise ValueError('Indica hasta 20 nombres de distribuciones Python; sin versiones, rutas ni opciones')
    packages = list(dict.fromkeys(packages))
    run = tools._run([tools.python_executable(), '-I', '-B', '-c', PROBE, json.dumps(packages)],
                     'inspect_python_environment', timeout=30, cwd=tools.files.output)
    try:
        if not run['ok']:
            raise ValueError('El interprete no completo el diagnostico')
        data = json.loads(run['output'])
        if (not isinstance(data, dict) or not isinstance(data.get('python'), dict)
                or not isinstance(data.get('packages'), list)
                or [p.get('name') for p in data['packages']] != packages
                or any(type(p.get('installed')) is not bool for p in data['packages'])):
            raise ValueError('Respuesta de diagnostico incompleta')
        result = {'ok': True, **data,
            'missing_packages': [p['name'] for p in data['packages'] if not p['installed']],
            'platform_limitations': [p['name'] + ' requiere Windows' for p in data['packages']
                if p['name'].casefold() in {'wmi', 'pywin32'} and data['python']['platform'] != 'win32'],
            'imports_tested': False,
            'scope': 'Metadatos del entorno aislado; las importaciones, compatibilidad y funciones requieren pruebas.',
            'process': run}
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        result = {'ok': False, 'error': 'No se pudo inspeccionar Python: ' + str(exc),
                  'process': run}
    save_json(tools.files.output / 'python_environment.json', result)
    return result
