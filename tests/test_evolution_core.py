from pathlib import Path

from igris_os.evolution.evolution_core import EvolutionCore, EvolutionPatch


def _patch(path: Path, old: str, new: str) -> EvolutionPatch:
    return EvolutionPatch(path, old, new, "verified reliability fix", "feature-1")


def test_evolution_requires_verifier_and_leaves_source_untouched(tmp_path: Path) -> None:
    target = tmp_path / "module.py"
    target.write_text("VALUE = 1\n", encoding="utf-8")
    result = EvolutionCore(tmp_path).evolve([_patch(target, "VALUE = 1\n", "VALUE = 2\n")])

    assert result.ok is False
    assert result.applied_patches == []
    assert target.read_text(encoding="utf-8") == "VALUE = 1\n"


def test_verified_patch_records_relative_snapshot_and_waits_for_promotion(tmp_path: Path) -> None:
    target = tmp_path / "src" / "module.py"
    target.parent.mkdir()
    target.write_text("VALUE = 1\n", encoding="utf-8")
    root = tmp_path
    observed = []

    result = EvolutionCore(root).evolve(
        [_patch(target, "VALUE = 1\n", "VALUE = 2\n")],
        verifier=lambda project: observed.append(project / "src" / "module.py") is None
        and (project / "src" / "module.py").read_text(encoding="utf-8") == "VALUE = 2\n",
    )

    assert result.ok is True
    assert result.rollback_performed is False
    assert "pendiente de promoción explícita" in result.message
    assert observed == [target]
    assert (tmp_path / ".evolution_backups" / result.snapshot_id / "src" / "module.py").read_text(encoding="utf-8") == "VALUE = 1\n"


def test_failed_external_verification_restores_entire_patch_batch(tmp_path: Path) -> None:
    first = tmp_path / "a" / "same.py"
    second = tmp_path / "b" / "same.py"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text("VALUE = 'a'\n", encoding="utf-8")
    second.write_text("VALUE = 'b'\n", encoding="utf-8")
    patches = [
        _patch(first, "VALUE = 'a'\n", "VALUE = 'A'\n"),
        _patch(second, "VALUE = 'b'\n", "VALUE = 'B'\n"),
    ]

    result = EvolutionCore(tmp_path).evolve(patches, verifier=lambda _: False)

    assert result.ok is False
    assert result.rollback_performed is True
    assert first.read_text(encoding="utf-8") == "VALUE = 'a'\n"
    assert second.read_text(encoding="utf-8") == "VALUE = 'b'\n"
    assert "attention" not in result.message


def test_patch_rejects_outside_and_protected_panel_paths(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    core = EvolutionCore(root)
    external = tmp_path / "outside.py"
    external.write_text("x=1\n", encoding="utf-8")
    panel = root / "src" / "igris_os" / "ui" / "cinematic.py"
    panel.parent.mkdir(parents=True)
    panel.write_text("panel\n", encoding="utf-8")

    assert core.apply_patch(_patch(external, "x=1\n", "x=2\n")) is False
    assert core.apply_patch(_patch(panel, "panel\n", "changed\n")) is False
    assert external.read_text(encoding="utf-8") == "x=1\n"
    assert panel.read_text(encoding="utf-8") == "panel\n"


def test_snapshot_ids_are_unique_and_nested_paths_do_not_collide(tmp_path: Path) -> None:
    first = tmp_path / "one" / "config.py"
    second = tmp_path / "two" / "config.py"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text("ONE\n", encoding="utf-8")
    second.write_text("TWO\n", encoding="utf-8")
    core = EvolutionCore(tmp_path)

    snapshot_a = core.create_snapshot([first, second])
    snapshot_b = core.create_snapshot([first, second])
    directory = tmp_path / ".evolution_backups" / snapshot_a

    assert snapshot_a != snapshot_b
    assert (directory / "one" / "config.py").read_text(encoding="utf-8") == "ONE\n"
    assert (directory / "two" / "config.py").read_text(encoding="utf-8") == "TWO\n"

