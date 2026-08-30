from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_DOCS = (
    "docs/USER_GUIDE.md",
    "docs/PRIVACY.md",
    "docs/RELEASE_NOTES_5.0.0-RC1.md",
    "docs/EXCLUDED_EXPERIMENTS.md",
    "docs/COMMERCIAL_RELEASE.md",
)


@dataclass(frozen=True, slots=True)
class ReleaseReadiness:
    technical_ready: bool
    commercial_ready: bool
    errors: tuple[str, ...]


def inspect(root: Path = ROOT) -> ReleaseReadiness:
    errors: list[str] = []
    for relative in REQUIRED_DOCS:
        if not (root / relative).is_file():
            errors.append("Falta documentación: " + relative)
    bundle = root / "dist" / "IGRIS OS"
    executable = bundle / "IGRIS OS.exe"
    sums = bundle / "SHA256SUMS.txt"
    if not executable.is_file():
        errors.append("Falta el ejecutable portable")
    if not sums.is_file():
        errors.append("Falta SHA256SUMS.txt")
    if executable.is_file() and sums.is_file():
        expected = sums.read_text(encoding="ascii", errors="replace").split()[0]
        actual = hashlib.sha256(executable.read_bytes()).hexdigest().upper()
        if expected.upper() != actual:
            errors.append("El SHA-256 del ejecutable no coincide")
    technical_errors = tuple(errors)
    seller = root / "release" / "SELLER.json"
    if not seller.is_file():
        errors.append("Falta release/SELLER.json")
    else:
        try:
            data = json.loads(seller.read_text(encoding="utf-8"))
            for key in ("legal_name", "support_email", "jurisdiction"):
                if not str(data.get(key, "")).strip():
                    errors.append("Dato comercial vacío: " + key)
            email = str(data.get("support_email", ""))
            if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
                errors.append("Correo de soporte inválido")
        except (OSError, ValueError, TypeError):
            errors.append("release/SELLER.json no es JSON válido")
    return ReleaseReadiness(
        not technical_errors,
        not errors,
        tuple(errors),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--technical", action="store_true")
    args = parser.parse_args()
    result = inspect()
    payload = {
        "technical_ready": result.technical_ready,
        "commercial_ready": result.commercial_ready,
        "errors": result.errors,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if (result.technical_ready if args.technical else result.commercial_ready) else 1


if __name__ == "__main__":
    raise SystemExit(main())
