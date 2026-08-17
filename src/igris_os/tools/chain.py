from __future__ import annotations

import ast
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class RetryPolicy:
    max_retries: int = 2
    base_delay: float = 0.5
    max_delay: float = 8.0
    retry_on: tuple = ("timeout", "connection")

    def next_delay(self, attempt: int) -> float:
        delay = self.base_delay * (2 ** attempt)
        return min(delay, self.max_delay)


@dataclass
class StepConfig:
    timeout_seconds: Optional[float] = None
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)


@dataclass
class ToolChain:
    name: str
    steps: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class StepResult:
    step_id: str
    ok: bool
    result: Any = None
    error: str = ""
    duration_ms: float = 0.0
    status: str = "done"


class ToolChainEngine:
    MAX_WORKERS = 3

    def __init__(self, registry: Dict[str, Callable] | None = None):
        self.registry = registry or {}

    def execute(self, chain: ToolChain, context: Dict[str, Any]) -> Dict[str, Any]:
        if not self.validate(chain):
            raise ValueError(f"Invalid chain: {chain.name}")
        results: Dict[str, StepResult] = {}
        remaining = {s.get("id", s["tool"]) for s in chain.steps}
        completed: set = set()
        while remaining:
            ready = [
                s for s in chain.steps
                if s.get("id", s["tool"]) in remaining
                and all(d in completed for d in s.get("depends_on", []))
                and self._check_condition(s, results, context)
            ]
            if not ready:
                break
            parallel = [s for s in ready if not s.get("sequential")]
            sequential = [s for s in ready if s.get("sequential")]
            if parallel:
                batch, remaining = self._split_batch(parallel, remaining)
                self.execute_parallel(batch, context, results)
            elif sequential:
                step = sequential[0]
                sid = step.get("id", step["tool"])
                self.execute_sequential([step], context, results)
                remaining.discard(sid)
                completed.add(sid)
            else:
                break
            for step in ready:
                sid = step.get("id", step["tool"])
                if sid in results:
                    completed.add(sid)
                    remaining.discard(sid)
        return {
            "chain": chain.name,
            "results": {sid: r.__dict__ for sid, r in results.items()},
            "ok": all(r.ok for r in results.values()),
        }

    def execute_branch(self, chain: ToolChain, context: Dict[str, Any],
                       branch_condition: Dict[str, Any]) -> Dict[str, Any]:
        steps = []
        for step in chain.steps:
            branches = step.get("branches", [])
            matched = False
            for branch in branches:
                if self._evaluate_expr(branch.get("when", ""), branch_condition, context):
                    steps.extend(branch.get("steps", []))
                    matched = True
                    break
            if not matched and "else" in step:
                steps.extend(step["else"])
            if not branches and "else" not in step:
                steps.append(step)
        branch_chain = ToolChain(name=f"{chain.name}_branch", steps=steps)
        return self.execute(branch_chain, context)

    def validate(self, chain: ToolChain) -> bool:
        ids = {s.get("id", s["tool"]) for s in chain.steps}
        if len(ids) != len(chain.steps):
            return False
        for s in chain.steps:
            for d in s.get("depends_on", []):
                if d not in ids:
                    return False
            tool = s["tool"]
            if not callable(tool) and tool not in self.registry:
                return False
        return not self._has_cycle(chain.steps)

    def rollback(self, chain: ToolChain, context: Dict[str, Any]) -> Dict[str, Any]:
        rolled: List[StepResult] = []
        for step in reversed(chain.steps):
            fn = step.get("rollback")
            if not fn:
                continue
            sid = step.get("id", step["tool"])
            t0 = time.perf_counter()
            try:
                res = fn(context)
                ok, error = True, ""
            except Exception as e:
                res, ok, error = None, False, str(e)
            rolled.append(StepResult(sid, ok, res, error, (time.perf_counter() - t0) * 1000))
        return {"chain": chain.name, "rolled_back": [r.__dict__ for r in rolled]}

    def execute_parallel(self, steps: List[Dict[str, Any]], context: Dict[str, Any], results: Dict[str, StepResult] | None = None) -> Dict[str, StepResult]:
        results = results or {}
        sem = threading.Semaphore(self.MAX_WORKERS)
        threads = []
        for step in steps:
            t = threading.Thread(target=self._run_step_with_retry, args=(step, context, results, sem), daemon=True)
            threads.append(t)
            t.start()
        for t in threads:
            t.join(timeout=300)
        return results

    def execute_sequential(self, steps: List[Dict[str, Any]], context: Dict[str, Any], results: Dict[str, StepResult] | None = None) -> Dict[str, StepResult]:
        results = results or {}
        for step in steps:
            self._run_step_with_retry(step, context, results)
        return results

    def _run_step_with_retry(self, step, context, results, sem=None):
        if sem:
            sem.acquire()
        try:
            sid = step.get("id", step["tool"])
            tool = step["tool"]
            if not callable(tool) and tool in self.registry:
                tool = self.registry[tool]
            params = step.get("params", {})
            config = StepConfig(**step.get("config", {}))
            t0 = time.perf_counter()
            last_error = ""
            attempts = 0
            ok = False
            res = None
            while True:
                attempts += 1
                try:
                    res = self._run_with_timeout(tool, context, params, config.timeout_seconds)
                    ok, last_error = True, ""
                    break
                except Exception as e:
                    last_error = str(e)
                    error_type = type(e).__name__.lower()
                    policy = config.retry_policy
                    if attempts > policy.max_retries or not self._should_retry(error_type, policy):
                        ok = False
                        break
                    time.sleep(policy.next_delay(attempts - 1))
            duration = (time.perf_counter() - t0) * 1000
            status = "done" if ok else "failed"
            if not ok and last_error:
                status = f"failed:{error_type}"
            results[sid] = StepResult(sid, ok, res, last_error, duration, status)
        finally:
            if sem:
                sem.release()

    def _run_with_timeout(self, tool, context, params, timeout_seconds):
        if timeout_seconds is None:
            return tool(context, **params)
        result = [None]
        exc = [None]
        def target():
            try:
                result[0] = tool(context, **params)
            except Exception as e:
                exc[0] = e
        t = threading.Thread(target=target, daemon=True)
        t.start()
        t.join(timeout_seconds)
        if t.is_alive():
            raise TimeoutError(f"Step timeout after {timeout_seconds}s")
        if exc[0] is not None:
            raise exc[0]
        return result[0]

    def _should_retry(self, error_type: str, policy: RetryPolicy) -> bool:
        return any(marker in error_type for marker in policy.retry_on)

    def generate_steps_from_nl(self, description: str, model: str = "qwen2.5-coder:1.5b") -> List[Dict[str, Any]]:
        prompt = (
            "Convierte la siguiente descripcion en una lista de pasos de tool chain JSON. "
            "Cada paso debe tener 'id', 'tool', 'params' y opcionalmente 'depends_on', 'sequential', 'config'. "
            "Usa solo herramientas del registro. Descripcion: " + description
        )
        text = ""
        try:
            from igris_os.ai import OllamaClient
            client = OllamaClient()
            reply = client.generate(prompt, model)
            if reply.ok:
                text = reply.text
        except Exception:
            text = ""
        steps = []
        if text:
            import json, re
            match = re.search(r"\[.*\]", text, re.DOTALL)
            if match:
                try:
                    steps = json.loads(match.group(0))
                except Exception:
                    steps = []
        if not steps:
            steps = [{"id": "step_0", "tool": "analyze", "params": {"description": description}, "sequential": True}]
        return steps

    def _split_batch(self, steps, remaining):
        batch, new_remaining = [], set(remaining)
        for s in steps:
            sid = s.get("id", s["tool"])
            if sid in new_remaining:
                batch.append(s)
                new_remaining.discard(sid)
        return batch, new_remaining

    def _check_condition(self, step, results, context):
        cond = step.get("condition")
        if not cond:
            return True
        dep_id = cond.get("on")
        if dep_id not in results:
            return False
        expr = cond.get("expr", "")
        prev = results[dep_id].result
        try:
            return bool(self._evaluate_expr(expr, {"result": prev}, context))
        except Exception:
            return False

    def _evaluate_expr(self, expr: str, local_vars: Dict[str, Any], context: Dict[str, Any]) -> bool:
        try:
            tree = ast.parse(expr, mode="eval")
        except SyntaxError:
            return False
        namespace = {"context": context, **local_vars}
        try:
            return bool(_safe_eval_node(tree.body, namespace))
        except Exception:
            return False

    def _has_cycle(self, steps):
        ids = {s.get("id", s["tool"]) for s in steps}
        graph = {i: set() for i in ids}
        for s in steps:
            sid = s.get("id", s["tool"])
            for d in s.get("depends_on", []):
                graph[sid].add(d)
        visited = set()
        path = set()

        def dfs(node):
            visited.add(node)
            path.add(node)
            for neighbor in graph.get(node, ()):
                if neighbor in path:
                    return True
                if neighbor not in visited and dfs(neighbor):
                    return True
            path.remove(node)
            return False

        return any(dfs(n) for n in ids if n not in visited)


def _safe_eval_node(node, namespace: dict) -> object:
    if isinstance(node, ast.Expression):
        return _safe_eval_node(node.body, namespace)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id not in namespace:
            raise ValueError(f"nombre desconocido: {node.id}")
        return namespace[node.id]
    if isinstance(node, ast.Attribute):
        if node.attr.startswith("_"):
            raise ValueError(f"atributo no permitido: {node.attr}")
        return getattr(_safe_eval_node(node.value, namespace), node.attr)
    if isinstance(node, ast.Subscript):
        return _safe_eval_node(node.value, namespace)[_safe_eval_node(node.slice, namespace)]
    if isinstance(node, ast.Slice):
        return slice(
            _safe_eval_node(node.lower, namespace) if node.lower else None,
            _safe_eval_node(node.upper, namespace) if node.upper else None,
            _safe_eval_node(node.step, namespace) if node.step else None,
        )
    if isinstance(node, ast.Tuple):
        return tuple(_safe_eval_node(elt, namespace) for elt in node.elts)
    if isinstance(node, ast.List):
        return [_safe_eval_node(elt, namespace) for elt in node.elts]
    if isinstance(node, ast.Dict):
        return {
            _safe_eval_node(k, namespace): _safe_eval_node(v, namespace)
            for k, v in zip(node.keys, node.values)
        }
    if isinstance(node, ast.Set):
        return {_safe_eval_node(elt, namespace) for elt in node.elts}
    if isinstance(node, ast.BinOp):
        left = _safe_eval_node(node.left, namespace)
        right = _safe_eval_node(node.right, namespace)
        return _BIN_OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp):
        operand = _safe_eval_node(node.operand, namespace)
        return _UNARY_OPS[type(node.op)](operand)
    if isinstance(node, ast.BoolOp):
        values = [_safe_eval_node(v, namespace) for v in node.values]
        if isinstance(node.op, ast.And):
            return all(values)
        return any(values)
    if isinstance(node, ast.Compare):
        left = _safe_eval_node(node.left, namespace)
        for op, comparator in zip(node.ops, node.comparators):
            right = _safe_eval_node(comparator, namespace)
            if not _CMP_OPS[type(op)](left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.IfExp):
        return _safe_eval_node(node.body, namespace) if _safe_eval_node(
            node.test, namespace) else _safe_eval_node(node.orelse, namespace)
    raise ValueError(f"expresion no permitida: {type(node).__name__}")


_BIN_OPS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.FloorDiv: lambda a, b: a // b,
    ast.Mod: lambda a, b: a % b,
    ast.Pow: lambda a, b: a ** b,
    ast.BitAnd: lambda a, b: a & b,
    ast.BitOr: lambda a, b: a | b,
    ast.BitXor: lambda a, b: a ^ b,
    ast.LShift: lambda a, b: a << b,
    ast.RShift: lambda a, b: a >> b,
}

_UNARY_OPS = {
    ast.Not: lambda a: not a,
    ast.USub: lambda a: -a,
    ast.UAdd: lambda a: +a,
    ast.Invert: lambda a: ~a,
}

_CMP_OPS = {
    ast.Eq: lambda a, b: a == b,
    ast.NotEq: lambda a, b: a != b,
    ast.Lt: lambda a, b: a < b,
    ast.LtE: lambda a, b: a <= b,
    ast.Gt: lambda a, b: a > b,
    ast.GtE: lambda a, b: a >= b,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
    ast.Is: lambda a, b: a is b,
    ast.IsNot: lambda a, b: a is not b,
}