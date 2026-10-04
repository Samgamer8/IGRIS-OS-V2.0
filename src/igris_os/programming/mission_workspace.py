"""Workspace de un encargo: lectura acotada, ediciones y evidencia independientes."""
from __future__ import annotations

import ast
import difflib
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath

EXCLUDED = {'.git', '.godot', '.venv', 'venv', '.tools', 'node_modules',
            '__pycache__', '.pytest_cache', 'runtime', 'build', 'dist', 'target',
            'igris_previous'}
TEXT_SUFFIXES = {'.py', '.gd', '.godot', '.tscn', '.tres', '.lua', '.js', '.mjs',
                 '.cjs', '.ts', '.tsx', '.jsx', '.json', '.toml', '.yaml', '.yml',
                 '.html', '.css', '.md', '.txt', '.cfg', '.ini', '.svg', '.rs',
                 '.go', '.cpp', '.h', '.cs', '.java', '.cmd', '.bat', '.ps1', '.sh'}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temporary, path)


def safe_relative(value: str) -> str:
    raw = str(value).replace('\\', '/')
    parts = raw.split('/')
    if (not raw or Path(raw).is_absolute() or PureWindowsPath(raw).drive
            or any(p in {'', '.', '..'} or ':' in p or p.endswith((' ', '.'))
                   or p.casefold() in EXCLUDED
                   or any(ord(c) < 32 or c in '<>"|?*' for c in p)
                   or p.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL',
                       *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}
                   for p in parts)
            or any(p.casefold().startswith('.env') for p in parts)
            or Path(raw).suffix.casefold() in {'.pem', '.key', '.pfx'}):
        raise ValueError('Ruta fuera del proyecto o privada: ' + raw)
    return raw


def project_files(root: Path) -> dict[str, bytes]:
    result, total = {}, 0
    if root.is_symlink() or getattr(root, 'is_junction', lambda: False)():
        raise ValueError('La carpeta es un enlace')
    for folder, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d.casefold() not in EXCLUDED)
        for name in dirs + files:
            path = Path(folder) / name
            if path.is_symlink() or getattr(path, 'is_junction', lambda: False)():
                raise ValueError('Enlace no permitido en el proyecto: ' + str(path))
        for name in sorted(files):
            path = Path(folder) / name
            relative = path.relative_to(root).as_posix()
            try:
                safe_relative(relative)
            except ValueError:
                continue
            size = path.stat().st_size
            total += size
            if size > 64 * 1024**2 or total > 512 * 1024**2 or len(result) >= 5000:
                raise ValueError('El proyecto excede la copia completa permitida; no se usara una copia parcial')
            result[relative] = path.read_bytes()
    return result


def is_test(path: str) -> bool:
    name = Path(path).name.casefold()
    return (name.startswith(('test_', 'verify_', 'acceptance_'))
            or '/tests/' in '/' + path.casefold()
            or name.endswith(('_test.py', '.test.js', '.test.mjs', '.spec.js')))


class MissionFiles:
    def __init__(self, workspace: Path):
        self.workspace = Path(workspace).resolve()
        self.root = self.workspace / 'working' / 'repository'
        self.output = self.workspace / 'output'
        self.before: dict[str, bytes] = {}
        self.read_hashes: dict[str, str] = {}
        self.locked: dict[str, str] = {}

    def prepare(self, source: Path | None, *, resume_report: str = '') -> None:
        if self.root.exists():
            report = Path(resume_report) if resume_report else None
            expected_report = self.output / 'mission_progress.json'
            if (report is None or report.is_symlink() or
                    report.resolve() != expected_report.resolve() or
                    not report.is_file() or self.root.is_symlink() or
                    getattr(self.root, 'is_junction', lambda: False)() or
                    not self.root.is_dir()):
                raise ValueError('Ya existe el workspace de este encargo')
            manifest_path = self.output / 'staging_manifest.json'
            if (manifest_path.is_symlink() or not manifest_path.is_file() or
                    manifest_path.stat().st_size > 4 * 1024 * 1024):
                raise ValueError('No se puede verificar el workspace existente')
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            if (not isinstance(manifest, dict) or
                    Path(str(manifest.get('staged', ''))).resolve() != self.root.resolve()):
                raise ValueError('El manifiesto no pertenece a este workspace')
            manifest_source = str(manifest.get('source') or '')
            if source is not None:
                source = Path(source).expanduser()
                if not source.is_dir() or source.is_symlink():
                    raise ValueError('No existe la carpeta del proyecto')
                source = source.resolve()
            if (str(source) if source else '') != (
                    str(Path(manifest_source).resolve()) if manifest_source else ''):
                raise ValueError('La continuacion debe conservar el proyecto original')
            original = project_files(source) if source else {}
            manifest_files = manifest.get('files')
            if not isinstance(manifest_files, list):
                raise ValueError('El manifiesto del workspace no es valido')
            expected = {}
            for item in manifest_files:
                if not isinstance(item, dict):
                    raise ValueError('El manifiesto del workspace no es valido')
                relative = safe_relative(item.get('path', ''))
                expected[relative] = str(item.get('sha256') or '')
            if expected != {path: digest(data) for path, data in original.items()}:
                raise ValueError('El original cambio desde la creacion del workspace')
            self.before = original
            self.locked = {p: digest(data) for p, data in original.items() if is_test(p)}
            return
        if source:
            source = Path(source).expanduser()
            if not source.is_dir():
                raise ValueError('No existe la carpeta del proyecto')
            self.before = project_files(source)
            source = source.resolve()
            if self.workspace.is_relative_to(source) or source.is_relative_to(self.workspace):
                raise ValueError('La copia de trabajo debe quedar fuera del original')
        self.root.mkdir(parents=True)
        for relative, data in self.before.items():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        if source and project_files(source) != self.before:
            raise ValueError('El original cambio durante la copia')
        self.locked = {p: digest(data) for p, data in self.before.items() if is_test(p)}
        save_json(self.output / 'staging_manifest.json', {
            'schema': 1, 'source': str(source) if source else '', 'staged': str(self.root),
            'files': [{'path': p, 'sha256': digest(b)} for p, b in self.before.items()],
            'truncated': False, 'source_modified': False})

    def path(self, relative: str) -> Path:
        relative = safe_relative(relative)
        path = self.root / relative
        for parent in (path, *path.parents):
            if parent == self.root:
                break
            if parent.is_symlink() or getattr(parent, 'is_junction', lambda: False)():
                raise ValueError('No se permiten enlaces')
        if not path.resolve().is_relative_to(self.root):
            raise ValueError('Ruta fuera del workspace')
        return path

    def listing(self) -> list[dict]:
        return [{'path': p, 'bytes': len(b)} for p, b in project_files(self.root).items()]

    def read(self, relative: str, start: int = 1, lines: int = 160) -> dict:
        relative = safe_relative(relative)
        path = self.path(relative)
        data = path.read_bytes()
        if path.suffix.casefold() not in TEXT_SUFFIXES or len(data) > 1_000_000:
            raise ValueError('El archivo no es texto editable o excede 1 MB')
        text = data.decode('utf-8-sig')
        self.read_hashes[relative] = digest(data)
        rows = text.splitlines()
        start = max(1, int(start))
        end = min(len(rows), start - 1 + min(250, max(1, int(lines))))
        return {'path': relative, 'sha256': digest(data), 'total_lines': len(rows),
                'start': start, 'end': end, 'content': '\n'.join(rows[start-1:end])}

    def _validate_write(self, relative: str, content: str, *, tester: bool = False):
        relative = safe_relative(relative)
        path = self.path(relative)
        if not isinstance(content, str) or len(content.encode('utf-8')) > 1_000_000:
            raise ValueError('Contenido invalido o superior a 1 MB')
        if path.suffix.casefold() not in TEXT_SUFFIXES:
            raise ValueError('Extension no editable')
        if relative.casefold() in {p.casefold() for p in self.locked}:
            raise ValueError('Prueba inmutable: ' + relative)
        if tester and not is_test(relative):
            raise ValueError('El comprobador solo puede crear pruebas')
        current = path.read_bytes() if path.is_file() else None
        if current is not None and self.read_hashes.get(relative) != digest(current):
            raise ValueError('Lee primero la version actual del archivo: ' + relative)
        if path.suffix == '.py':
            ast.parse(content, filename=relative)
        elif path.suffix == '.json':
            json.loads(content)
        if path.exists() and not path.is_file():
            raise ValueError('La ruta no es un archivo editable: ' + relative)
        return path, current

    def write(self, relative: str, content: str, *, tester: bool = False) -> dict:
        relative = safe_relative(relative)
        path, current = self._validate_write(relative, content, tester=tester)
        if current == content.encode('utf-8'):
            return {'changed': False, 'path': relative}
        path.parent.mkdir(parents=True, exist_ok=True)
        # Match batch writes and model evidence on every platform. Text mode's
        # implicit Windows newline translation used to change these bytes.
        path.write_bytes(content.encode('utf-8'))
        self.read_hashes[relative] = digest(path.read_bytes())
        return {'changed': True, 'path': relative}

    def read_many(self, paths: list[str]) -> list[dict]:
        if not isinstance(paths, list) or not 1 <= len(paths) <= 12:
            raise ValueError('Lee entre 1 y 12 archivos por lote')
        remembered = dict(self.read_hashes)
        try:
            result = [self.read(safe_relative(p)) for p in paths]
            if sum(len(row['content']) for row in result) > 24000:
                raise ValueError('El lote de lectura supera 24000 caracteres; divide la lectura')
            return result
        except (OSError, ValueError, TypeError):
            self.read_hashes = remembered
            raise

    def write_many(self, items: list[dict]) -> dict:
        from .mission_batch import write_many
        return write_many(self, items)

    def import_asset(self, relative: str, data: bytes, *, source_id: str = '') -> dict:
        """Importa un recurso binario validado dentro de la copia de trabajo.

        La biblioteca externa permanece read-only y nunca se sobreescribe un
        destino existente con contenido distinto.
        """
        from .external_resources import ASSET_SUFFIXES, MAX_RESOURCE_FILE
        relative = safe_relative(relative)
        path = self.path(relative)
        if Path(relative).suffix.casefold() not in ASSET_SUFFIXES:
            raise ValueError('Extension de recurso no permitida: ' + Path(relative).suffix)
        if not isinstance(data, (bytes, bytearray)) or len(data) > MAX_RESOURCE_FILE:
            raise ValueError('Recurso invalido o superior a 64 MB')
        if relative.casefold() in {p.casefold() for p in self.locked}:
            raise ValueError('Prueba inmutable: ' + relative)
        if path.exists():
            if not path.is_file():
                raise ValueError('La ruta de destino no es un archivo')
            if path.read_bytes() == bytes(data):
                return {'changed': False, 'path': relative, 'source': source_id}
            raise ValueError('El destino ya existe; importa el recurso con otro nombre')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(bytes(data))
        return {'changed': True, 'path': relative, 'source': source_id, 'bytes': len(data)}

    def fingerprint(self) -> str:
        return digest(json.dumps({p: digest(b) for p, b in project_files(self.root).items()},
                                 sort_keys=True).encode())

    def replace(self, relative: str, old: str, new: str) -> dict:
        path = self.path(relative)
        current = path.read_text(encoding='utf-8-sig')
        if not old or current.count(old) != 1:
            raise ValueError('El bloque original debe coincidir exactamente una vez')
        return self.write(relative, current.replace(old, new, 1))

    def freeze_tests(self, paths: list[str]) -> None:
        for relative in paths:
            relative = safe_relative(relative)
            path = self.path(relative)
            if not path.is_file() or not is_test(relative):
                raise ValueError('Falta la prueba requerida: ' + relative)
            self.locked[relative] = digest(path.read_bytes())

    def check_locked(self) -> None:
        for relative, expected in self.locked.items():
            path = self.path(relative)
            if not path.is_file() or digest(path.read_bytes()) != expected:
                raise ValueError('Se ha alterado una prueba protegida: ' + relative)

    def changes(self) -> tuple[list[str], str]:
        now = project_files(self.root)
        changed = [p for p, b in now.items() if self.before.get(p) != b]
        diff = []
        for p in changed:
            if Path(p).suffix.casefold() in TEXT_SUFFIXES:
                diff.extend(difflib.unified_diff(
                    self.before.get(p, b'').decode('utf-8-sig', errors='replace').splitlines(),
                    now[p].decode('utf-8-sig', errors='replace').splitlines(),
                    fromfile='a/' + p, tofile='b/' + p, lineterm=''))
        self.output.mkdir(parents=True, exist_ok=True)
        report = self.output / 'changes.diff'
        report.write_text('\n'.join(diff) + '\n', encoding='utf-8')
        return changed, str(report)
