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
