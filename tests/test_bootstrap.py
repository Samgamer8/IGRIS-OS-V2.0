from igris_os.bootstrap import build_igris
from igris_os.domain import Mission


def test_health_capability(tmp_path):
    result = build_igris(tmp_path).execute(Mission("estado"), "system.health")
    assert result.ok
    assert result.message == "Nucleo operativo"
    assert "cpu_percent" in result.data
    assert "memory_percent" in result.data
