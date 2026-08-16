from pathlib import Path

from igris_os.application import RuntimeProbe


def test_probe_reports_system_tools_external(tmp_path):
    probe = RuntimeProbe(tmp_path)
    statuses = probe.probe()
    assert "python" in statuses
    assert statuses["python"].available
    assert statuses["python"].state in ("internal", "external")


def test_probe_detects_bundled_tool_as_internal(tmp_path):
    godot_dir = tmp_path / ".tools" / "godot"
    godot_dir.mkdir(parents=True)
    fake = godot_dir / "Godot_v4.7.1-stable_win64.exe"
    fake.write_bytes(b"x")
    probe = RuntimeProbe(tmp_path)
    status = probe.probe()["godot"]
    assert status.state == "internal"
    assert status.path == str(fake)


def test_probe_missing_when_nothing_bundled(tmp_path):
    probe = RuntimeProbe(tmp_path)
    status = probe.probe()["ollama"]
    assert status.state in ("internal", "external", "missing")
    assert status.path == "" or Path(status.path).exists()


def test_probe_missing_list_and_summary(tmp_path):
    probe = RuntimeProbe(tmp_path)
    missing = probe.missing()
    assert isinstance(missing, list)
    assert all(not item.available for item in missing)
    summary = probe.summary()
    assert "FALTA" in summary or "SYS" in summary or "EMP" in summary


def test_catalogue_has_k3_llm_runtime():
    names = [spec.name for spec in RuntimeProbe.TOOLS]
    assert "k3" in names
    spec = RuntimeProbe.TOOLS[names.index("k3")]
    assert spec.category == "llm"
    assert "k3.exe" in spec.bundled

