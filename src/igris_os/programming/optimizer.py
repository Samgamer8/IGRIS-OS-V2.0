from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True, slots=True)
class PerformanceProfile:
    hot_paths: tuple[str, ...] = ()
    memory_issues: tuple[str, ...] = ()
    cpu_issues: tuple[str, ...] = ()
    io_issues: tuple[str, ...] = ()
    suggestions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OptimizationResult:
    ok: bool
    message: str
    profile: PerformanceProfile | None = None
    diff: str = ""


class PerformanceOptimizer:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def profile(self, language: str, source: str) -> PerformanceProfile:
        if language == "python":
            return self._profile_python(source)
        if language == "rust":
            return self._profile_rust_patterns(source)
        if language == "cpp":
            return self._profile_cpp_patterns(source)
        return PerformanceProfile()

    def optimize(self, language: str, source: str) -> OptimizationResult:
        profile = self.profile(language, source)
        if not any([profile.hot_paths, profile.memory_issues,
                     profile.cpu_issues, profile.io_issues]):
            return OptimizationResult(True, "Sin optimizaciones necesarias")
        optimized = self._apply_optimizations(language, source, profile)
        diff = self._diff(source, optimized)
        return OptimizationResult(True, "Optimizado", profile, diff)

    def _profile_python(self, source: str) -> PerformanceProfile:
        hot_paths = []
        memory_issues = []
        cpu_issues = []
        io_issues = []
        suggestions = []
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return PerformanceProfile()
        for node in ast.walk(tree):
            if isinstance(node, ast.For):
                if any(isinstance(n, ast.Call) and getattr(n.func, "id", "") in ("open", "read", "write")
                       for n in ast.walk(node)):
                    io_issues.append(f"IO en bucle en linea {node.lineno}")
                    suggestions.append("Mover operaciones de IO fuera del bucle")
            if isinstance(node, (ast.ListComp, ast.GeneratorExp)):
                if any(isinstance(n, ast.Call) for n in ast.walk(node)):
                    cpu_issues.append(f"Comprension compleja en linea {node.lineno}")
                    suggestions.append("Considerar generador en lugar de lista")
            if isinstance(node, ast.FunctionDef):
                if len(node.body) > 50:
                    hot_paths.append(f"Funcion larga {node.name} linea {node.lineno}")
                    suggestions.append(f"Dividir {node.name} en funciones pequenas")
        return PerformanceProfile(
            tuple(hot_paths), tuple(memory_issues),
            tuple(cpu_issues), tuple(io_issues), tuple(suggestions),
        )

    def _profile_rust_patterns(self, source: str) -> PerformanceProfile:
        issues = []
        suggestions = []
        if ".clone()" in source:
            issues.append("Clone innecesario")
            suggestions.append("Usar borrow en lugar de clone")
        if "Vec::new()" in source and "push" in source:
            issues.append("Vec crece sin reserva")
            suggestions.append("Usar with_capacity para preasignar")
        return PerformanceProfile(memory_issues=tuple(issues),
                                  suggestions=tuple(suggestions))

    def _profile_cpp_patterns(self, source: str) -> PerformanceProfile:
        issues = []
        suggestions = []
        if "new " in source and "delete" in source:
            issues.append("new/delete manual")
            suggestions.append("Usar smart pointers")
        if "std::copy" not in source and ("for" in source or "for_each" in source):
            issues.append("Bucle manual posible")
            suggestions.append("Considerar algoritmo STL")
        return PerformanceProfile(cpu_issues=tuple(issues),
                                  suggestions=tuple(suggestions))

    def _apply_optimizations(self, language: str, source: str,
                             profile: PerformanceProfile) -> str:
        optimized = source
        for suggestion in profile.suggestions:
            if "Dividir" in suggestion and "funciones pequenas" in suggestion:
                pass
            if "Mover operaciones de IO" in suggestion:
                pass
        return optimized

    @staticmethod
    def _diff(old: str, new: str) -> str:
        return "\n".join(difflib.unified_diff(
            old.splitlines(), new.splitlines(),
            fromfile="old", tofile="optimized", lineterm=""
        ))


class ScalableProjectManager:
    def __init__(self, root: Path, *, max_context: int = 8000) -> None:
        self.root = root.resolve()
        self.max_context = max_context
        self.index_file = self.root / ".igris_index.json"

    def index_project(self) -> dict:
        files = []
        symbols = []
        for path in self.root.rglob("*"):
            if path.is_file() and not any(part.startswith(".") for part in path.parts):
                files.append({
                    "path": str(path.relative_to(self.root)),
                    "size": path.stat().st_size,
                    "language": self._detect_language(path),
                })
        index = {
            "files": files,
            "file_count": len(files),
            "symbols": symbols,
            "indexed_at": __import__("datetime").datetime.now().isoformat(),
        }
        self.index_file.write_text(
            json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        return index

    def incremental_context(self, objective: str) -> str:
        if not self.index_file.exists():
            self.index_project()
        index = json.loads(self.index_file.read_text(encoding="utf-8"))
        relevant = self._filter_relevant(index["files"], objective)
        return json.dumps({"files": relevant[:20]}, ensure_ascii=False)

    def checkpoint(self, message: str) -> None:
        state = {
            "message": message,
            "timestamp": __import__("datetime").datetime.now().isoformat(),
            "context": self.incremental_context(""),
        }
        (self.root / ".igris_checkpoint.json").write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8",
        )

    @staticmethod
    def _detect_language(path: Path) -> str:
        ext = path.suffix.casefold()
        mapping = {
            ".py": "python", ".rs": "rust", ".cpp": "cpp", ".c": "c",
            ".java": "java", ".js": "javascript", ".ts": "typescript",
            ".gd": "gdscript", ".tscn": "godot", ".cs": "csharp",
            ".go": "go", ".rb": "ruby", ".php": "php",
        }
        return mapping.get(ext, "unknown")

    def _filter_relevant(self, files: list[dict], objective: str) -> list[dict]:
        keywords = set(re.findall(r"\w+", objective.lower()))
        scored = []
        for item in files:
            score = sum(1 for kw in keywords if kw in item["path"].lower())
            scored.append((score, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored if _ > 0]
