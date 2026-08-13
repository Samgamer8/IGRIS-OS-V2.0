import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Evaluation:
    candidate: str
    baseline_score: float
    candidate_score: float
    tests_passed: bool

    @property
    def promotable(self) -> bool:
        return self.tests_passed and self.candidate_score > self.baseline_score


class EvolutionLab:
    def __init__(self, root: Path) -> None:
        self.root = root

    def record(self, evaluation: Evaluation) -> Path:
        if not 0 <= evaluation.baseline_score <= 100 or not 0 <= evaluation.candidate_score <= 100:
            raise ValueError("Puntuacion invalida")
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"{evaluation.candidate}.json"
        path.write_text(json.dumps({**asdict(evaluation),
                                    "promotable": evaluation.promotable}, indent=2),
                        encoding="utf-8")
        return path
