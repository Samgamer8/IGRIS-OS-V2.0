from igris_os.bootstrap import build_igris
from igris_os.domain import Mission


def test_godot_capability_requires_kernel_confirmation(tmp_path):
    kernel = build_igris(tmp_path)
    mission = Mission("juego")
    denied = kernel.execute(mission, "games.godot.scaffold", {"name": "Demo"})
    token = kernel.issue_approval(mission.objective, "games.godot.scaffold")
    allowed = kernel.execute(mission, "games.godot.scaffold",
                             {"name": "Demo"}, approval=token)
    assert denied.code == "CONFIRMATION_REQUIRED"
    assert allowed.ok


def test_creation_catalog_is_visible(tmp_path):
    names = {spec.name for spec in build_igris(tmp_path).registry.specs()}
    assert "programming.python.develop" in names
    assert "multimedia.status" in names
    assert "multimedia.verify" in names
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
    mission = Mission("redimensiona")
    token = kernel.issue_approval(mission.objective, "image.resize")
    result = kernel.execute(
        mission, "image.resize",
        {"source": str(source), "output": "result.png",
         "width": 40, "height": 40}, approval=token)
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


def test_verify_capability_detects_blank_image(tmp_path):
    from PIL import Image

    source = tmp_path / "black.png"
    Image.new("RGB", (40, 30), (0, 0, 0)).save(source)
    result = build_igris(tmp_path / "runtime").execute(
        Mission("verifica"), "multimedia.verify", {"source": str(source)})
    assert result.ok
    assert result.data["verified"] is False
    assert result.data["blank"] is True


def test_invalid_pipeline_returns_controlled_evidence(tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    kernel = build_igris(tmp_path / "runtime")
    mission = Mission("edita")
    token = kernel.issue_approval(mission.objective, "multimedia.pipeline")
    result = kernel.execute(
        mission, "multimedia.pipeline",
        {"source": str(source), "operations": [
            {"kind": "no_permitida", "output": "x.bin"}]},
        approval=token)
    assert not result.ok
    assert result.code == "MEDIA_PIPELINE_FAILED"
    assert "report" in result.data
