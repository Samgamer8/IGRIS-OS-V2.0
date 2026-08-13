import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "assets/igris_icon_v2.ico",
    "assets/igris_window_art_only_1600.png",
    "src/igris_os/ui/cinematic.py",
    "src/igris_os/application/kernel.py",
    "src/igris_os/security/policy.py",
    "docs/SESSION_CONTINUITY.md",
)


def main() -> int:
    missing = [name for name in REQUIRED if not (ROOT / name).is_file()]
    damaged = []
    for path in (ROOT / "src").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if any(marker in text for marker in ("Ã", "Â", "â€¢", "â€”")):
            damaged.append(str(path.relative_to(ROOT)))
    state = json.loads((ROOT / "PROJECT_STATE.json").read_text(encoding="utf-8"))
    if missing or damaged or state.get("canonical_folder") != "IGRIS OS V2.O":
        print(json.dumps({"missing": missing, "encoding": damaged}, indent=2))
        return 1
    print("RELEASE CHECK: APROBADO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
