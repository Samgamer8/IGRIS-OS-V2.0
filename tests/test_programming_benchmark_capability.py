from igris_os.bootstrap import build_igris
from igris_os.domain import Mission


def test_programming_benchmark_capability_is_local(tmp_path):
    result = build_igris(tmp_path / "runtime").execute(
        Mission("evalua programacion"), "programming.benchmark")

    assert result.ok
    assert result.data["passed"] is True
    assert result.data["passed_count"] == result.data["total"]