"""Auditor reproducible de limpieza para la Release Candidate de IGRIS OS."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IGNORED_DIRS = {".git", ".venv", "build", "dist", "runtime", "__pycache__"}


def python_files(root: Path = ROOT) -> list[Path]:
    return sorted(
        path for path in root.rglob("*.py")
        if not any(part in IGNORED_DIRS for part in path.relative_to(root).parts)
    )


def executable_placeholders(tree: ast.AST, path: Path) -> list[dict[str, object]]:
    """Detecta funciones de produccion cuyo unico cuerpo ejecutable es ``pass``."""
    if "src" not in path.parts:
        return []
    findings: list[dict[str, object]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        statements = [item for item in node.body
                      if not (isinstance(item, ast.Expr)
                              and isinstance(item.value, ast.Constant)
                              and isinstance(item.value.value, str))]
        if len(statements) == 1 and isinstance(statements[0], ast.Pass):
            findings.append({"file": str(path.relative_to(ROOT)),
                             "line": node.lineno, "symbol": node.name})
    return findings


def inspect(root: Path = ROOT) -> dict[str, object]:
    syntax_errors: list[dict[str, object]] = []
    placeholders: list[dict[str, object]] = []
    files = python_files(root)
    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        except (OSError, UnicodeError, SyntaxError) as exc:
            syntax_errors.append({"file": str(path.relative_to(root)),
                                  "error": str(exc)})
            continue
        placeholders.extend(executable_placeholders(tree, path))
    temporary = sorted(
        str(path.relative_to(root)) for path in (root / "src" / "igris_os").rglob("*")
        if path.is_file() and path.suffix in {".pyc", ".pyo", ".tmp", ".bak", ".orig"}
    )
    return {
        "python_files_checked": len(files),
        "ast_errors": syntax_errors,
        "executable_placeholders": placeholders,
        "temporary_artifacts": temporary,
        "passed": not syntax_errors and not placeholders and not temporary,
    }


def main() -> int:
    report = inspect()
    target = ROOT / "runtime" / "audit" / "phase4_audit.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
