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


def test_engineering_assessment_is_human_readable():
    rendered = format_result({
        "facts": ["Archivos inspeccionados: 3"],
        "risks": [{"severity": "high", "path": "app.py"}],
        "doubts": ["Falta definir el objetivo"],
        "required_tests": ["pytest"],
        "proposal": ["Trabajar en una copia aislada"],
    })
    assert "DIAGNOSTICO TECNICO" in rendered
    assert "Archivos inspeccionados" in rendered
    assert "Falta definir" in rendered
    assert "copia aislada" in rendered


def test_change_proposal_is_human_readable():
    rendered = format_result({
        "affected_files": ["app.py"],
        "changes": ["Aplicar cambio mínimo"],
        "risks": ["high: app.py: eval"],
        "tests": ["pytest"],
        "requires_confirmation": True,
    })
    assert "PROPUESTA DE CAMBIOS" in rendered
    assert "app.py" in rendered
    assert "CONFIRMACION REQUERIDA" in rendered


def test_project_delivery_lists_files_and_verification(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("print('ok')", encoding="utf-8")
    (project / "test_main.py").write_text("def test_ok(): pass", encoding="utf-8")
    (project / "VERIFICATION.json").write_text("{}", encoding="utf-8")

    rendered = format_result({"project": str(project)})

    assert "PROYECTO ENTREGADO" in rendered
    assert "main.py" in rendered
    assert "test_main.py" in rendered
    assert "VERIFICATION.json presente" in rendered
    assert "Sin modificar" in rendered


def test_sales_plan_format_shows_calculated_break_even():
    rendered = format_result({"sales_plan": {
        "product": "IGRIS", "audience": "equipos pequeños",
        "channel": "demostraciones", "contribution_margin": 40,
        "break_even_sales": 12,
        "actions": ["Lanzar experimento"],
        "assumptions": ["No es una previsión"],
    }})
    assert "PLAN COMERCIAL" in rendered
    assert "Punto de equilibrio: 12" in rendered


def test_staging_format_requires_separate_delivery_authorization():
    rendered = format_result({"staged_project": "runtime/missions/abc/projects/demo"})
    assert "STAGING VERIFICADO" in rendered
    assert "autorización de entrega" in rendered
