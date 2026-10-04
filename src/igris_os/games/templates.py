"""Bounded local discovery of version-matched Godot Windows export templates."""
from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import re
import shutil
import tempfile
import time
import zipfile

RELEASE = "windows_release_x86_64.exe"
DEBUG = "windows_debug_x86_64.exe"
MAX_TEMPLATE_BYTES = 512 * 1024 * 1024


def template_version(version: str) -> str:
    match = re.match(r"^(4\.\d+(?:\.\d+)?\.(?:stable|rc\d+|beta\d+|dev\d+)(?:\.mono)?)\b", version.strip())
    return match.group(1) if match else ""


def _version_file(path: Path) -> str:
    try:
        if path.stat().st_size > 256:
            return ""
        return path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return ""


def _is_pe(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return path.stat().st_size >= 64 and handle.read(2) == b"MZ"
    except OSError:
        return False


def inspect_tpz(path: Path, expected: str) -> dict | None:
    try:
        with zipfile.ZipFile(path) as archive:
            version = archive.getinfo("templates/version.txt")
            if version.file_size > 256:
                return None
            actual = archive.read(version).decode("utf-8").strip()
            member = archive.getinfo("templates/" + RELEASE)
            if not 64 <= member.file_size <= MAX_TEMPLATE_BYTES:
                return None
            with archive.open(member) as stream:
                if stream.read(2) != b"MZ":
                    return None
            return {"path": str(path), "version": actual,
                    "compatible": bool(expected and actual == expected)}
    except (OSError, ValueError, KeyError, UnicodeError, zipfile.BadZipFile):
        return None


def discover_templates(search_root: Path, executable: Path | None, version: str) -> dict:
    expected = template_version(version)
    root = Path(search_root).expanduser().resolve()
    roots = [root]
    appdata = os.environ.get("APPDATA")
    if appdata:
        roots.append(Path(appdata) / "Godot/export_templates")
    if os.name != "nt":
        roots.append(Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))) / "godot/export_templates")
    if executable:
        roots.append(Path(executable).parent / "editor_data/export_templates")
    directories, archives, searched = [], [], []
    diagnostics = []
    if not root.is_dir():
        diagnostics.append("La carpeta indicada no existe: " + str(root))
    seen = set()
    examined = 0
    deadline = time.monotonic() + 10
    truncated = False
    for base in roots:
        base = base.resolve()
        if base in seen or not base.is_dir():
            continue
        seen.add(base)
        searched.append(str(base))
        for current, dirs, files in os.walk(base, followlinks=False):
            dirs[:] = [d for d in dirs if d not in {".git", ".venv", "node_modules", "__pycache__", ".godot"}
                       and not (Path(current) / d).is_symlink()]
            examined += len(files) + len(dirs)
            if examined > 25000 or time.monotonic() > deadline:
                truncated = True
                break
            folder = Path(current)
            if RELEASE in files and _is_pe(folder / RELEASE):
                actual = _version_file(folder / "version.txt")
                if not actual:
                    actual = template_version(folder.name) or template_version(folder.parent.name)
                directories.append({"path": str(folder), "version": actual,
                                    "compatible": bool(expected and actual == expected)})
            for name in files:
                if name.casefold().endswith(".tpz"):
                    item = inspect_tpz(folder / name, expected)
                    if item:
                        archives.append(item)
        if truncated:
            break
    return {"expected_version": expected, "godot_version": version,
            "godot_executable": str(executable or ""), "searched": searched,
            "directories": directories, "archives": archives, "truncated": truncated,
            "diagnostics": diagnostics,
            "ready": any(item["compatible"] for item in directories + archives)}


@contextmanager
def prepared_templates(report: dict):
    """Reuse matching files or extract only the two Windows binaries from a TPZ."""
    directory = next((item for item in report["directories"] if item["compatible"]), None)
    if directory:
        yield Path(directory["path"])
        return
    package = next((item for item in report["archives"] if item["compatible"]), None)
    if package is None:
        raise ValueError("No se encontraron plantillas compatibles con " + report["expected_version"])
    # Temporary files are removed after export; no global installation or overwrite.
    with tempfile.TemporaryDirectory(prefix="igris-godot-templates-") as temporary:
        target = Path(temporary)
        with zipfile.ZipFile(package["path"]) as archive:
            for name in (RELEASE, DEBUG):
                try:
                    member = archive.getinfo("templates/" + name)
                except KeyError:
                    if name == DEBUG:
                        continue
                    raise ValueError("El paquete no contiene la plantilla Windows release")
                if not 64 <= member.file_size <= MAX_TEMPLATE_BYTES:
                    raise ValueError("Tamano de plantilla no permitido")
                with archive.open(member) as source, (target / name).open("wb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
                if not _is_pe(target / name):
                    raise ValueError("La plantilla Windows no tiene cabecera PE")
        yield target
