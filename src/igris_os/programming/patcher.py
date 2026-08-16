from __future__ import annotations

import ast
import difflib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True, slots=True)
class PatchResult:
    ok: bool
    message: str
    patch: str = ""
    applied_files: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = field(default_factory=tuple)


class SurgicalPatcher:
    REPAIR_SYSTEM = (
        "Eres ingeniero senior de parches quirurgicos. "
        "Analiza el codigo y el error. Devuelve SOLO JSON con el parche minimo: "
        '{"operation":"replace|insert|delete","path":"ruta","start_line":1,'
        '"end_line":2,"content":"nuevo codigo","explanation":"cambio"}. '
        "Sin markdown."
    )

    def __init__(self, root: Path, *, timeout: int = 30) -> None:
        self.root = root.resolve()
        self.timeout = timeout

    def apply_patch(self, target: Path, operation: str,
                    start_line: int, end_line: int,
                    content: str) -> PatchResult:
        if not target.is_relative_to(self.root):
            return PatchResult(False, "Ruta fuera del workspace")
        if not target.exists():
            return PatchResult(False, "Archivo no existe")
        original = target.read_text(encoding="utf-8", errors="replace").splitlines()
        if start_line < 1 or end_line > len(original):
            return PatchResult(False, "Lineas fuera de rango")
        new_lines = list(original)
        if operation == "replace":
            new_lines[start_line - 1:end_line] = content.splitlines()
        elif operation == "insert":
            new_lines[start_line - 1:start_line - 1] = content.splitlines()
        elif operation == "delete":
            del new_lines[start_line - 1:end_line]
        else:
            return PatchResult(False, f"Operacion desconocida: {operation}")
        new_content = "\n".join(new_lines)
        if not new_content.endswith("\n"):
            new_content += "\n"
        try:
            ast.parse(new_content)
        except SyntaxError as exc:
            return PatchResult(False, f"Parche invalido: SyntaxError {exc}")
        patch = "\n".join(difflib.unified_diff(
            original, new_content.splitlines(),
            fromfile=str(target), tofile=str(target),
            lineterm=""
        ))
        target.write_text(new_content, encoding="utf-8")
        return PatchResult(True, "Parche aplicado", patch, (str(target),))

    def repair_with_patch(self, target: Path, diagnostics: str,
                          client, model: str,
                          max_attempts: int = 3) -> PatchResult:
        for attempt in range(1, max_attempts + 1):
            prompt = (
                self.REPAIR_SYSTEM +
                "\nARCHIVO:\n" + target.read_text(encoding="utf-8", errors="replace") +
                "\nDIAGNOSTICO:\n" + diagnostics[:3000] +
                "\n\nDevuelve el parque JSON."
            )
            reply = client.generate(prompt, model)
            if not reply.ok:
                continue
            try:
                cleaned = re.sub(r"^\s*```(?:json)?|```\s*$", "", reply.text,
                                 flags=re.IGNORECASE | re.MULTILINE).strip()
                data = json.loads(cleaned, strict=False)
                result = self.apply_patch(
                    target=Path(str(data.get("path", target))),
                    operation=str(data.get("operation", "replace")),
                    start_line=int(data.get("start_line", 1)),
                    end_line=int(data.get("end_line", 1)),
                    content=str(data.get("content", "")),
                )
                if result.ok:
                    return PatchResult(
                        True, f"Reparado en intento {attempt}",
                        result.patch, result.applied_files,
                        (data.get("explanation", ""),))
                return PatchResult(False, f"Parche invalido: {result.message}",
                                   diagnostics=(result.message,))
            except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
                continue
        return PatchResult(False, "No se pudo reparar",
                           diagnostics=("max_attempts_reached",))

    def generate_ast_diff(self, old: str, new: str) -> str:
        try:
            old_tree = ast.dump(ast.parse(old), indent=2)
            new_tree = ast.dump(ast.parse(new), indent=2)
            return "\n".join(difflib.unified_diff(
                old_tree.splitlines(), new_tree.splitlines(),
                fromfile="old_ast", tofile="new_ast",
                lineterm=""
            ))
        except SyntaxError:
            return "\n".join(difflib.unified_diff(
                old.splitlines(), new.splitlines(),
                fromfile="old", tofile="new",
                lineterm=""
            ))


class AdvancedDebugger:
    CRASH_PATTERNS: dict[str, str] = {
        r"Segmentation fault|SIGSEGV|access violation": "memory_access_violation",
        r"Stack overflow|stack exhaustion": "stack_overflow",
        r"Out of memory|OOM|MemoryError": "out_of_memory",
        r"NullPointerException|NoneType": "null_pointer",
        r"IndexError|IndexOutOfRangeException|out of range": "index_out_of_range",
        r"KeyError|KeyNotFound": "key_not_found",
        r"TypeError|type mismatch": "type_mismatch",
        r"ImportError|ModuleNotFoundError|No module named": "missing_dependency",
        r"PermissionError|EACCES|access denied": "permission_denied",
        r"FileNotFoundError|No such file or directory": "file_not_found",
        r"ConnectionError|timeout|ECONNREFUSED": "connection_failure",
        r"Deadlock|livelock|starvation": "deadlock",
        r"Floating point exception|division by zero": "division_by_zero",
    }

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def analyze_crash(self, stderr: str, stdout: str = "") -> dict:
        combined = stderr + "\n" + stdout
        patterns_found = []
        for pattern, category in self.CRASH_PATTERNS.items():
            if re.search(pattern, combined, re.IGNORECASE):
                patterns_found.append(category)
        if not patterns_found:
            patterns_found.append("unknown")
        return {
            "categories": patterns_found,
            "root_cause": self._guess_root_cause(patterns_found, combined),
            "suggested_fix": self._suggest_fix(patterns_found),
            "severity": self._severity(patterns_found),
        }

    def analyze_memory(self, output: str) -> dict:
        leaks = []
        if "memory leak" in output.lower() or "leaked" in output.lower():
            leaks.append("potential_leak")
        if "OOM" in output or "OutOfMemory" in output:
            leaks.append("oom_risk")
        return {"leaks": leaks, "recommendation": "profile_with_valgrind" if leaks else "ok"}

    def _guess_root_cause(self, categories: Sequence[str], text: str) -> str:
        if "memory_access_violation" in categories:
            return "Acceso a memoria invalido: puntero nulo o buffer overflow"
        if "null_pointer" in categories:
            return "Uso de objeto nulo sin comprobar"
        if "missing_dependency" in categories:
            return "Dependencia no instalada o path incorrecto"
        if "permission_denied" in categories:
            return "Permisos insuficientes para acceder a recurso"
        if "stack_overflow" in categories:
            return "Recursion infinita o stack demasiado pequeno"
        return "Causa desconocida, revisar traza completa"

    def _suggest_fix(self, categories: Sequence[str]) -> str:
        if "memory_access_violation" in categories:
            return "Revisar punteros, agregar validaciones de bounds y usar smart pointers"
        if "null_pointer" in categories:
            return "Agregar comprobaciones de None antes de acceder a atributos"
        if "missing_dependency" in categories:
            return "Instalar dependencia y verificar PYTHONPATH/Cargo.toml/package.json"
        if "permission_denied" in categories:
            return "Ejecutar con permisos adecuados o ajustar ACLs"
        if "stack_overflow" in categories:
            return "Convertir recursion a iteracion o aumentar tamano de stack"
        return "Revisar traza completa y agregar logging"

    def _severity(self, categories: Sequence[str]) -> str:
        critical = {"memory_access_violation", "stack_overflow", "deadlock"}
        high = {"null_pointer", "out_of_memory", "permission_denied"}
        if any(c in critical for c in categories):
            return "critical"
        if any(c in high for c in categories):
            return "high"
        return "medium"
