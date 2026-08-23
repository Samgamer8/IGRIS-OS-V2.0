import json

import pytest

from igris_os.files import RepositoryStager


def test_staging_copies_without_modifying_source(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    original = source / "app.py"
    original.write_text("value = 1\n", encoding="utf-8")
    result = RepositoryStager(tmp_path / "workspace").stage(
        source, confirmed=True)
    staged = __import__("pathlib").Path(result.root) / "app.py"
    assert staged.read_text(encoding="utf-8") == "value = 1\n"
    staged.write_text("value = 2\n", encoding="utf-8")
    assert original.read_text(encoding="utf-8") == "value = 1\n"
    manifest = json.loads(
        __import__("pathlib").Path(result.manifest).read_text(encoding="utf-8"))
    assert manifest["source_modified"] is False
    assert result.verified


def test_staging_requires_confirmation(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    with pytest.raises(PermissionError):
        RepositoryStager(tmp_path / "workspace").stage(source)


def test_staging_skips_symlinks_when_supported(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("secret", encoding="utf-8")
    link = source / "link.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("Symlinks no disponibles")
    result = RepositoryStager(tmp_path / "workspace").stage(
        source, confirmed=True)
    assert result.files == 0
