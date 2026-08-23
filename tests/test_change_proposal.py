from igris_os.programming import ChangeProposalBuilder


def test_proposal_reports_risk_without_writing(tmp_path):
    source = tmp_path / "app.py"
    source.write_text("value = eval('1')\n", encoding="utf-8")

    proposal = ChangeProposalBuilder().build(tmp_path, "revisar seguridad")

    assert proposal.requires_confirmation
    assert proposal.can_apply
    assert proposal.affected_files == ("app.py",)
    assert proposal.risks
    assert proposal.tests
    assert source.read_text(encoding="utf-8") == "value = eval('1')\n"


def test_critical_preflight_blocks_change_proposal(tmp_path):
    (tmp_path / "broken.py").write_text("def broken(:\n", encoding="utf-8")

    proposal = ChangeProposalBuilder().build(tmp_path, "corregir sintaxis")

    assert not proposal.can_apply
    assert proposal.changes == (
        "Resolver primero los bloqueos críticos del preflight",)