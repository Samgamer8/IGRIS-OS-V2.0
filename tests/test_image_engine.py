from PIL import Image

from igris_os.multimedia import ImageEngine


def test_image_resize_requires_confirmation(tmp_path):
    source = tmp_path / "source.png"
    Image.new("RGB", (100, 50), "red").save(source)
    engine = ImageEngine(tmp_path)
    assert not engine.resize(source, "out.png", 20, 20).ok
    result = engine.resize(source, "output/out.png", 20, 20, confirmed=True)
    assert result.ok
    with Image.open(result.output) as image:
        assert image.size == (20, 10)
