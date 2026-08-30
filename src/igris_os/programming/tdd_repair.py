from __future__ import annotations

import ast
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from igris_os.programming.engineering_workflow import EngineeringWorkflow


@dataclass(frozen=True, slots=True)
class TddObservation:
    function: str
    args: tuple[Any, ...]
    expected: Any


@dataclass(frozen=True, slots=True)
class TddRepairResult:
    ok: bool
    message: str
    changed_files: tuple[str, ...] = ()
    observations: int = 0
    duration_seconds: float = 0.0


class PythonTddMicroRepairer:
    """Repara funciones puras pequenas usando ejemplos literales de pytest."""

    PARAMETER_NAMES = ("a", "b", "c", "value", "items", "text")

    def repair(self, root: Path, module: str = "app.py", *, timeout: int = 20) -> TddRepairResult:
        started = time.monotonic()
        project_root = root.resolve()
        target = (project_root / module).resolve()
        if not target.is_relative_to(project_root) or not target.is_file():
            return TddRepairResult(False, "Modulo objetivo no valido")
        observations = self._collect_observations(project_root)
        if not observations:
            return TddRepairResult(False, "No hay asserts literales para reparar")
        original = target.read_text(encoding="utf-8")
        try:
            updated, changed = self._rewrite_source(original, observations)
        except (SyntaxError, ValueError) as exc:
            return TddRepairResult(False, "No se pudo sintetizar reparacion: " + str(exc))
        if not changed:
            return TddRepairResult(False, "Sin reparacion aplicable", observations=len(observations))
        target.write_text(updated, encoding="utf-8")
        checked = EngineeringWorkflow().run(
            project_root, ("python", "-m", "pytest", "-q"), confirmed=True, timeout=timeout)
        ok = bool(checked.run and checked.run.returncode == 0 and not checked.run.timed_out)
        if not ok:
            target.write_text(original, encoding="utf-8")
            detail = checked.reason if checked.run is None else (checked.run.stdout + checked.run.stderr)[-1000:]
            return TddRepairResult(
                False, "Reparacion rechazada por pruebas: " + detail,
                observations=len(observations),
                duration_seconds=round(time.monotonic() - started, 3),
            )
        return TddRepairResult(
            True, "Reparacion TDD verificada",
            (module,), len(observations), round(time.monotonic() - started, 3),
        )

    def _collect_observations(self, root: Path) -> tuple[TddObservation, ...]:
        observations: list[TddObservation] = []
        for path in sorted(root.rglob("test_*.py")) + sorted(root.rglob("*_test.py")):
            if any(part in {".git", ".pytest_cache", "__pycache__"} for part in path.parts):
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Assert):
                    continue
                observation = self._observation_from_assert(node)
                if observation is not None:
                    observations.append(observation)
        return tuple(observations)

    def _observation_from_assert(self, node: ast.Assert) -> TddObservation | None:
        test = node.test
        if not isinstance(test, ast.Compare) or len(test.ops) != 1 or len(test.comparators) != 1:
            return None
        if not isinstance(test.ops[0], ast.Eq) or not isinstance(test.left, ast.Call):
            return None
        function = self._function_name(test.left.func)
        if not function:
            return None
        try:
            args = tuple(ast.literal_eval(arg) for arg in test.left.args)
            expected = ast.literal_eval(test.comparators[0])
        except (ValueError, TypeError):
            return None
        return TddObservation(function, args, expected)

    @staticmethod
    def _function_name(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return ""

    def _rewrite_source(self, source: str, observations: tuple[TddObservation, ...]) -> tuple[str, bool]:
        tree = ast.parse(source)
        by_function: dict[str, list[TddObservation]] = {}
        for observation in observations:
            by_function.setdefault(observation.function, []).append(observation)
        changed = False
        existing = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef) or node.name not in by_function:
                continue
            params = [arg.arg for arg in node.args.args]
            expression = self._select_expression(params, tuple(by_function[node.name]))
            if expression is None:
                continue
            node.body = [ast.Return(ast.parse(expression, mode="eval").body)]
            changed = True
        for name, items in by_function.items():
            if name in existing:
                continue
            arity = max(len(item.args) for item in items)
            params = list(self.PARAMETER_NAMES[:arity]) or ["value"]
            expression = self._select_expression(params, tuple(items))
            if expression is None:
                continue
            function = ast.parse(
                f"def {name}({', '.join(params)}):\n    return {expression}\n"
            ).body[0]
            tree.body.append(function)
            changed = True
        ast.fix_missing_locations(tree)
        return ast.unparse(tree) + "\n", changed

    def _select_expression(self, params: list[str], observations: tuple[TddObservation, ...]) -> str | None:
        if not params:
            values = {repr(item.expected) for item in observations}
            return values.pop() if len(values) == 1 else None
        candidates = self._candidate_expressions(params, observations)
        for expression in candidates:
            if self._matches(expression, params, observations):
                return expression
        return None

    def _candidate_expressions(self, params: list[str], observations: tuple[TddObservation, ...]) -> tuple[str, ...]:
        first_expected = observations[0].expected
        candidates: list[str] = []
        can_return_constant = (
            len(observations) >= 2
            and isinstance(first_expected, (str, int, float, bool, type(None)))
        )
        if can_return_constant and all(item.expected == first_expected for item in observations):
            candidates.append(repr(first_expected))
        if len(params) >= 2:
            a, b = params[0], params[1]
            candidates.extend((f"{a} + {b}", f"{a} - {b}", f"{b} - {a}", f"{a} * {b}"))
        value = params[0]
        candidates.extend((
            f"len({value})",
            f"len({value}.split())",
            f"{value}.upper()",
            f"{value}.lower()",
            f"{value}.strip()",
            f"{value}.strip().lower()",
            f"{value}.lower().strip()",
            f"sorted({value})",
        ))
        return tuple(dict.fromkeys(candidates))

    @staticmethod
    def _matches(expression: str, params: list[str], observations: tuple[TddObservation, ...]) -> bool:
        try:
            compiled = compile(ast.parse(expression, mode="eval"), "<tdd-expression>", "eval")
        except SyntaxError:
            return False
        for item in observations:
            if len(item.args) != len(params):
                return False
            local_values = dict(zip(params, item.args, strict=True))
            try:
                safe_globals = {"__builtins__": {}, "len": len, "sorted": sorted}
                actual = eval(compiled, safe_globals, local_values)
            except Exception:
                return False
            if actual != item.expected:
                return False
        return True


class PythonTddProjectRepairer:
    """Busca el modulo reparable dentro de un proyecto Python y valida la suite completa."""

    _EXCLUDED = {".git", ".pytest_cache", "__pycache__", ".venv", "venv", "build", "dist"}

    def repair(self, root: Path, *, timeout: int = 30) -> TddRepairResult:
        started = time.monotonic()
        project_root = root.resolve()
        if not project_root.is_dir():
            return TddRepairResult(False, "Proyecto no valido")
        before = EngineeringWorkflow().run(
            project_root, ("python", "-m", "pytest", "-q"), confirmed=True, timeout=timeout)
        if before.run and before.run.returncode == 0 and not before.run.timed_out:
            return TddRepairResult(True, "Proyecto ya verificado", duration_seconds=0.0)
        tried = 0
        last_message = "Sin modulos candidatos"
        for relative in self._candidate_modules(project_root):
            tried += 1
            result = PythonTddMicroRepairer().repair(
                project_root, relative.as_posix(), timeout=timeout)
            if result.ok:
                return TddRepairResult(
                    True, "Reparacion TDD de proyecto verificada",
                    result.changed_files, result.observations,
                    round(time.monotonic() - started, 3),
                )
            last_message = result.message
        return TddRepairResult(
            False, f"No se encontro reparacion verificable tras {tried} modulos: {last_message}",
            duration_seconds=round(time.monotonic() - started, 3),
        )

    def _candidate_modules(self, root: Path) -> tuple[Path, ...]:
        modules: list[Path] = []
        for path in sorted(root.rglob("*.py")):
            relative = path.relative_to(root)
            if any(part in self._EXCLUDED for part in relative.parts):
                continue
            if path.name.startswith("test_") or path.name.endswith("_test.py"):
                continue
            modules.append(relative)
        return tuple(modules)
