import ast
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from igris_os.ai import ModelReply
from igris_os.programming.preprocessor import PythonPreprocessor
from igris_os.security import run_restricted


FORBIDDEN = {"eval", "exec", "compile", "__import__"}
FORBIDDEN_IMPORTS = {"subprocess", "socket", "ctypes", "shutil"}
FORBIDDEN_ATTRIBUTES = {
    "system", "popen", "spawn", "remove", "removedirs", "rmdir",
    "unlink", "rmtree", "rename", "replace", "chmod", "chown",
}

REPAIR_SYSTEM = (
    "Eres un ingeniero senior especializado en depuracion autonoma. "
    "Analiza el codigo fuente y el error de prueba. Devuelve SOLO JSON: "
    '{"source":"codigo completo corregido","explanation":"cambio realizado"}. '
    "Sin markdown. Sin texto fuera del JSON."
)


@dataclass(frozen=True, slots=True)
class Verification:
    ok: bool
    message: str
    sha256: str = ""
    diagnostics: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class RepairResult:
    ok: bool
    message: str
    source: str = ""
    attempts: int = 0
    diagnostics: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class LintIssue:
    line: int
    code: str
    message: str
    severity: str  # "error" | "warning"


@dataclass(frozen=True, slots=True)
class LintReport:
    ok: bool
    issues: tuple[LintIssue, ...] = ()


@dataclass(frozen=True, slots=True)
class DependencyReport:
    stdlib: tuple[str, ...] = ()
    third_party: tuple[str, ...] = ()


class PythonWorkshop:
    def __init__(self, root: Path, timeout: int = 20,
                 repair_model: str = "qwen2.5-coder:7b") -> None:
        self.root = root.resolve()
        self.timeout = timeout
        self.repair_model = repair_model
        self.preprocessor = PythonPreprocessor()

    def verify(self, source: str, tests: str) -> Verification:
        try:
            trees = (ast.parse(source), ast.parse(tests))
        except SyntaxError as exc:
            return Verification(False, f"SyntaxError: {exc}")
        for tree in trees:
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    names = ([a.name.split(".")[0] for a in node.names]
                             if isinstance(node, ast.Import)
                             else [str(node.module).split(".")[0]])
                    if FORBIDDEN_IMPORTS.intersection(names):
                        return Verification(False, "Importacion peligrosa")
                if isinstance(node, ast.Call):
                    if (isinstance(node.func, ast.Name) and
                            node.func.id in FORBIDDEN):
                        return Verification(
                            False, "Ejecucion dinamica bloqueada")
                    if (isinstance(node.func, ast.Attribute) and
                            node.func.attr in FORBIDDEN_ATTRIBUTES):
                        return Verification(
                            False, "Operacion de sistema bloqueada")
        lint = self.lint(source)
        if not lint.ok:
            errors = [issue.message for issue in lint.issues
                      if issue.severity == "error"]
            return Verification(False, "Lint: " + "; ".join(errors),
                                diagnostics=tuple(errors))
        source = self.preprocessor.process(source, "solution.py")
        tests = self.preprocessor.process(tests, "test_solution.py")
        if not self.preprocessor.is_valid_python(source):
            return Verification(False, "SyntaxError tras preprocesado")
        if not self.preprocessor.is_valid_python(tests):
            return Verification(False, "Tests con SyntaxError tras preprocesado")
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "solution.py").write_text(source, encoding="utf-8")
        (self.root / "test_solution.py").write_text(tests, encoding="utf-8")
        run = run_restricted(
            self.root, timeout=self.timeout, memory_limit_mb=512,
            cpu_seconds=max(10, self.timeout))
        if run.timed_out:
            return Verification(False, "Pruebas agotaron el tiempo",
                                diagnostics=("timeout",))
        if run.returncode:
            diag = (run.stdout + run.stderr)[-4000:]
            message = (run.stdout + run.stderr)[-2000:]
            if run.returncode == 2:
                message = "Seguridad: " + message
            return Verification(False, message, diagnostics=(diag,))
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
        (self.root / "verification.json").write_text(
            json.dumps({"sha256": digest, "tests_passed": True}, indent=2),
            encoding="utf-8",
        )
        return Verification(True, "Codigo verificado", digest)

    def verify_with_repair(self, source: str, tests: str,
                           client, max_attempts: int = 3,
                           on_progress: Callable[[int, str], None] | None = None
                           ) -> RepairResult:
        current = source
        last_diagnostics = ""
        for attempt in range(1, max_attempts + 1):
            if on_progress:
                on_progress(int(60 * attempt / max_attempts),
                            f"Verificacion intento {attempt}/{max_attempts}")
            report = self.verify(current, tests)
            if report.ok:
                return RepairResult(True, "Codigo verificado tras " +
                                    str(attempt - 1) + " reparaciones",
                                    current, attempt - 1)
            last_diagnostics = report.diagnostics[0] if report.diagnostics else report.message
            if attempt == max_attempts:
                break
            if on_progress:
                on_progress(int(60 * attempt / max_attempts) + 10,
                            f"Reparando intento {attempt}/{max_attempts}")
            repair = self._repair(current, tests, last_diagnostics, client)
            if not repair.ok or not repair.source.strip():
                return RepairResult(False, "Reparacion fallida: " +
                                    repair.message, current, attempt,
                                    (last_diagnostics,))
            current = repair.source
        return RepairResult(False, "No supero verificacion tras " +
                            str(max_attempts) + " intentos",
                            current, max_attempts, (last_diagnostics,))

    def _repair(self, source: str, tests: str, diagnostics: str,
                client) -> RepairResult:
        prompt = (
            REPAIR_SYSTEM +
            "\nCODIGO FUENTE:\n" + source +
            "\nTESTS:\n" + tests +
            "\nDIAGNOSTICO DEL FALLO:\n" + diagnostics[:3000]
        )
        reply: ModelReply = client.generate(prompt, self.repair_model)
        if not reply.ok:
            return RepairResult(False, "Modelo de reparacion sin respuesta: " +
                                (reply.error or ""))
        try:
            cleaned = re.sub(r"^\s*```(?:json)?|```\s*$", "", reply.text,
                             flags=re.IGNORECASE).strip()
            data = json.loads(cleaned, strict=False)
            fixed = str(data.get("source", "")).strip()
            if not fixed:
                raise ValueError("Sin source en respuesta de reparacion")
            ast.parse(fixed)
            return RepairResult(True, str(data.get("explanation", "")),
                                fixed)
        except (ValueError, TypeError, KeyError, json.JSONDecodeError,
                SyntaxError) as exc:
            return RepairResult(False, "Reparacion invalida: " + str(exc))

    def lint(self, source: str) -> LintReport:
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            return LintReport(False, (LintIssue(
                exc.lineno or 0, "E901", f"SyntaxError: {exc}", "error"),))
        defined = set(dir(__builtins__)) | {"self", "cls", "int", "str",
                    "float", "bool", "list", "dict", "tuple", "set", "type",
                    "object", "bytes", "complex", "None", "True", "False",
                    "ZeroDivisionError", "TypeError", "ValueError", "KeyError",
                    "IndexError", "AttributeError", "ImportError", "IOError",
                    "OSError", "RuntimeError", "StopIteration", "AssertionError",
                    "ArithmeticError", "LookupError", "BufferError", "Exception",
                    "BaseException", "MemoryError", "OverflowError", "Warning",
                    "DeprecationWarning", "PendingDeprecationWarning",
                    "SyntaxError", "NameError", "IndentationError",
                    "TabError", "SystemExit", "GeneratorExit", "KeyboardInterrupt",
                    "staticmethod", "classmethod", "property", "input", "print",
                    "len", "range", "enumerate", "zip", "map", "filter",
                    "abs", "min", "max", "sum", "round", "sorted", "reversed",
                    "isinstance", "issubclass", "hasattr", "getattr", "setattr",
                    "open", "file", "help", "id", "hash", "repr", "ascii",
                    "chr", "ord", "bin", "hex", "oct", "pow", "divmod",
                    "all", "any", "iter", "next", "callable", "super",
                    "__name__", "__doc__", "__package__", "__file__",
                    "__builtins__", "__loader__", "__spec__", "__annotations__"}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)):
                defined.add(node.name)
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Name):
                        defined.add(decorator.id)
            elif isinstance(node, ast.arg):
                defined.add(node.arg)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    defined.add(alias.asname or alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    defined.add(alias.asname or alias.name)
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                defined.add(node.id)
            elif isinstance(node, ast.ExceptHandler):
                if node.name:
                    defined.add(node.name)
        issues = []
        seen = set()
        for node in ast.walk(tree):
            if (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
                    and node.id not in defined):
                key = (node.lineno, node.id)
                if key not in seen:
                    seen.add(key)
                    issues.append(LintIssue(
                        node.lineno, "E0602",
                        f"Nombre no definido: {node.id}", "error"))
        for index, line in enumerate(source.splitlines(), 1):
            if len(line) > 100:
                issues.append(LintIssue(
                    index, "W501", "Linea mayor de 100 caracteres", "warning"))
        ok = all(issue.severity == "warning" for issue in issues)
        return LintReport(ok, tuple(issues))

    def dependencies(self, source: str) -> DependencyReport:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return DependencyReport()
        stdlib = set(sys.stdlib_module_names)
        std, third = set(), set()
        for node in ast.walk(tree):
            roots = []
            if isinstance(node, ast.Import):
                roots = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots = [node.module.split(".")[0]]
            for root in roots:
                (std if root in stdlib else third).add(root)
        return DependencyReport(tuple(sorted(std)), tuple(sorted(third)))
