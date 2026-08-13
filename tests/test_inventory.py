import json

from igris_os.storage.source_inventory import inventory_source, write_inventory


def test_inventory_hashes_and_excludes_build(tmp_path):
    (tmp_path / "keep.txt").write_text("IGRIS", encoding="utf-8")
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "skip.txt").write_text("skip", encoding="utf-8")
    result = inventory_source(tmp_path)
    assert result["file_count"] == 1
    assert result["files"][0]["sha256"]


def test_large_file_is_not_hashed(tmp_path):
    (tmp_path / "large.bin").write_bytes(b"12345")
    assert inventory_source(tmp_path, max_hash_bytes=2)["files"][0]["status"] == "too_large"


def test_inventory_json(tmp_path):
    source, output = tmp_path / "source", tmp_path / "manifest.json"
    source.mkdir()
    (source / "a.py").write_text("pass", encoding="utf-8")
    write_inventory([source], output)
    assert json.loads(output.read_text(encoding="utf-8"))["schema"] == 1
