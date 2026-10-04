"""Bibliotecas externas de recursos para misiones de programacion.

Las carpetas se tratan como fuentes de solo lectura. El modelo nunca recibe una
ruta arbitraria para escribir fuera del workspace: solo puede listar, inspeccionar
metadatos acotados y copiar recursos permitidos a la copia de trabajo.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import struct
import wave

from .mission_workspace import EXCLUDED, safe_relative

ASSET_SUFFIXES = {
    '.glb', '.gltf', '.obj', '.fbx', '.dae', '.stl', '.blend',
    '.png', '.jpg', '.jpeg', '.webp', '.svg', '.bmp', '.tga',
    '.wav', '.ogg', '.mp3', '.flac', '.mtl', '.material', '.tres', '.bin',
}
REFERENCE_SUFFIXES = {'.skp'}
MAX_RESOURCE_FILE = 64 * 1024**2
MAX_LISTED = 2500
MAX_TOTAL_METADATA_BYTES = 2 * 1024**3


def _is_link(path: Path) -> bool:
    return path.is_symlink() or getattr(path, 'is_junction', lambda: False)()


class ExternalResourceLibrary:
    """Vista segura y read-only sobre hasta cuatro carpetas externas."""

    def __init__(self, roots=()):
        cleaned = []
        seen = set()
        for raw in roots or ():
            if len(cleaned) >= 4:
                break
            path = Path(str(raw)).expanduser()
            if not path.is_dir() or _is_link(path):
                continue
            resolved = path.resolve()
            key = os.path.normcase(str(resolved))
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(resolved)
        self.roots = tuple(cleaned)

    @property
    def available(self) -> bool:
        return bool(self.roots)

    def _iter(self):
        count = 0
        total = 0
        for index, root in enumerate(self.roots, 1):
            for folder, dirs, files in os.walk(root, followlinks=False):
                dirs[:] = sorted(d for d in dirs if d.casefold() not in EXCLUDED)
                base = Path(folder)
                safe_dirs = []
                for dirname in dirs:
                    candidate = base / dirname
                    if not _is_link(candidate):
                        safe_dirs.append(dirname)
                dirs[:] = safe_dirs
                for name in sorted(files):
                    path = base / name
                    if _is_link(path) or not path.is_file():
                        continue
                    try:
                        relative = path.relative_to(root).as_posix()
                        safe_relative(relative)
                        size = path.stat().st_size
                    except (OSError, ValueError):
                        continue
                    count += 1
                    total += size
                    if count > MAX_LISTED or total > MAX_TOTAL_METADATA_BYTES:
                        return
                    suffix = path.suffix.casefold()
                    yield {
                        'id': f'r{index}/{relative}',
                        'root': f'r{index}',
                        'path': relative,
                        'bytes': size,
                        'suffix': suffix,
                        'usable_asset': suffix in ASSET_SUFFIXES and size <= MAX_RESOURCE_FILE,
                        'reference_asset': suffix in REFERENCE_SUFFIXES and size <= MAX_RESOURCE_FILE,
                    }

    def listing(self, query: str = '', limit: int = 500):
        needle = str(query or '').casefold().strip()
        result = []
        for item in self._iter():
            if needle and needle not in item['path'].casefold():
                continue
            result.append(item)
            if len(result) >= max(1, min(1000, int(limit))):
                break
        return result

    def roots_summary(self):
        return [{'id': f'r{i}', 'path': str(root)} for i, root in enumerate(self.roots, 1)]

    def _resolve(self, resource_id: str) -> tuple[Path, str]:
        value = str(resource_id).replace('\\', '/').strip()
        if '/' not in value or not value.startswith('r'):
            raise ValueError('Recurso invalido; usa un id devuelto por list_resources')
        head, relative = value.split('/', 1)
        try:
            index = int(head[1:]) - 1
        except ValueError as exc:
            raise ValueError('Recurso invalido') from exc
        if index < 0 or index >= len(self.roots):
            raise ValueError('Biblioteca de recursos inexistente')
        relative = safe_relative(relative)
        root = self.roots[index]
        path = root / relative
        if not path.is_file() or _is_link(path) or not path.resolve().is_relative_to(root):
            raise ValueError('El recurso no existe o sale de la biblioteca')
        if path.stat().st_size > MAX_RESOURCE_FILE:
            raise ValueError('El recurso supera 64 MB')
        return path, relative

    def inspect(self, resource_id: str) -> dict:
        path, relative = self._resolve(resource_id)
        suffix = path.suffix.casefold()
        size = path.stat().st_size
        result = {'id': resource_id, 'path': relative, 'bytes': size,
                  'suffix': suffix, 'usable_asset': suffix in ASSET_SUFFIXES,
                  'reference_asset': suffix in REFERENCE_SUFFIXES}
        try:
            if suffix == '.png':
                data = path.read_bytes()[:24]
                if len(data) >= 24 and data[:8] == b'\x89PNG\r\n\x1a\n':
                    result['image'] = {'width': struct.unpack('>I', data[16:20])[0],
                                       'height': struct.unpack('>I', data[20:24])[0]}
            elif suffix == '.wav':
                with wave.open(str(path), 'rb') as wav:
                    result['audio'] = {'channels': wav.getnchannels(), 'sample_rate': wav.getframerate(),
                                       'frames': wav.getnframes(),
                                       'duration_seconds': round(wav.getnframes() / max(1, wav.getframerate()), 3)}
            elif suffix == '.skp':
                header = path.read_bytes()[:96]
                printable = ''.join(chr(b) if 32 <= b < 127 else ' ' for b in header)
                result['model'] = {
                    'format': 'skp',
                    'direct_godot_import': False,
                    'role': 'visual_reference',
                    'header_hint': ' '.join(printable.split())[:80],
                    'conversion_required': 'Convertir/exportar a GLB/GLTF antes de usarlo como malla de Godot',
                }
            elif suffix == '.obj':
                vertices = faces = objects = 0
                with path.open('r', encoding='utf-8', errors='ignore') as handle:
                    for line in handle:
                        if line.startswith('v '): vertices += 1
                        elif line.startswith('f '): faces += 1
                        elif line.startswith(('o ', 'g ')): objects += 1
                result['model'] = {'format': 'obj', 'vertices': vertices, 'faces': faces,
                                   'objects_or_groups': objects}
            elif suffix in {'.gltf', '.glb'}:
                document = self._gltf_json(path, suffix)
                if document:
                    result['model'] = {
                        'format': suffix[1:],
                        'scenes': len(document.get('scenes', [])),
                        'nodes': len(document.get('nodes', [])),
                        'meshes': len(document.get('meshes', [])),
                        'materials': len(document.get('materials', [])),
                        'animations': len(document.get('animations', [])),
                        'mesh_names': [str(x.get('name', '')) for x in document.get('meshes', [])[:20]
                                       if isinstance(x, dict) and x.get('name')],
                    }
        except (OSError, ValueError, json.JSONDecodeError, wave.Error, struct.error):
            result['metadata_warning'] = 'No se pudieron extraer metadatos avanzados; el archivo sigue disponible.'
        return result

    @staticmethod
    def _gltf_json(path: Path, suffix: str):
        if suffix == '.gltf':
            if path.stat().st_size > 8 * 1024**2:
                return None
            return json.loads(path.read_text(encoding='utf-8-sig'))
        with path.open('rb') as handle:
            header = handle.read(12)
            if len(header) != 12 or header[:4] != b'glTF':
                return None
            _magic, version, _length = struct.unpack('<4sII', header)
            if version != 2:
                return None
            chunk_header = handle.read(8)
            if len(chunk_header) != 8:
                return None
            chunk_length, chunk_type = struct.unpack('<II', chunk_header)
            if chunk_type != 0x4E4F534A or chunk_length > 8 * 1024**2:
                return None
            payload = handle.read(chunk_length).rstrip(b'\x00 \t\r\n')
            return json.loads(payload.decode('utf-8'))

    def copy_to_project(self, resource_id: str, destination: str, files) -> dict:
        path, _relative = self._resolve(resource_id)
        suffix = path.suffix.casefold()
        if suffix not in ASSET_SUFFIXES:
            raise ValueError('Formato no permitido como recurso de proyecto: ' + suffix)
        return files.import_asset(destination, path.read_bytes(), source_id=resource_id)
