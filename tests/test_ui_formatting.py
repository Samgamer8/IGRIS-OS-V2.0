from igris_os.ui.cinematic import format_result, runtime_root


def test_capabilities_are_human_readable():
    rendered = format_result({"capabilities": [
        {"name": "system.health", "description": "Diagnóstico local",
         "risk": "read_only"}]})
    assert "Diagnóstico local" in rendered
    assert "read_only" not in rendered
    assert "{'" not in rendered


def test_tools_show_availability():
    rendered = format_result({"tools": [
        {"name": "ffmpeg", "available": True},
        {"name": "godot", "available": False}]})
    assert "ffmpeg: disponible" in rendered
    assert "godot: no instalada" in rendered


def test_source_runtime_is_anchored_to_project():
    assert runtime_root().name == "runtime"
    assert runtime_root().parent.name == "IGRIS OS V2.O"


def test_pipeline_outputs_are_human_readable():
    rendered = format_result({
        "outputs": ["preview.png", "final.mp4"], "report": "report.json"})
    assert "PLAN MULTIMEDIA COMPLETADO" in rendered
    assert "final.mp4" in rendered
    assert "report.json" in rendered


def test_pipeline_rollback_is_explained():
    rendered = format_result({"rolled_back": True, "report": "evidence.json"})
    assert "ROLLBACK APLICADO" in rendered
    assert "evidence.json" in rendered
