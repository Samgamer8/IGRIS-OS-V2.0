"""Herramientas ejecutables del equipo. Los resultados proceden de procesos reales."""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import re
import shutil
import sys
import xml.etree.ElementTree as ET

from igris_os.games.runtime import GodotRuntime
from igris_os.security.restricted import _filtered_env
from igris_os.security.sandbox import JobObjectSandbox
from .mission_workspace import MissionFiles, digest, project_files, save_json


class MissionTools:
    def __init__(self, files: MissionFiles, *, allow_downloads: bool = False,
                 sandbox=None, godot=None):
        self.files = files
        self.allow_downloads = allow_downloads
        self.sandbox = sandbox or JobObjectSandbox(
            memory_limit_mb=2048, cpu_seconds=120, max_processes=12)
        self.godot = godot or GodotRuntime(timeout=120)
        self.history: list[dict] = []
        self.dependencies = files.workspace / 'dependencies'
        self.python = (self.dependencies / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python'))
        self.python_packages = ['pytest']
        self.known_python_versions = {}

    def inventory(self) -> dict:
        python, python_error = '', ''
        try:
            python = self.python_executable()
        except ValueError as exc:
            python_error = str(exc)
        return {'python': python, 'python_error': python_error, 'node': shutil.which('node'),
                'npm': shutil.which('npm'), 'godot': str(self.godot.executable or ''),
                'verification_adapters': ['python:pytest', 'godot:SceneTree', 'javascript:node:test'],
                'downloads_allowed': self.allow_downloads,
                'available_actions': ['list_files', 'read_file', 'read_files', 'search', 'write_file', 'write_files',
                    'replace_text', 'run_tests', 'inspect_python_environment', 'install_python_packages',
                    'install_node_packages', 'ensure_godot', 'build_windows_executable', 'finish']}

    def python_executable(self) -> str:
        if self.python.is_file():
            return str(self.python)
        if getattr(sys, 'frozen', False):
            raise ValueError('No hay interprete Python de la mision; inicia IGRIS desde launch_igris.cmd')
        return sys.executable

    def inspect_python(self, packages=None) -> dict:
        from .python_environment import inspect_python_environment
        from .mission_dependencies import package_key
        result = inspect_python_environment(self, packages)
        if result['ok']:
            for package in result['packages']:
                name = package['name']
                if name not in self.python_packages and len(self.python_packages) < 20:
                    self.python_packages.append(name)
                if package['installed'] and (package_key(name) in self.known_python_versions
                                              or len(self.known_python_versions) < 32):
                    self.known_python_versions[package_key(name)] = name + '==' + package['version']
            self._save()
        return result

    def _run(self, command: list[str], label: str, *, timeout=120, cwd=None, sandbox=None) -> dict:
        env = _filtered_env()
        env.update(PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
                   PYTHONPATH=os.pathsep.join([str(self.files.root), str(self.files.root / 'src')]))
        result = (sandbox or self.sandbox).run(command, timeout=timeout,
            cwd=str(cwd or self.files.root), env=env)
        output = (result.stdout or '') + '\n' + (result.stderr or '')
        record = {'label': label, 'command': command,
                  'ok': result.returncode == 0 and not result.timed_out,
                  'returncode': result.returncode, 'timed_out': result.timed_out,
                  'sandboxed': result.sandboxed, 'output': output[-20000:]}
        self.history.append(record)
        self._save()
        return record

    def _save(self):
        save_json(self.files.output / 'tool_runs.json', {'runs': self.history})
        save_json(self.files.output / 'tool_environment.json', {
            'python': str(self.python), 'godot': str(self.godot.executable or ''),
            'python_packages': self.python_packages, 'known_python_versions': self.known_python_versions})

    def restore_environment(self, previous: Path):
        receipt = previous / 'output/tool_environment.json'
        if not receipt.is_file():
            return
        data = json.loads(receipt.read_text(encoding='utf-8'))
        self.python_packages = data.get('python_packages', ['pytest'])
        self.known_python_versions = data.get('known_python_versions', {})
        # Virtual environments cannot be moved safely; retain the environment
        # in the earlier mission instead of losing its installed dependencies.
        python = Path(data.get('python', ''))
        if python.is_file() and python.absolute().is_relative_to(self.files.workspace.parent):
            self.python = python
        godot = data.get('godot')
        if godot and Path(godot).is_file():
            self.godot = GodotRuntime(godot, timeout=120)
        self._save()

    def _godot_check(self, run, label: str) -> dict:
        record = {'label': label, 'ok': run.ok, 'returncode': run.returncode,
                  'command': list(run.command), 'output': run.output[-20000:]}
        self.history.append(record)
        self._save()
        return record

    def _pytest(self, paths: list[str], label: str) -> dict:
        # Override project addopts so -k/--ignore/--collect-only cannot make the
        # acceptance suite disappear. Parse the report, not the model's claim.
        report = self.files.output / ('pytest_' + str(len(self.history)) + '.xml')
        report.parent.mkdir(parents=True, exist_ok=True)
        python = self.python_executable()
        run = self._run([python, '-m', 'pytest', '-q', '-o', 'addopts=',
                         '-p', 'no:cacheprovider', '--junitxml=' + str(report), *paths], label)
        try:
            cases = ET.parse(report).getroot().findall('.//testcase')
            run['tests'] = len(cases)
            run['ok'] = run['ok'] and bool(cases) and all(
                not any(c.tag in {'failure', 'error', 'skipped'} for c in case)
                for case in cases)
        except (OSError, ET.ParseError):
            run.update(ok=False, tests=0)
        self._save()
        return run

    def verify(self, technology: str, test_paths: list[str]) -> dict:
        self.files.check_locked()
        before = {p: digest(b) for p, b in project_files(self.files.root).items()}
        checks = []
        if not test_paths:
            return {'ok': False, 'checks': [], 'error': 'Faltan pruebas de los requisitos'}
        for p in test_paths:
            self.files.path(p)
        if technology == 'python':
            for path, data in project_files(self.files.root).items():
                if path.endswith('.py'):
                    try:
                        ast.parse(data.decode('utf-8-sig'), filename=path)
                    except (SyntaxError, UnicodeError) as exc:
                        return {'ok': False, 'checks': [], 'error': str(exc)}
            regression = [p for p in self.files.locked if p.endswith('.py') and p not in test_paths]
            if regression:
                checks.append(self._pytest(regression, 'regression'))
            for path in test_paths:
                if not path.endswith('.py'):
                    raise ValueError('La prueba Python debe terminar en .py')
                checks.append(self._pytest([path], path))
        elif technology == 'godot':
            if not self.godot.available:
                return {'ok': False, 'checks': [], 'error': 'Godot ausente; usa ensure_godot'}
            checks.append(self._godot_check(self.godot.import_project(self.files.root), 'import'))
            if checks[-1]['ok']:
                regression = [p for p in self.files.locked if p.endswith('.gd') and p not in test_paths]
                for path in list(dict.fromkeys([*regression, *test_paths])):
                    if not path.endswith('.gd'):
                        raise ValueError('La prueba Godot debe terminar en .gd')
                    check = self._godot_check(self.godot.run_script(self.files.root, path), path)
                    if path in test_paths:
                        check['ok'] = check['ok'] and 'IGRIS_TEST_OK' in check['output']
                    checks.append(check)
                checks.append(self._godot_check(
                    self.godot.run(self.files.root, frames=60, headless=True), 'boot'))
        elif technology == 'javascript':
            node = shutil.which('node')
            if not node:
                return {'ok': False, 'checks': [], 'error': 'Node no esta instalado; se requiere su runtime local'}
            regression = [p for p in self.files.locked if p.endswith(('.js', '.mjs', '.cjs')) and p not in test_paths]
            for path in list(dict.fromkeys([*regression, *test_paths])):
                run = self._run([node, '--test', '--test-reporter=tap', self.files.path(path).as_posix()], path)
                count = re.search(r'# tests (\d+)', run['output'])
                skipped = re.search(r'# (?:skipped|todo) [1-9]', run['output'])
                run['ok'] = run['ok'] and bool(count and int(count[1])) and not skipped
                checks.append(run)
        else:
            return {'ok': False, 'checks': [], 'error': 'No hay verificador ejecutable para ' + technology}
        self.files.check_locked()
        after = {p: digest(b) for p, b in project_files(self.files.root).items()}
        modified = [p for p, h in before.items() if after.get(p) != h]
        unexpected = [p for p in after if p not in before and not (
            technology == 'godot' and p.endswith('.gd.uid') and p[:-4] in after)]
        self._save()
        return {'ok': bool(checks) and all(c['ok'] for c in checks) and not modified and not unexpected,
                'checks': checks, 'source_mutations': modified + unexpected}

    def install_python(self, packages: list[str]) -> dict:
        from .mission_dependencies import install_python
        return install_python(self, packages)

    def install_node(self, packages: list[str]) -> dict:
        self._validate_packages(packages, python=False)
        if not self.allow_downloads:
            return {'ok': False, 'needs_download_approval': True, 'packages': packages}
        npm = shutil.which('npm')
        node = shutil.which('node')
        if not npm or not node:
            return {'ok': False, 'error': 'Node/npm no esta instalado'}
        if not (self.files.root / 'package.json').is_file():
            return {'ok': False, 'error': 'Crea y lee primero package.json'}
        # On Windows call npm-cli through node without a cmd.exe shell.
        cli = Path(npm).resolve().parent / 'node_modules/npm/bin/npm-cli.js'
        command = [node, str(cli)] if cli.is_file() else [npm]
        return self._run([*command, 'install', '--ignore-scripts', '--no-audit',
                          '--no-fund', '--registry=https://registry.npmjs.org', *packages],
                         'install_node_packages')

    @staticmethod
    def _validate_packages(packages, *, python):
        pattern = (r'[A-Za-z0-9][A-Za-z0-9_.-]*==[A-Za-z0-9][A-Za-z0-9_.+!-]*'
                   if python else r'(?:@[a-z0-9_.-]+/)?[a-z0-9][a-z0-9_.-]*@\d+\.\d+\.\d+(?:-[a-z0-9.-]+)?')
        if (not isinstance(packages, list) or not 1 <= len(packages) <= 12
                or any(not isinstance(p, str) or not re.fullmatch(pattern, p) for p in packages)):
            raise ValueError('Especifica paquetes con version exacta; sin rutas, URLs ni opciones')

    def ensure_godot(self):
        if self.godot.available:
            return {'ok': True, 'path': str(self.godot.executable)}
        if not self.allow_downloads:
            return {'ok': False, 'needs_download_approval': True, 'tool': 'godot'}
        from .portable_tools import install_godot
        installed = install_godot(self.files.workspace / 'tools')
        self.godot = GodotRuntime(installed['path'], timeout=120)
        self.history.append({'label': 'install_godot', 'ok': True, **installed})
        self._save()
        return installed
