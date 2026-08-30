from pathlib import Path

from igris_os.ui.control_center import load_programs, save_programs, system_snapshot


def test_academy_registry_round_trip(tmp_path: Path):
    programs = [{"name": "Editor", "path": str(tmp_path / "editor.exe")}]

    save_programs(tmp_path, programs)

    assert load_programs(tmp_path) == programs


def test_system_snapshot_reports_real_percentages():
    snapshot = system_snapshot()

    assert 0 <= snapshot["cpu"] <= 100
    assert 0 <= snapshot["memory"] <= 100
    assert 0 <= snapshot["disk"] <= 100
    assert snapshot["python"]
    assert snapshot["platform"]
