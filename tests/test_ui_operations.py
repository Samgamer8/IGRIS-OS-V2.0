from igris_os.ui.operations import ApprovalQueue, DeliverableRegistry


def test_approval_queue_add_approve_and_reject():
    queue = ApprovalQueue()
    approval = queue.add("crea un juego", "games.godot.scaffold",
                         "write_workspace")
    assert queue.pending_count() == 1
    assert queue.pending()[0].objective == "crea un juego"
    assert queue.pending()[0].capability == "games.godot.scaffold"
    rejected = queue.add("borra algo", "x", "destructive")
    assert queue.reject(rejected.id).id == rejected.id
    assert queue.pending_count() == 1
    approved = queue.approve(approval.id)
    assert approved.id == approval.id
    assert queue.pending_count() == 0
    assert queue.clear() == 0


def test_approval_queue_unknown_id_returns_none():
    queue = ApprovalQueue()
    queue.add("x", "y")
    assert queue.approve("inexistente") is None
    assert queue.reject("inexistente") is None


def test_approval_queue_clear_returns_count():
    queue = ApprovalQueue()
    queue.add("a", "y")
    queue.add("b", "y")
    assert queue.clear() == 2
    assert queue.pending_count() == 0


def test_deliverable_registry_records_only_existing_paths(tmp_path):
    registry = DeliverableRegistry()
    existing = tmp_path / "proyecto"
    existing.mkdir()
    assert registry.record("m1", "objetivo", "project",
                           str(existing)) is not None
    assert registry.record("m2", "objetivo", "artifact",
                           str(tmp_path / "no_existe")) is None
    assert registry.count() == 1


def test_deliverable_registry_undo_last(tmp_path):
    registry = DeliverableRegistry()
    first = tmp_path / "a"
    second = tmp_path / "b"
    first.mkdir()
    second.mkdir()
    registry.record("m1", "o", "project", str(first))
    registry.record("m2", "o", "project", str(second))
    last = registry.undo_last()
    assert last.path == str(second)
    assert registry.count() == 1
    assert registry.last().path == str(first)
    assert registry.undo_last().path == str(first)
    assert registry.undo_last() is None


def test_discard_only_within_root(tmp_path):
    root = tmp_path / "missions"
    root.mkdir()
    inside = root / "m1" / "output"
    inside.mkdir(parents=True)
    (inside / "x.txt").write_text("datos", encoding="utf-8")
    outside = tmp_path / "fuera"
    outside.mkdir()
    registry = DeliverableRegistry()
    item = registry.record("m1", "o", "project", str(inside))
    assert registry.discard(item, root) is True
    assert not inside.exists()
    item2 = registry.record("m2", "o", "project", str(outside))
    assert registry.discard(item2, root) is False
    assert outside.exists()
