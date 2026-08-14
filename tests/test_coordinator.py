import json

from igris_os.application import SpecialistCoordinator
from igris_os.ai import ModelReply


class FakeClient:
    def __init__(self, fail_at=-1):
        self.calls = []
        self.fail_at = fail_at

    def generate(self, prompt, model):
        self.calls.append((prompt, model))
        if len(self.calls) == self.fail_at:
            return ModelReply(False, "", model, "fallo controlado")
        return ModelReply(True, f"informe {len(self.calls)}", model)


def test_specialists_are_cross_reviewed_and_recorded(tmp_path):
    client = FakeClient()
    result = SpecialistCoordinator(client, tmp_path).coordinate(
        "programa una API Python", "coder")
    assert result.complete
    assert len(result.findings) == 3
    assert result.review.role == "revisor_independiente"
    evidence = json.loads(
        (tmp_path / "specialist_coordination.json").read_text(encoding="utf-8"))
    assert evidence["complete"] is True


def test_specialist_failure_prevents_complete_result(tmp_path):
    result = SpecialistCoordinator(FakeClient(fail_at=2), tmp_path).coordinate(
        "crea un videojuego", "coder")
    assert not result.complete
    assert not result.findings[1].ok
