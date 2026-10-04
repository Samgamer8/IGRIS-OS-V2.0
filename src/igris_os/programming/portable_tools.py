"""Instalacion portable de Godot desde su publicacion oficial con digest obligatorio."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import re
import tempfile
import time
import sys
import urllib.request
import zipfile


def install_godot(destination: Path, *, opener=None) -> dict:
    if platform.machine().casefold() not in {'amd64', 'x86_64'} or sys.platform not in {'win32', 'linux'}:
        raise ValueError('No hay un paquete portable compatible con este sistema')
    opener = opener or urllib.request.build_opener()
    api = 'https://api.github.com/repos/godotengine/godot-builds/releases/latest'
    with opener.open(urllib.request.Request(api, headers={'User-Agent': 'IGRIS-OS'}), timeout=30) as response:
        release = json.loads(response.read(4 * 1024**2))
    tag = str(release.get('tag_name', ''))
    if not re.fullmatch(r'4\.\d+(?:\.\d+)?-stable', tag):
        raise ValueError('La publicacion no es una version estable compatible de Godot 4')
    platform_name = 'win64.exe' if os.name == 'nt' else 'linux.x86_64'
    name = f'Godot_v{tag}_{platform_name}.zip'
    asset = next((a for a in release.get('assets', []) if a.get('name') == name), {})
    url = f'https://github.com/godotengine/godot-builds/releases/download/{tag}/{name}'
    digest = str(asset.get('digest', ''))
    size = asset.get('size', 0)
    if (asset.get('browser_download_url') != url or
            not re.fullmatch(r'sha256:[0-9a-fA-F]{64}', digest) or
            not isinstance(size, int) or not 0 < size <= 256 * 1024**2):
        raise ValueError('No hay un paquete oficial con tamano y SHA-256 verificables')
    destination = Path(destination).resolve()
    target = destination / name.removesuffix('.zip')
    if target.exists():
        raise ValueError('Ya existe una herramienta en el destino; se conserva')
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination) as temporary:
        archive = Path(temporary) / 'godot.zip'
        sha, received, deadline = hashlib.sha256(), 0, time.monotonic() + 300
        with opener.open(urllib.request.Request(url, headers={'User-Agent': 'IGRIS-OS'}), timeout=30) as response, archive.open('wb') as output:
            while chunk := response.read(1024 * 1024):
                received += len(chunk)
                if received > size or time.monotonic() > deadline:
                    raise ValueError('La descarga supero su limite de tamano o tiempo')
                sha.update(chunk)
                output.write(chunk)
        if received != size or sha.hexdigest().lower() != digest[7:].lower():
            raise ValueError('El paquete no coincide con su SHA-256 oficial')
        with zipfile.ZipFile(archive) as bundle:
            executable = name.removesuffix('.zip')
            member = bundle.getinfo(executable)
            if member.file_size > 512 * 1024**2 or member.is_dir():
                raise ValueError('Contenido de Godot fuera de limites')
            data = bundle.read(member)
        with target.open('xb') as output:
            output.write(data)
        if os.name != 'nt':
            target.chmod(0o700)
    return {'ok': True, 'path': str(target), 'source': url,
            'archive_sha256': sha.hexdigest(), 'sha256': hashlib.sha256(data).hexdigest()}
