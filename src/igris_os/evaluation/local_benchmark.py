from __future__ import annotations

from dataclasses import asdict, dataclass
import ast
import json
from pathlib import Path
import sys
import tempfile
import time

import requests

from igris_os.application.assistant import AssistantService
from igris_os.ai import ModelReply
from igris_os.programming import EngineeringWorkflow
from igris_os.programming import ProgrammingPreflight


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    name: str
    source: str
    expect_critical: bool = False
    expect_risk: bool = False


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    name: str
    passed: bool
    details: str


@dataclass(frozen=True, slots=True)
class ConversationCase:
    name: str
    prompt: str
    expected_terms: tuple[str, ...] = ()


class LocalProgrammingBenchmark:
    """Evaluación local de programación sin red, cuentas ni cuotas."""

    CASES = (
        BenchmarkCase("python_valido", "def add(a, b):\n    return a + b\n"),
        BenchmarkCase("syntax_invalida", "def broken(:\n", True),
        BenchmarkCase("eval_peligroso", "value = eval('1')\n", False, True),
    )

    CONVERSATION_CASES = (
        ConversationCase("saludo", "hola"),
        ConversationCase("estado", "que tal te encuentras?"),
        ConversationCase("critica", "tu respuesta es repetitiva"),
        ConversationCase("limite", "que puedes garantizar?"),
    )

    def run(self) -> tuple[BenchmarkResult, ...]:
        results = [self._check_case(case) for case in self.CASES]
        results.extend(self._check_conversation_case(case) for case in self.CONVERSATION_CASES)
        results.append(self._check_execution())
        results.append(self._check_timeout())
        results.append(self._check_forbidden_execution())
        return tuple(results)

    def run_and_record(self, path: Path) -> dict[str, object]:
        """Ejecuta una sesión y guarda evidencia local, sin telemetría externa."""
        results = self.run()
        report = {
            "passed": all(item.passed for item in results),
            "total": len(results),
            "passed_count": sum(item.passed for item in results),
            "results": [asdict(item) for item in results],
        }
        target = path.resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report

    @staticmethod
    def check_generated_python(client, model: str) -> BenchmarkResult:
        schema = {'type': 'object', 'properties': {'code': {'type': 'string'}},
                  'required': ['code'], 'additionalProperties': False}
        reply = client.generate_json(
            'Escriba una funcion Python suma_positivos(valores) que sume solo los numeros '
            'mayores que cero, sin modificar la lista. Solo una funcion, sin imports ni '
            'codigo de nivel superior. Devuelva su codigo en la propiedad code del JSON.',
            model, schema)
        if not reply.ok:
            return BenchmarkResult('generated_python', False, reply.error)
        try:
            source = json.loads(reply.text)['code']
            tree = ast.parse(source)
            if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
                raise ValueError('Se esperaba una sola funcion')
            if tree.body[0].name != 'suma_positivos':
                raise ValueError('Nombre de funcion incorrecto')
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom, ast.Attribute)):
                    raise ValueError('Construccion no permitida en la prueba')
                if isinstance(node, ast.Call) and (
                        not isinstance(node.func, ast.Name) or node.func.id != 'sum'):
                    raise ValueError('Llamada no permitida en la prueba')
        except (ValueError, TypeError, KeyError, SyntaxError) as exc:
            return BenchmarkResult('generated_python', False, str(exc))
        with tempfile.TemporaryDirectory(prefix='igris-generated-benchmark-') as directory:
            root = Path(directory)
            (root / 'generated.py').write_text(source, encoding='utf-8')
            verification = (
                'from generated import suma_positivos\n'
                'assert suma_positivos([]) == 0\n'
                'assert suma_positivos([-3, 0]) == 0\n'
                'values = [1, 2, -7]\n'
                'assert suma_positivos(values) == 3\n'
                'assert values == [1, 2, -7]\n'
                'assert suma_positivos([1.5, -1, 2.5]) == 4\n'
                "print('native-code-ok')\n")
            (root / 'verify.py').write_text(verification, encoding='utf-8')
            result = EngineeringWorkflow().run(
                root, [sys.executable, 'verify.py'], confirmed=True, timeout=10)
            passed = bool(result.executed and result.run and result.run.returncode == 0
                          and result.run.stdout.strip() == 'native-code-ok')
            return BenchmarkResult('generated_python', passed,
                f'backend={reply.backend}; sandboxed={getattr(result.run, "sandboxed", False)}; '
                f'returncode={getattr(result.run, "returncode", None)}')

    @staticmethod
    def _check_conversation_case(case: ConversationCase) -> BenchmarkResult:
        class BenchmarkClient:
            def models(self):
                return ("qwen2.5-coder:7b",)

            def generate(self, prompt, model):
                return ModelReply(True, "respuesta conversacional sobre " +
                                  prompt.split("ULTIMO MENSAJE DEL USUARIO:\n")[-1], model)

        reply = AssistantService(BenchmarkClient()).respond(case.prompt)
        text = reply.text.casefold()
        expected = any(term.casefold() in text for term in case.expected_terms)
        passed = bool(reply.ok and text and "respuesta conversacional" in text)
        return BenchmarkResult(
            "conversation_" + case.name, passed,
            f"ok={reply.ok}; routed_to_conversation={passed}; chars={len(text)}")

    def _check_case(self, case: BenchmarkCase) -> BenchmarkResult:
        with tempfile.TemporaryDirectory(prefix="igris-benchmark-") as raw:
            root = Path(raw)
            (root / "app.py").write_text(case.source, encoding="utf-8")
            report = ProgrammingPreflight().inspect(root)
            critical = any(item.severity == "critical" for item in report.findings)
            risk = any(item.category == "security" for item in report.findings)
            passed = critical == case.expect_critical and risk == case.expect_risk
            return BenchmarkResult(
                case.name, passed,
                f"critical={critical}; security_risk={risk}; files={report.files}")

    @staticmethod
    def _check_execution() -> BenchmarkResult:
        with tempfile.TemporaryDirectory(prefix="igris-benchmark-") as raw:
            root = Path(raw)
            (root / "app.py").write_text("print('benchmark-ok')\n", encoding="utf-8")
            result = EngineeringWorkflow().run(
                root, [sys.executable, "app.py"], confirmed=True, timeout=10)
            passed = bool(result.executed and result.run and
                          result.run.returncode == 0 and
                          result.run.stdout.strip() == "benchmark-ok")
            details = "executed=" + str(result.executed)
            if result.run:
                details += f"; returncode={result.run.returncode}; sandboxed={result.run.sandboxed}"
            return BenchmarkResult("sandbox_execution", passed, details)

    @staticmethod
    def _check_timeout() -> BenchmarkResult:
        with tempfile.TemporaryDirectory(prefix="igris-benchmark-") as raw:
            root = Path(raw)
            (root / "app.py").write_text("print('start')\n", encoding="utf-8")
            result = EngineeringWorkflow().run(
                root, [sys.executable, "-c", "import time; time.sleep(3)"],
                confirmed=True, timeout=1)
            passed = bool(result.executed and result.run and result.run.timed_out)
            return BenchmarkResult("sandbox_timeout", passed,
                                    f"executed={result.executed}; timed_out={getattr(result.run, 'timed_out', False)}")

    @staticmethod
    def _check_forbidden_execution() -> BenchmarkResult:
        with tempfile.TemporaryDirectory(prefix="igris-benchmark-") as raw:
            root = Path(raw)
            (root / "app.py").write_text("print('ok')\n", encoding="utf-8")
            result = EngineeringWorkflow().run(
                root, ["cmd.exe", "/c", "echo", "blocked"], confirmed=True)
            passed = not result.executed and result.reason == "Ejecutable no permitido"
            return BenchmarkResult("forbidden_executable", passed, result.reason)


def run_local_benchmark() -> dict[str, object]:
    results = LocalProgrammingBenchmark().run()
    return {
        "passed": all(item.passed for item in results),
        "total": len(results),
        "passed_count": sum(item.passed for item in results),
        "results": [asdict(item) for item in results],
    }


def run_inference_benchmark(endpoint: str, model: str, backend: str,
                            rounds: int = 3) -> dict[str, object]:
    from igris_os.ai.ollama import _is_loopback_endpoint

    endpoint = endpoint.rstrip('/').removesuffix('/v1')
    if not _is_loopback_endpoint(endpoint):
        raise ValueError('El benchmark solo permite motores en loopback')
    if backend not in {'ollama', 'openai'} or not 1 <= rounds <= 10:
        raise ValueError('Motor o numero de rondas invalido')
    prompt = ('Explique en espanol, en tres frases, por que debe ejecutar pruebas '
              'antes de entregar un programa. No utilice listas.')
    results = []
    for index in range(rounds):
        messages = [{'role': 'user', 'content': prompt}]
        if backend == 'ollama':
            path = '/api/chat'
            body = {'model': model, 'messages': messages, 'stream': False,
                    'keep_alive': '60s', 'options': {'temperature': 0, 'seed': 42,
                    'num_ctx': 4096, 'num_predict': 256}}
        else:
            path = '/v1/chat/completions'
            body = {'model': model, 'messages': messages, 'stream': False,
                    'temperature': 0, 'seed': 42, 'max_tokens': 256}
        started = time.perf_counter()
        response = requests.post(endpoint + path, json=body, timeout=120)
        response.raise_for_status()
        data = response.json()
        elapsed = time.perf_counter() - started
        if backend == 'ollama':
            text = data.get('message', {}).get('content', '')
            tokens = data.get('eval_count', 0)
            complete = data.get('done') is True and data.get('done_reason') != 'length'
        else:
            choice = data.get('choices', [{}])[0]
            text = choice.get('message', {}).get('content', '')
            tokens = data.get('usage', {}).get('completion_tokens', 0)
            complete = choice.get('finish_reason') == 'stop'
        results.append({'round': index + 1, 'seconds': round(elapsed, 4),
                        'tokens': tokens, 'tokens_per_second': round(tokens / elapsed, 2),
                        'complete': bool(text.strip() and complete), 'text': text})
    return {'backend': backend, 'endpoint': endpoint, 'model': model,
            'context_tokens': 4096, 'output_limit': 256, 'results': results}