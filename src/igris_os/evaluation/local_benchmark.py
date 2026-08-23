from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
import tempfile

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