import json

import pytest

from igris_os.voice import VoiceDatasetRecorder, VoiceSample


def test_manifest_records_explicit_owner_consent(tmp_path):
    recorder = VoiceDatasetRecorder(tmp_path, "microfono")
    path = recorder.save_manifest([
        VoiceSample(1, "hola", str(tmp_path / "1.wav"), 2.0, True)])
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["speaker_consent"] is True
    assert document["purpose"].startswith("voz original")
    assert document["format"]["sample_rate"] == 24000


def test_invalid_recording_is_rejected(tmp_path):
    recorder = VoiceDatasetRecorder(tmp_path, "microfono")
    with pytest.raises(ValueError):
        recorder.record(1, "", 10)
