from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import sys
import tempfile

from igris_os.programming import EngineeringWorkflow, ProgrammingPreflight


@dataclass(frozen=True, slots=True)
class ProjectSnapshot:
    name: str
    source: str
    tests: str = ""
    expect_syntax_error: bool = False
    expect_security_risk: bool = False
    expect_tests_pass: bool = False


@dataclass(frozen=True, slots=True)
class SnapshotResult:
    name: str
    score: int
    passed: bool
    syntax_error: bool
    security_risk: bool
    tests_pass: bool
    evidence: tuple[str, ...]


class TemporalProgrammingBenchmark:
    """Compara etapas de un proyecto con criterios constantes y locales."""

    SNAPSHOTS = (
        ProjectSnapshot("v1_sintaxis_rota", "def add(:\n", expect_syntax_error=True),
        ProjectSnapshot("v2_insegura", "def add(a, b):\n    return eval('a+b')\n",
                        "def test_add():\n    assert True\n", expect_security_risk=True),
        ProjectSnapshot("v3_funcional", "def add(a, b):\n    return a + b\n",
                        "def test_add():\n    from app import add\n    assert add(2, 3) == 5\n",
                        expect_tests_pass=True),
        ProjectSnapshot("v4_verificada", "def add(a, b):\n    return a + b\n",
                        "def test_add():\n    from app import add\n    assert add(2, 3) == 5\n",
                        expect_tests_pass=True),
    )

    def run(self) -> tuple[SnapshotResult, ...]:
        return tuple(self._run_snapshot(snapshot) for snapshot in self.SNAPSHOTS)

    def _run_snapshot(self, snapshot: ProjectSnapshot) -> SnapshotResult:
        with tempfile.TemporaryDirectory(prefix="igris-temporal-") as raw:
            root = Path(raw)
            (root / "app.py").write_text(snapshot.source, encoding="utf-8")
            if snapshot.tests:
                (root / "test_app.py").write_text(snapshot.tests, encoding="utf-8")
            report = ProgrammingPreflight().inspect(root)
            syntax_error = any(item.category == "syntax" for item in report.findings)
            security_risk = any(item.category == "security" for item in report.findings)
            tests_pass = False
            if snapshot.tests and not syntax_error and not security_risk:
                execution = EngineeringWorkflow().run(
                    root, [sys.executable, "-m", "pytest", "-q"],
                    confirmed=True, timeout=15)
                tests_pass = bool(execution.run and execution.run.returncode == 0
                                  and not execution.run.timed_out)
            diagnostic_checks = (
                syntax_error == snapshot.expect_syntax_error,
                security_risk == snapshot.expect_security_risk,
                tests_pass == snapshot.expect_tests_pass,
            )
            quality_checks = (
                not syntax_error,
                not security_risk,
                tests_pass,
            )
            score = int(sum(quality_checks) * 100 / len(quality_checks))
            evidence = (
                f"syntax_error={syntax_error}",
                f"security_risk={security_risk}",
                f"tests_pass={tests_pass}",
            )
            return SnapshotResult(snapshot.name, score, all(diagnostic_checks),
                                  syntax_error, security_risk, tests_pass, evidence)

    def report(self) -> dict[str, object]:
        results = self.run()
        scores = [result.score for result in results]
        return {
            "passed": all(result.passed for result in results),
            "snapshots": len(results),
            "results": [asdict(result) for result in results],
            "score_start": scores[0],
            "score_end": scores[-1],
            "improvement_points": scores[-1] - scores[0],
        }

    def write_report(self, path: Path) -> dict[str, object]:
        report = self.report()
        target = path.resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report