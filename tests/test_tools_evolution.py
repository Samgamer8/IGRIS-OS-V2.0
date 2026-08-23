import pytest

from igris_os.evolution import Evaluation, EvolutionLab
from igris_os.tools import safe_output


def test_safe_output_stays_in_workspace(tmp_path):
    assert safe_output(tmp_path, "video/out.mp4").is_relative_to(tmp_path.resolve())
    with pytest.raises(ValueError):
        safe_output(tmp_path, "../out.mp4")


def test_evolution_only_promotes_measured_improvement(tmp_path):
    good = Evaluation("v2", 70, 85, True)
    bad = Evaluation("v3", 90, 80, True)
    assert good.promotable
    assert not bad.promotable
    assert EvolutionLab(tmp_path).record(good).exists()


def test_evolution_gate_requires_tests_security_and_improvement(tmp_path):
    lab = EvolutionLab(tmp_path)
    good = lab.compare(
        "candidate_good",
        {"tests": 90, "security": 95, "quality": 70, "performance": 70},
        {"tests": 100, "security": 100, "quality": 80, "performance": 75})
    bad = lab.compare(
        "candidate_bad",
        {"tests": 95, "security": 95, "quality": 80, "performance": 80},
        {"tests": 90, "security": 100, "quality": 90, "performance": 90})
    assert __import__("json").loads(good.read_text())["promotable_to_review"]
    assert not __import__("json").loads(bad.read_text())["promotable_to_review"]
    assert len(lab.reviewable()) == 1
    assert all(not item["production_promoted"] for item in lab.reviewable())
