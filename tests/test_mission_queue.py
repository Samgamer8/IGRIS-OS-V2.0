import json

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
