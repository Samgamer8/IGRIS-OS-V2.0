from pathlib import Path
from unittest.mock import Mock

from igris_os.evolution.self_improver import SelfImprover


SOURCE = "def calculate(value):\n    return value + 1\n"
REPLACEMENT = "def calculate(value):\n    if not isinstance(value, int):\n        raise TypeError('value must be int')\n    return value + 1"


def test_auto_refactor_only_proposes_by_default(tmp_path: Path) -> None:
    source = tmp_path / "module.py"
    source.write_text(SOURCE, encoding="utf-8")
    improver = SelfImprover(tmp_path, client=Mock())
    improver.scan_weaknesses = lambda: [{
        "file": str(source), "line": 2, "issue": "test weakness", "severity": "low"}]
    improver.propose_improvement = lambda _: REPLACEMENT

    result = improver.auto_refactor()

    assert result[0]["proposal"] == REPLACEMENT
    assert result[0]["applied"] is False
    assert source.read_text(encoding="utf-8") == SOURCE
    assert not (tmp_path / ".evolution_backups").exists()


def test_apply_requires_explicit_confirmation_and_external_verifier(tmp_path: Path) -> None:
    source = tmp_path / "module.py"
    source.write_text(SOURCE, encoding="utf-8")
    improver = SelfImprover(tmp_path, client=Mock())

    assert improver.apply_improvement(source, REPLACEMENT, line=2) is False
    assert improver.apply_improvement(
        source, REPLACEMENT, line=2, confirmed=True) is False
    assert source.read_text(encoding="utf-8") == SOURCE


def test_verified_improvement_is_applied_with_snapshot(tmp_path: Path) -> None:
    source = tmp_path / "module.py"
    source.write_text(SOURCE, encoding="utf-8")
    improver = SelfImprover(tmp_path, client=Mock())
    observed = []

    def verifier(root: Path) -> bool:
        observed.append(root)
        return "TypeError" in source.read_text(encoding="utf-8")

    assert improver.apply_improvement(
        source, REPLACEMENT, line=2, confirmed=True, validator=verifier) is True
    assert len(observed) == 1
    assert observed[0] == tmp_path.resolve()
    assert "TypeError" in source.read_text(encoding="utf-8")
    snapshots = list((tmp_path / ".evolution_backups").glob("snap_*/module.py"))
    assert len(snapshots) == 1
    assert snapshots[0].read_text(encoding="utf-8") == SOURCE


def test_failed_verifier_rolls_back_candidate(tmp_path: Path) -> None:
    source = tmp_path / "module.py"
    source.write_text(SOURCE, encoding="utf-8")
    improver = SelfImprover(tmp_path, client=Mock())

    assert improver.apply_improvement(
        source, REPLACEMENT, line=2, confirmed=True, validator=lambda _: False) is False
    assert source.read_text(encoding="utf-8") == SOURCE


def test_replacement_must_preserve_function_name_and_signature(tmp_path: Path) -> None:
    source = tmp_path / "module.py"
    source.write_text(SOURCE, encoding="utf-8")
    improver = SelfImprover(tmp_path, client=Mock())

    assert improver.apply_improvement(
        source, "def changed(other):\n    return other", line=2,
        confirmed=True, validator=lambda _: True) is False
    assert source.read_text(encoding="utf-8") == SOURCE


def test_protected_panel_and_outside_files_are_never_candidates(tmp_path: Path) -> None:
    root = tmp_path / "igris_os"
    panel = root / "ui" / "cinematic.py"
    panel.parent.mkdir(parents=True)
    panel.write_text(SOURCE, encoding="utf-8")
    outside = tmp_path / "outside.py"
    outside.write_text(SOURCE, encoding="utf-8")
    improver = SelfImprover(root, client=Mock())

    assert improver.apply_improvement(
        panel, REPLACEMENT, line=2, confirmed=True, validator=lambda _: True) is False
    assert improver.apply_improvement(
        outside, REPLACEMENT, line=2, confirmed=True, validator=lambda _: True) is False
    assert panel.read_text(encoding="utf-8") == SOURCE
    assert outside.read_text(encoding="utf-8") == SOURCE
