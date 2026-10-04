"""Install an official version-matched TPZ after capability approval."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import tempfile
import urllib.error
import urllib.request

from igris_os.games.templates import discover_templates, inspect_tpz, template_version


def install_templates(runtime, root: Path, *, on_progress=None, opener=None) -> dict:
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError("La carpeta de instalacion no existe: " + str(root))
    version = runtime.version()
    expected = template_version(version)
    if not re.fullmatch(r"4\.\d+(?:\.\d+)?\.stable", expected):
        raise ValueError("No se ha identificado una version estable de Godot 4 compatible: " + version)
    status = discover_templates(root, runtime.executable, version)
    if status["ready"]:
        return {"template_search": status, "downloaded": False}
    tag = expected.removesuffix(".stable") + "-stable"
    asset_name = f"Godot_v{tag}_export_templates.tpz"
    api = "https://api.github.com/repos/godotengine/godot-builds/releases/tags/" + tag
    opener = opener or urllib.request.build_opener()
    if on_progress:
        on_progress(5, "Consultando la publicacion oficial de Godot " + tag)
    request = urllib.request.Request(api, headers={"User-Agent": "IGRIS-OS", "Accept": "application/vnd.github+json"})
    try:
        with opener.open(request, timeout=30) as response:
            release = json.loads(response.read(4 * 1024 * 1024))
    except urllib.error.HTTPError as exc:
        raise ValueError(f"La consulta de Godot {tag} devolvio HTTP {exc.code}. "
                         "No se descargara otra version. Comprueba la version en el editor Godot.") from exc
    if not isinstance(release, dict) or release.get("tag_name") != tag:
        raise ValueError("La publicacion oficial no corresponde a la version instalada")
    asset = next((item for item in release.get("assets", [])
                  if isinstance(item, dict) and item.get("name") == asset_name), None)
    if asset is None:
        raise ValueError("La publicacion oficial no contiene " + asset_name)
    url = asset.get("browser_download_url", "")
    expected_url = "https://github.com/godotengine/godot-builds/releases/download/" + tag + "/" + asset_name
    digest = str(asset.get("digest", ""))
    if url != expected_url or not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", digest):
        raise ValueError("No hay URL oficial y hash SHA-256 verificable para este paquete")
    size = asset.get("size", 0)
    if not isinstance(size, int) or not 1 <= size <= 2 * 1024**3:
        raise ValueError("Tamano del paquete oficial fuera del limite permitido")
    destination = root / ".tools" / "export_templates"
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / asset_name
    if target.exists():
        raise ValueError("Ya existe un paquete no compatible o no verificable; se conserva: " + str(target))
    with tempfile.TemporaryDirectory(prefix="download-", dir=destination) as temporary:
        partial = Path(temporary) / asset_name
        sha = hashlib.sha256()
        received = 0
        last_progress = -1
        with opener.open(urllib.request.Request(url, headers={"User-Agent": "IGRIS-OS"}), timeout=30) as response, partial.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                received += len(chunk)
                if received > size:
                    raise ValueError("La descarga excede el tamano anunciado")
                sha.update(chunk)
                output.write(chunk)
                progress = 10 + int(80 * received / size)
                if on_progress and progress != last_progress:
                    on_progress(progress, f"Descargando plantillas: {received // 1048576}/{size // 1048576} MB")
                    last_progress = progress
        if received != size or sha.hexdigest().lower() != digest[7:].lower():
            raise ValueError("La descarga no coincide con el tamano y hash oficiales")
        package = inspect_tpz(partial, expected)
        if not package or not package["compatible"]:
            raise ValueError("El contenido del paquete no corresponde a Godot " + expected)
        # Exclusive creation avoids replacing a file installed concurrently.
        try:
            with target.open("xb") as output, partial.open("rb") as source:
                import shutil
                shutil.copyfileobj(source, output, length=1024 * 1024)
        except FileExistsError:
            raise ValueError("Otro proceso creo el paquete durante la descarga; se conserva")
    if on_progress:
        on_progress(100, "Plantillas descargadas y verificadas")
    return {"downloaded": True, "output": str(target), "sha256": sha.hexdigest(),
            "template_search": discover_templates(root, runtime.executable, version)}
