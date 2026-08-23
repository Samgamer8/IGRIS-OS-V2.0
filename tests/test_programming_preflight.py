from igris_os.programming.preflight import ProgrammingPreflight


def test_preflight_reports_syntax_risk_and_tests(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "app.py").write_text("value = eval('1')\n", encoding="utf-8")
    (root / "test_app.py").write_text("def test_value():\n    assert True\n", encoding="utf-8")

    report = ProgrammingPreflight().inspect(root)

    assert report.ok
    assert report.files == 2
    assert report.python_files == 2
    assert report.test_files == 1
    assert any(item.category == "security" for item in report.findings)


def test_preflight_marks_invalid_python_critical(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "broken.py").write_text("def broken(:\n", encoding="utf-8")

    report = ProgrammingPreflight().inspect(root)

    assert not report.ok
    assert any(item.severity == "critical" for item in report.findings)


def test_preflight_excludes_generated_directories(tmp_path):
    root = tmp_path / "project"
    (root / "dist").mkdir(parents=True)
    (root / "dist" / "broken.py").write_text("def broken(:\n", encoding="utf-8")

    report = ProgrammingPreflight(max_files=1).inspect(root)

    assert report.files == 0
    assert report.findings == ()


def test_preflight_accepts_python_utf8_bom(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "bom.py").write_text("print('ok')\n", encoding="utf-8-sig")

    report = ProgrammingPreflight().inspect(root)

    assert not any(item.category == "syntax" for item in report.findings)


def test_preflight_does_not_flag_regular_object_exec_method(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "app.py").write_text("dialog.exec()\n", encoding="utf-8")

    report = ProgrammingPreflight().inspect(root)

    assert not any(item.category == "security" for item in report.findings)