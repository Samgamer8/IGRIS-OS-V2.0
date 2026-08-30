from __future__ import annotations

import hashlib
import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = (
    "USER_GUIDE.md",
    "PRIVACY.md",
    "RELEASE_NOTES_5.0.0-RC1.md",
    "EXCLUDED_EXPERIMENTS.md",
    "COMMERCIAL_RELEASE.md",
)


def package(root: Path = ROOT) -> Path:
    bundle = root / "dist" / "IGRIS OS"
    executable = bundle / "IGRIS OS.exe"
    if not executable.is_file():
        raise FileNotFoundError("Falta el ejecutable portable")
    docs_target = bundle / "docs"
    docs_target.mkdir(parents=True, exist_ok=True)
    for name in DOCS:
        source = root / "docs" / name
        if not source.is_file():
            raise FileNotFoundError("Falta documentación: " + name)
        shutil.copy2(source, docs_target / name)
    seller = root / "release" / "SELLER.example.json"
    if not seller.is_file():
        raise FileNotFoundError("Falta SELLER.example.json")
    shutil.copy2(seller, bundle / "SELLER.example.json")
    manifest = bundle / "MANIFEST.sha256"
    files = sorted(
        path for path in bundle.rglob("*")
        if path.is_file() and path != manifest)
    lines = []
    for path in files:
        digest = hashlib.sha256(path.read_bytes()).hexdigest().upper()
        relative = path.relative_to(bundle).as_posix()
        lines.append(f"{digest}  {relative}")
    manifest.write_text("\n".join(lines) + "\n", encoding="ascii")
    archive = root / "dist" / "IGRIS OS RC1 Windows x64.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for path in sorted(bundle.rglob("*")):
            if path.is_file():
                output.write(path, (Path("IGRIS OS") /
                                     path.relative_to(bundle)).as_posix())
    return archive


def main() -> int:
    archive = package()
    digest = hashlib.sha256(archive.read_bytes()).hexdigest().upper()
    print(f"RC EMPAQUETADA: {archive}")
    print(f"SHA256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
