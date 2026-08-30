from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import tempfile
import time

from igris_os.programming import (
    EngineeringWorkflow, PythonTddMicroRepairer, PythonTddProjectRepairer,
)


@dataclass(frozen=True, slots=True)
class ProductionReadinessResult:
    name: str
    passed: bool
    score: int
    duration_seconds: float
    evidence: tuple[str, ...]


class ProductionProgrammingReadinessBenchmark:
    """Mide productividad real minima: reparar codigo y probarlo sin mocks."""

    def run(self) -> tuple[ProductionReadinessResult, ...]:
        return (
            self._repair_math_project(),
            self._repair_text_project(),
            self._repair_multifile_project(),
        )

    def report(self) -> dict[str, object]:
        results = self.run()
        score = int(sum(item.score for item in results) / len(results)) if results else 0
        return {
            "kind": "production_programming_readiness",
            "passed": all(item.passed for item in results),
            "score": score,
            "results": [asdict(item) for item in results],
        }

    def write_report(self, path: Path) -> dict[str, object]:
        report = self.report()
        target = path.resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report

    def _repair_math_project(self) -> ProductionReadinessResult:
        return self._run_repair_case(
            "repair_math_project",
            "def add(a, b):\n    return 0\n\ndef multiply(a, b):\n    return 0\n",
            "from app import add, multiply\n\n"
            "def test_add():\n    assert add(2, 3) == 5\n    assert add(-1, 4) == 3\n\n"
            "def test_multiply():\n    assert multiply(3, 4) == 12\n    assert multiply(-2, 5) == -10\n",
        )

    def _repair_text_project(self) -> ProductionReadinessResult:
        return self._run_repair_case(
            "repair_text_project",
            "def word_count(text):\n    return 0\n\ndef normalize(text):\n    return text\n",
            "from app import normalize, word_count\n\n"
            "def test_word_count():\n    assert word_count('uno dos tres') == 3\n    assert word_count('') == 0\n\n"
            "def test_normalize():\n    assert normalize('  HOLA  ') == 'hola'\n",
        )

    def _repair_multifile_project(self) -> ProductionReadinessResult:
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="igris-production-readiness-") as raw:
            root = Path(raw)
            (root / "main.py").write_text(
                "from service import total_items\n\n"
                "def run(items):\n    return total_items(items)\n",
                encoding="utf-8")
            (root / "service.py").write_text(
                "def total_items(items):\n    return 0\n",
                encoding="utf-8")
            (root / "test_service.py").write_text(
                "from main import run\nfrom service import total_items\n\n"
                "def test_total_items():\n    assert total_items(['a', 'b', 'c']) == 3\n\n"
                "def test_run_delegates_to_service():\n    assert run(['x', 'y']) == 2\n",
                encoding="utf-8")
            before = EngineeringWorkflow().run(
                root, ("python", "-m", "pytest", "-q"), confirmed=True, timeout=20)
            before_failed = bool(before.run and before.run.returncode != 0)
            repaired = PythonTddProjectRepairer().repair(root, timeout=20)
            after = EngineeringWorkflow().run(
                root, ("python", "-m", "pytest", "-q"), confirmed=True, timeout=20)
            after_passed = bool(after.run and after.run.returncode == 0 and not after.run.timed_out)
            touched_service = "service.py" in repaired.changed_files
            passed = before_failed and repaired.ok and after_passed and touched_service
            checks = (before_failed, repaired.ok, after_passed, touched_service,
                      repaired.duration_seconds <= 8)
            score = int(sum(checks) * 100 / len(checks))
            return ProductionReadinessResult(
                name="repair_multifile_project",
                passed=passed,
                score=score,
                duration_seconds=round(time.monotonic() - started, 3),
                evidence=(
                    f"before_failed={before_failed}",
                    f"repair_ok={repaired.ok}",
                    f"after_passed={after_passed}",
                    f"changed_files={','.join(repaired.changed_files)}",
                    f"repair_duration={repaired.duration_seconds}",
                ),
            )

    def _run_repair_case(self, name: str, source: str, tests: str) -> ProductionReadinessResult:
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="igris-production-readiness-") as raw:
            root = Path(raw)
            (root / "app.py").write_text(source, encoding="utf-8")
            (root / "test_app.py").write_text(tests, encoding="utf-8")
            before = EngineeringWorkflow().run(
                root, ("python", "-m", "pytest", "-q"), confirmed=True, timeout=20)
            before_failed = bool(before.run and before.run.returncode != 0)
            repaired = PythonTddMicroRepairer().repair(root, timeout=20)
            after = EngineeringWorkflow().run(
                root, ("python", "-m", "pytest", "-q"), confirmed=True, timeout=20)
            after_passed = bool(after.run and after.run.returncode == 0 and not after.run.timed_out)
            passed = before_failed and repaired.ok and after_passed
            checks = (before_failed, repaired.ok, after_passed, repaired.duration_seconds <= 5)
            score = int(sum(checks) * 100 / len(checks))
            return ProductionReadinessResult(
                name=name,
                passed=passed,
                score=score,
                duration_seconds=round(time.monotonic() - started, 3),
                evidence=(
                    f"before_failed={before_failed}",
                    f"repair_ok={repaired.ok}",
                    f"after_passed={after_passed}",
                    f"repair_duration={repaired.duration_seconds}",
                ),
            )
