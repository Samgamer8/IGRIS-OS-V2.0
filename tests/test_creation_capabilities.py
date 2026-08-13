from igris_os.bootstrap import build_igris
from igris_os.domain import Mission


def test_godot_capability_requires_kernel_confirmation(tmp_path):
    kernel = build_igris(tmp_path)
    denied = kernel.execute(Mission("juego"), "games.godot.scaffold",
                            {"name": "Demo"})
    allowed = kernel.execute(Mission("juego"), "games.godot.scaffold",
                             {"name": "Demo"}, confirmed=True)
    assert denied.code == "CONFIRMATION_REQUIRED"
    assert allowed.ok


def test_creation_catalog_is_visible(tmp_path):
    names = {spec.name for spec in build_igris(tmp_path).registry.specs()}
    assert "programming.python.develop" in names
    assert "multimedia.status" in names
    assert "image.resize" in names
    assert "multimedia.extract_audio" in names
    assert "multimedia.thumbnail" in names
    assert "multimedia.transcode" in names
    assert "files.inspect" in names


def test_resize_capability_processes_attached_image(tmp_path):
    from PIL import Image

    source = tmp_path / "source.png"
    Image.new("RGB", (100, 80), "red").save(source)
    kernel = build_igris(tmp_path / "runtime")
    result = kernel.execute(
        Mission("redimensiona"), "image.resize",
        {"source": str(source), "output": "result.png",
         "width": 40, "height": 40}, confirmed=True)
    assert result.ok
    assert result.data["output"].endswith("result.png")


def test_inspect_files_returns_hash_and_text_preview(tmp_path):
    source = tmp_path / "code.py"
    source.write_text("print('IGRIS')", encoding="utf-8")
    kernel = build_igris(tmp_path / "runtime")
    result = kernel.execute(
        Mission("analiza"), "files.inspect", {"sources": [str(source)]})
    assert result.ok
    item = result.data["files"][0]
    assert item["name"] == "code.py"
    assert item["preview"] == "print('IGRIS')"
    assert len(item["sha256"]) == 64


def test_inspect_files_caps_file_count(tmp_path):
    sources = []
    for index in range(55):
        path = tmp_path / f"{index}.txt"
        path.write_text("x", encoding="utf-8")
        sources.append(str(path))
    result = build_igris(tmp_path / "runtime").execute(
        Mission("analiza"), "files.inspect", {"sources": sources})
    assert result.ok
    assert len(result.data["files"]) == 50
