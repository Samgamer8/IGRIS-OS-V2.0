"""Copias de trabajo y publicacion de cambios con respaldo y deteccion de conflictos."""
import hashlib
import os
from pathlib import Path
import shutil
import tempfile

EXCLUDED = {".godot", ".git", "__pycache__"}


def snapshot(root):
    root = Path(root).resolve()
    result, size = {}, 0
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if d not in EXCLUDED]
        for name in dirs + files:
            p = Path(directory) / name
            if p.is_symlink() or getattr(p, "is_junction", lambda: False)():
                raise ValueError("El proyecto contiene un enlace; revisa su destino antes de reanudar: " + str(p))
        for name in files:
            p = Path(directory) / name
            size += p.stat().st_size
            if size > 512 * 1024 * 1024 or len(result) >= 5000:
                raise ValueError("El proyecto supera el limite de copia (512 MiB / 5000 archivos)")
            with p.open("rb") as stream:
                result[p.relative_to(root).as_posix()] = hashlib.file_digest(stream, "sha256").hexdigest()
    return result


def clone_project(source, target):
    source, target = Path(source).resolve(), Path(target).resolve()
    if not (source / "project.godot").is_file():
        raise ValueError("No existe project.godot en " + str(source))
    if target.is_relative_to(source) or source.is_relative_to(target):
        raise ValueError("La copia de trabajo debe estar fuera del proyecto original")
    before = snapshot(source)
    target.mkdir(parents=True, exist_ok=False)
    for name in before:
        dest = target / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / name, dest)
    if snapshot(source) != before or snapshot(target) != before:
        raise ValueError("El proyecto cambio durante la copia; no se inicia la generacion")
    return before


def publish_changes(source, destination, expected, backup):
    source, destination, backup = map(lambda p: Path(p).resolve(), (source, destination, backup))
    if snapshot(destination) != expected:
        raise ValueError("La carpeta de entrega cambio mientras IGRIS trabajaba. Se conserva la copia verificada sin sobrescribir tus cambios.")
    current = snapshot(source)
    changed = sorted(name for name, digest in current.items() if expected.get(name) != digest)
    backup.mkdir(parents=True, exist_ok=False)
    applied = []
    try:
        for name in changed:
            dest = destination / name
            if name in expected:
                old = backup / name
                old.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dest, old)
            dest.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=dest.parent, prefix="igris-publish-", delete=False) as tmp:
                temporary = Path(tmp.name)
            try:
                shutil.copy2(source / name, temporary)
                os.replace(temporary, dest)
                applied.append(name)
            finally:
                temporary.unlink(missing_ok=True)
    except OSError:
        for name in reversed(applied):
            dest = destination / name
            if name in expected:
                shutil.copy2(backup / name, dest)
            else:
                dest.unlink(missing_ok=True)
        raise
    return changed
