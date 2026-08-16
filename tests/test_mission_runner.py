from pathlib import Path

from igris_os.application import CapabilityRegistry, IgrisKernel
from igris_os.application.mission_queue import MissionQueue
from igris_os.domain import ActionRisk, CapabilitySpec, ExecutionResult, Mission
from igris_os.security import PermissionPolicy
from igris_os.storage.audit import AuditLog
from igris_os.storage.workspace import MissionWorkspace
from igris_os.ui.mission_runner import MissionRunner


class SyncExecutor:
    def submit(self, fn, *args):
        return fn(*args)


class FakeChat:
    def __init__(self):
        self.lines = []

    def append(self, line):
        self.lines.append(line)


class FakeAssistant:
    def respond(self, objective, context):
        return ExecutionResult.success(f"respondido: {objective}")

    def respond_agentic(self, objective, context):
        return self.respond(objective, context)


def build_context(tmp_path: Path):
    registry = CapabilityRegistry()
    kernel = IgrisKernel(
        registry, PermissionPolicy(),
        AuditLog(tmp_path / "audit.jsonl"),
        MissionWorkspace(tmp_path / "missions"))
    queue = MissionQueue(tmp_path / "missions_queue.json")
    return registry, kernel, queue


def test_runner_executes_capability_with_approval_token(tmp_path):
    registry, kernel, queue = build_context(tmp_path)
    registry.register(
        CapabilitySpec("write", "escribe", ActionRisk.WRITE_WORKSPACE),
        lambda request: ExecutionResult.success("escrito"))

    objective = "crea archivo"
    payload = {"__approval": kernel.issue_approval(objective, "write")}
    queue.enqueue(objective, "capability", "write", payload)

    chat = FakeChat()
    runner = MissionRunner(queue, kernel, FakeAssistant(), SyncExecutor(), chat)
    runner.dispatch_next()

    assert queue.summary()["completed"] == 1


def test_runner_marks_capability_without_token_failed(tmp_path):
    registry, kernel, queue = build_context(tmp_path)
    registry.register(
        CapabilitySpec("write", "escribe", ActionRisk.WRITE_WORKSPACE),
        lambda request: ExecutionResult.success("no deberia"))
    queue.enqueue("objetivo", "capability", "write", {})

    runner = MissionRunner(queue, kernel, FakeAssistant(), SyncExecutor(), FakeChat())
    runner.dispatch_next()

    assert queue.summary()["failed"] == 1
    assert queue.summary()["completed"] == 0


def test_runner_chat_uses_assistant(tmp_path):
    registry, kernel, queue = build_context(tmp_path)
    queue.enqueue("explica algo", "chat")

    runner = MissionRunner(queue, kernel, FakeAssistant(), SyncExecutor(), FakeChat())
    runner.dispatch_next()

    assert queue.summary()["completed"] == 1


def test_runner_handles_capability_crash_without_failing_thread(tmp_path):
    registry, kernel, queue = build_context(tmp_path)
    registry.register(
        CapabilitySpec("boom", "estalla", ActionRisk.READ_ONLY),
        lambda request: (_ for _ in ()).throw(RuntimeError("boom")))

    queue.enqueue("prueba", "capability", "boom", {})
    chat = FakeChat()
    runner = MissionRunner(queue, kernel, FakeAssistant(), SyncExecutor(), chat)
    runner.dispatch_next()

    assert queue.summary()["failed"] == 1
