from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from igris_os.production_bootstrap import EXPERIMENTAL_CAPABILITIES, build_production_igris
from tools.package_production_rc import DOCS


ROOT = Path(__file__).resolve().parents[1]


def inspect(root: Path = ROOT) -> dict:
    errors: list[str] = []
    bundle = root / "dist" / "IGRIS OS RC1"
    executable = bundle / "IGRIS OS RC1.exe"
    sums = bundle / "SHA256SUMS.txt"
    if not executable.is_file() or not sums.is_file():
        errors.append("Falta EXE RC o SHA256SUMS.txt")
    else:
        expected = sums.read_text(encoding="ascii").split()[0].upper()
        actual = hashlib.sha256(executable.read_bytes()).hexdigest().upper()
        if expected != actual:
            errors.append("Hash del EXE RC inválido")
    for name in DOCS:
        if not (bundle / "docs" / name).is_file():
            errors.append("Documento no empaquetado: " + name)
    kernel = build_production_igris(root / "runtime" / "rc_check")
    names = {spec.name for spec in kernel.registry.specs()}
    leaked = sorted(names & EXPERIMENTAL_CAPABILITIES)
    if leaked:
        errors.append("Capacidades experimentales expuestas: " + ", ".join(leaked))
    technical_ready = not errors
    seller = root / "release" / "SELLER.json"
    commercial_errors: list[str] = []
    if not seller.is_file():
        commercial_errors.append("Falta release/SELLER.json")
    else:
        try:
            data = json.loads(seller.read_text(encoding="utf-8"))
            for key in ("legal_name", "support_email", "jurisdiction"):
                if not str(data.get(key, "")).strip():
                    commercial_errors.append("Dato comercial vacío: " + key)
        except (OSError, ValueError, TypeError):
            commercial_errors.append("SELLER.json inválido")
    return {
        "technical_ready": technical_ready,
        "commercial_ready": technical_ready and not commercial_errors,
        "capability_count": len(names),
        "errors": errors + commercial_errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--technical", action="store_true")
    args = parser.parse_args()
    result = inspect()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    ready = result["technical_ready"] if args.technical else result["commercial_ready"]
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
