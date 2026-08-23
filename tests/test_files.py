import pytest

from igris_os.files import FileIndexer


def test_index_and_read(tmp_path):
    (tmp_path / "a.txt").write_text("hola", encoding="utf-8")
    item = FileIndexer(tmp_path).scan()[0]
    assert item.path == "a.txt"
    assert item.sha256
    assert FileIndexer(tmp_path).read_text("a.txt") == "hola"


def test_path_escape_is_blocked(tmp_path):
    with pytest.raises(ValueError):
        FileIndexer(tmp_path).read_text("../secret.txt")
