from igris_os.programming import EngineeringAssessor


def test_assessment_separates_facts_risks_doubts_and_tests(tmp_path):
    (tmp_path / "app.py").write_text("value = eval('1')\n", encoding="utf-8")
    (tmp_path / "test_app.py").write_text(
        "def test_value():\n    assert True\n", encoding="utf-8")

    assessment = EngineeringAssessor().assess(tmp_path, "revisar seguridad")

    assert assessment.facts[0].startswith("Proyecto:")
    assert assessment.risks[0].category == "security"
    assert assessment.doubts == ()
    assert "No modificar la fuente original" in assessment.proposal
    assert assessment.required_tests


def test_assessment_blocks_critical_project(tmp_path):
    (tmp_path / "broken.py").write_text("def broken(:\n", encoding="utf-8")

    assessment = EngineeringAssessor().assess(tmp_path, "corregir sintaxis")

    assert not assessment.can_proceed
    assert assessment.risks[0].severity == "critical"