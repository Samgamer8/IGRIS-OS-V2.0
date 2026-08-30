import json

from igris_os.cli import main


def complete_project(root):
    (root / "tests").mkdir()
    (root / "README.md").write_text("# app", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        "[project]\nname='cli-app'\nversion='1.0.0'\n", encoding="utf-8")
    (root / "tests" / "test_app.py").write_text(
        "def test_ok(): assert True\n", encoding="utf-8")


def test_cli_verify_stops_before_permission(tmp_path, capsys):
    complete_project(tmp_path)
    code = main(["verify", "--project", str(tmp_path)])
    payload = json.loads(capsys.readouterr().out)
    assert code == 2
    assert payload["code"] == "PERMISSION_REQUIRED"
    assert not (tmp_path / "IGRIS_DELIVERY_REPORT.json").exists()


def test_cli_verify_executes_after_explicit_permission(tmp_path, capsys):
    complete_project(tmp_path)
    code = main([
        "verify", "--project", str(tmp_path), "--approve-execution"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["ok"] is True
    assert payload["sandboxed"] is True
    assert (tmp_path / "IGRIS_DELIVERY_REPORT.json").is_file()


def test_program_command_stops_without_permission(capsys):
    code = main(["program", "crea una calculadora"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 2
    assert payload["code"] == "PERMISSION_REQUIRED"
