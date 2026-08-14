import json

import pytest

from igris_os.application import MissionQueue


def test_queue_persists_lifecycle(tmp_path):
    path = tmp_path / "queue.json"
    queue = MissionQueue(path)
    created = queue.enqueue("analiza proyecto", "capability",
                            "repository.analyze", {"root": "demo"})
    running = queue.next()
    assert running.id == created.id
    assert running.state == "running"
    queue.finish(running.id, True, "terminada")
    restored = MissionQueue(path)
    assert restored.summary()["completed"] == 1
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document[0]["message"] == "terminada"


def test_running_job_is_recovered_after_restart(tmp_path):
    path = tmp_path / "queue.json"
    queue = MissionQueue(path)
    queue.enqueue("continua", "chat")
    queue.next()
    recovered = MissionQueue(path)
    assert recovered.summary()["pending"] == 1
    assert recovered.next().attempts == 2


def test_cancel_only_affects_pending_jobs(tmp_path):
    queue = MissionQueue(tmp_path / "queue.json")
    queue.enqueue("uno", "chat")
    queue.enqueue("dos", "chat")
    queue.next()
    assert queue.cancel_pending() == 1
    summary = queue.summary()
    assert summary["running"] == 1
    assert summary["cancelled"] == 1


def test_corrupt_queue_recovers_empty(tmp_path):
    path = tmp_path / "queue.json"
    path.write_text("not json", encoding="utf-8")
    assert MissionQueue(path).summary()["pending"] == 0


def test_progress_is_monotonic_and_cancellation_is_persisted(tmp_path):
    path = tmp_path / "queue.json"
    queue = MissionQueue(path)
    job = queue.enqueue("larga", "chat")
    queue.next()
    queue.update_progress(job.id, 25, "analizando")
    queue.update_progress(job.id, 20)
    assert queue.request_active_cancellation()
    assert queue.cancellation_requested(job.id)
    assert queue.cancel_at_safe_point(job.id)
    assert queue.summary()["cancelled"] == 1
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document[0]["progress"] == 100
    assert document[0]["state"] == "cancelled"
    assert document[0]["cancellation_requested"] is True
    with pytest.raises(ValueError):
        queue.update_progress(job.id, 101)
