from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from igris_os.memory.experience import ExperienceMemory

from .local_benchmark import BenchmarkResult, LocalProgrammingBenchmark


@dataclass(frozen=True, slots=True)
class TrainingSession:
    passed: bool
    total: int
    passed_count: int
    experience_id: str | None
    results: tuple[BenchmarkResult, ...]


class LocalTrainingRunner:
    """Registra aprendizaje local únicamente tras una evaluación completa."""

    def __init__(self, memory_root: Path,
                 benchmark: LocalProgrammingBenchmark | None = None) -> None:
        self.memory = ExperienceMemory(memory_root)
        self.benchmark = benchmark or LocalProgrammingBenchmark()

    def run(self) -> TrainingSession:
        results = self.benchmark.run()
        passed_count = sum(item.passed for item in results)
        passed = bool(results) and passed_count == len(results)
        experience_id = None
        if passed:
            record = self.memory.record_experience(
                "local_programming_training", "python",
                "preflight_sandbox_conversation_benchmark",
                True, 1.0, 1)
            experience_id = record.experience_id
        return TrainingSession(
            passed, len(results), passed_count, experience_id, results)