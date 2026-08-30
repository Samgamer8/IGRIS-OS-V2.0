import json
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "assets/igris_icon_v2.ico",
    "assets/igris_window_art_only_1600.png",
    "src/igris_os/ui/cinematic.py",
    "src/igris_os/application/kernel.py",
    "src/igris_os/security/policy.py",
    "README.md",
    "VERSION",
)


def main() -> int:
    missing = [name for name in REQUIRED if not (ROOT / name).is_file()]
    damaged = []
    for path in (ROOT / "src").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if any(marker in text for marker in ("Ã", "Â", "â€¢", "â€”")):
            damaged.append(str(path.relative_to(ROOT)))
    version = (ROOT / "VERSION").read_text(encoding="ascii").strip()
    metadata = tomllib.loads(
        (ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    declared = metadata["project"]["version"]
    inconsistent = version != declared
    if missing or damaged or inconsistent:
        print(json.dumps(
            {"missing": missing, "encoding": damaged,
             "version": version, "declared_version": declared,
             "version_inconsistent": inconsistent},
            indent=2))
        return 1
    print("RELEASE CHECK: APROBADO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
