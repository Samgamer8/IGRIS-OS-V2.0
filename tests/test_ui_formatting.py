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
    # Independiente del nombre de la carpeta: el runtime debe vivir junto
    # al paquete fuente (proyecto/src/igris_os).
    assert (runtime_root().parent / "src" / "igris_os").is_dir()


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


def test_repository_map_is_human_readable():
    rendered = format_result({"repository": {
        "files": 12, "symbols": 30, "tests": 4,
        "languages": {"python": 10, "javascript": 2},
        "matches": [{"path": "src/app.py"}], "manifest": "map.json"}})
    assert "MAPA DEL REPOSITORIO" in rendered
    assert "src/app.py" in rendered
    assert "map.json" in rendered


def test_staged_repository_is_human_readable():
    rendered = format_result({"staged_repository": {
        "files": 20, "total_bytes": 4000, "root": "workspace/repository",
        "manifest": "staging.json", "verified": True}})
    assert "COPIA AISLADA VERIFICADA" in rendered
    assert "workspace/repository" in rendered


def test_repository_changes_explain_original_is_safe():
    rendered = format_result({"repository_changes": {
        "changed_files": ["app.py"], "report": "changes.diff",
        "original_modified": False}})
    assert "CAMBIOS PROPUESTOS" in rendered
    assert "Sin modificar" in rendered
