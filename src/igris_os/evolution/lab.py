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

    def compare(self, candidate: str, baseline: dict[str, float],
                proposed: dict[str, float]) -> Path:
        required = {"tests", "security", "quality", "performance"}
        if set(baseline) != required or set(proposed) != required:
            raise ValueError("Metricas incompletas")
        values = [*baseline.values(), *proposed.values()]
        if any(not 0 <= float(value) <= 100 for value in values):
            raise ValueError("Puntuacion invalida")
        weights = {"tests": 0.4, "security": 0.3,
                   "quality": 0.2, "performance": 0.1}
        baseline_score = sum(float(baseline[key]) * weight
                             for key, weight in weights.items())
        candidate_score = sum(float(proposed[key]) * weight
                              for key, weight in weights.items())
        gates = {"tests": proposed["tests"] >= 95,
                 "security": proposed["security"] >= 95,
                 "improvement": candidate_score >= baseline_score + 2}
        document = {
            "candidate": candidate, "baseline": baseline,
            "proposed": proposed, "baseline_score": baseline_score,
            "candidate_score": candidate_score, "gates": gates,
            "promotable_to_review": all(gates.values()),
            "production_promoted": False,
        }
        safe = "".join(c for c in candidate if c.isalnum() or c in "_-")
        if not safe:
            raise ValueError("Candidato invalido")
        target = self.root / "quarantine" / (safe + ".json")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(document, ensure_ascii=False, indent=2),
                          encoding="utf-8")
        return target

    def reviewable(self) -> list[dict]:
        folder = self.root / "quarantine"
        if not folder.is_dir():
            return []
        results = []
        for path in sorted(folder.glob("*.json")):
            try:
                item = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if item.get("promotable_to_review"):
                results.append(item)
        return results
