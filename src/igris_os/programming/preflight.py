from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PreflightFinding:
    severity: str
    category: str
    path: str
    message: str
    evidence: str


@dataclass(frozen=True, slots=True)
class PreflightReport:
    root: str
    files: int
    python_files: int
    test_files: int
    findings: tuple[PreflightFinding, ...]
    truncated: bool = False

    @property
    def ok(self) -> bool:
        return not any(item.severity == "critical" for item in self.findings)


class ProgrammingPreflight:
    """Inspección estática de solo lectura antes de una tarea de programación."""

    _EXCLUDED = {".git", ".venv", "venv", "node_modules", "build", "dist",
                 "runtime", "__pycache__", ".pytest_cache", "target"}
    _DANGEROUS_CALLS = {"eval", "exec", "system", "popen"}

    def __init__(self, *, max_files: int = 2000,
                 max_file_bytes: int = 512_000) -> None:
        self.max_files = max_files
        self.max_file_bytes = max_file_bytes

    def inspect(self, root: Path) -> PreflightReport:
        project_root = root.resolve()
        if not project_root.is_dir() or project_root.is_symlink():
            raise ValueError("Proyecto no valido")
        findings: list[PreflightFinding] = []
        files = python_files = test_files = 0
        truncated = False
        for path in sorted(project_root.rglob("*")):
            if files >= self.max_files:
                truncated = True
                break
            if not path.is_file() or path.is_symlink():
                continue
            relative = path.relative_to(project_root)
            if any(part in self._EXCLUDED for part in relative.parts):
                continue
            if path.stat().st_size > self.max_file_bytes:
                findings.append(PreflightFinding(
                    "medium", "limit", relative.as_posix(),
                    "Archivo omitido por tamaño", str(path.stat().st_size)))
                continue
            files += 1
            if path.name.startswith("test_") or path.name.endswith("_test.py"):
                test_files += 1
            if path.suffix.casefold() != ".py":
                continue
            python_files += 1
            self._inspect_python(path, project_root, findings)
        if python_files and not test_files:
            findings.append(PreflightFinding(
                "medium", "quality", ".", "No se detectaron archivos de pruebas",
                "python_files=" + str(python_files)))
        return PreflightReport(str(project_root), files, python_files,
                               test_files, tuple(findings), truncated)

    def _inspect_python(self, path: Path, root: Path,
                        findings: list[PreflightFinding]) -> None:
        relative = path.relative_to(root).as_posix()
        source = path.read_text(encoding="utf-8-sig", errors="replace")
        try:
            tree = ast.parse(source, filename=relative)
        except SyntaxError as exc:
            findings.append(PreflightFinding(
                "critical", "syntax", relative, "SyntaxError detectado",
                f"linea={exc.lineno}: {exc.msg}"))
            return
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = self._call_name(node)
                is_builtin = isinstance(node.func, ast.Name)
                is_sensitive_method = (
                    isinstance(node.func, ast.Attribute)
                    and name in {"system", "popen"}
                )
                if (is_builtin and name in self._DANGEROUS_CALLS) or is_sensitive_method:
                    findings.append(PreflightFinding(
                        "high", "security", relative,
                        f"Llamada sensible detectada: {name}",
                        f"linea={node.lineno}"))

    @staticmethod
    def _call_name(node: ast.Call) -> str:
        function = node.func
        if isinstance(function, ast.Name):
            return function.id
        if isinstance(function, ast.Attribute):
            return function.attr
        return ""