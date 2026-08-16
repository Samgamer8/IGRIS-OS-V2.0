import shutil
import subprocess
from pathlib import Path

import pytest

pytest.importorskip("PIL")

from igris_os.multimedia import VisualVerifier


def _contentful_image(path: Path) -> None:
    from PIL import Image
    image = Image.new("RGB", (40, 30), (20, 20, 20))
    px = image.load()
    for x in range(40):
        for y in range(30):
            if (x + y) % 4 == 0:
                px[x, y] = (210, 210, 210)
    image.save(path)


def test_missing_image_is_rejected(tmp_path):
    check = VisualVerifier().verify_image(tmp_path / "no.png")
    assert not check.ok


def test_non_image_is_rejected(tmp_path):
    path = tmp_path / "fake.png"
    path.write_text("no soy una imagen", encoding="utf-8")
    check = VisualVerifier().verify_image(path)
    assert not check.ok


def test_blank_image_is_rejected(tmp_path):
    from PIL import Image
    path = tmp_path / "black.png"
    Image.new("RGB", (40, 30), (0, 0, 0)).save(path)
    check = VisualVerifier().verify_image(path)
    assert not check.ok
    assert check.blank


def test_contentful_image_passes(tmp_path):
    path = tmp_path / "ok.png"
    _contentful_image(path)
    check = VisualVerifier().verify_image(path)
    assert check.ok
    assert (check.width, check.height) == (40, 30)
    assert check.std_brightness >= 2.0


def test_reference_matches_itself(tmp_path):
    path = tmp_path / "ok.png"
    _contentful_image(path)
    comparison = VisualVerifier().compare_reference(path, path)
    assert comparison.ok
    assert comparison.similarity > 0.99
    assert comparison.changed_ratio == 0.0


def test_reference_detects_shifted_content(tmp_path):
    from PIL import Image
    reference = tmp_path / "ref.png"
    shifted = tmp_path / "shifted.png"
    image = Image.new("RGB", (80, 60), (20, 20, 20))
    px = image.load()
    for x in range(80):
        for y in range(60):
            if (x + y) % 4 == 0:
                px[x, y] = (220, 220, 220)
    image.save(reference)
    image.crop((8, 0, 80, 60)).save(shifted)
    comparison = VisualVerifier().compare_reference(shifted, reference)
    assert not comparison.ok
    assert comparison.changed_ratio > 0
    assert comparison.diff_bbox is not None


def test_reference_missing_image_is_rejected(tmp_path):
    path = tmp_path / "ok.png"
    _contentful_image(path)
    comparison = VisualVerifier().compare_reference(
        tmp_path / "no.png", path)
    assert not comparison.ok


def test_uniform_top_border_is_flagged(tmp_path):
    from PIL import Image
    path = tmp_path / "borders.png"
    image = Image.new("RGB", (40, 30), (30, 30, 30))
    px = image.load()
    for x in range(40):
        for y in range(4):
            px[x, y] = (255, 255, 255)
    for x in range(40):
        for y in range(4, 30):
            px[x, y] = ((x * 5) % 255, (y * 9) % 255, (x + y) % 255)
    image.save(path)
    check = VisualVerifier().verify_image(path)
    assert check.ok
    assert "top" in check.uniform_borders


def test_verify_dispatches_images(tmp_path):
    path = tmp_path / "ok.png"
    _contentful_image(path)
    assert VisualVerifier().verify(path).ok


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg no disponible")
def test_blank_video_is_rejected(tmp_path):
    video = tmp_path / "black.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi",
         "-i", "color=black:size=64x64:duration=0.5",
         "-pix_fmt", "yuv420p", str(video)],
        capture_output=True, check=True)
    check = VisualVerifier().verify_video(video)
    assert not check.ok
    assert check.blank


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg no disponible")
def test_contentful_video_passes(tmp_path):
    video = tmp_path / "color.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi",
         "-i", "testsrc=size=64x64:duration=0.5",
         "-pix_fmt", "yuv420p", str(video)],
        capture_output=True, check=True)
    check = VisualVerifier().verify_video(video)
    assert check.ok
