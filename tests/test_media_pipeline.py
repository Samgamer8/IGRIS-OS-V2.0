import json
from pathlib import Path

from igris_os.multimedia import MediaEngine, MediaPipeline, MediaResult


class FakeEngine:
    fail_kind = ""

    def __init__(self, workspace):
        self.workspace = Path(workspace)

    def _result(self, kind, output):
        if kind == self.fail_kind:
            return MediaResult(False, "fallo simulado")
        target = self.workspace / output
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"ok")
        return MediaResult(True, "ok", str(target))

    def thumbnail(self, source, output, second=0, confirmed=False):
        return self._result("thumbnail", output)

    def transcode(self, source, output, confirmed=False):
        return self._result("transcode", output)

    def extract_audio(self, source, output, confirmed=False):
        return self._result("extract_audio", output)

    def trim(self, source, output, start, duration, confirmed=False):
        return self._result("trim", output)


def test_pipeline_delivers_outputs_and_evidence(tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    workspace = tmp_path / "workspace"
    result = MediaPipeline(workspace, FakeEngine).execute(source, [
        {"kind": "thumbnail", "output": "preview.png"},
        {"kind": "transcode", "output": "final.mp4"},
    ], confirmed=True)
    assert result.ok
    assert len(result.outputs) == 2
    report = json.loads(Path(result.report).read_text(encoding="utf-8"))
    assert report["ok"]
    assert len(report["steps"]) == 2


def test_pipeline_rolls_back_outputs_when_later_step_fails(tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    workspace = tmp_path / "workspace"

    class FailingEngine(FakeEngine):
        fail_kind = "transcode"

    result = MediaPipeline(workspace, FailingEngine).execute(source, [
        {"kind": "thumbnail", "output": "preview.png"},
        {"kind": "transcode", "output": "final.mp4"},
    ], confirmed=True)
    assert not result.ok
    assert result.rolled_back
    assert not (workspace / "preview.png").exists()
    assert Path(result.report).is_file()


def test_pipeline_rejects_path_escape(tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    result = MediaPipeline(tmp_path / "workspace", FakeEngine).execute(
        source, [{"kind": "thumbnail", "output": "../escape.png"}],
        confirmed=True)
    assert not result.ok
    assert not (tmp_path / "escape.png").exists()


def test_trim_validates_interval_without_running_ffmpeg(tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    result = MediaEngine(tmp_path).trim(
        source, "out.mp4", -1, 5, confirmed=True)
    assert not result.ok
