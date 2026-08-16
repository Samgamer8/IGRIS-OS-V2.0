from __future__ import annotations

import traceback
from typing import Any

from igris_os.application.mission_queue import MissionQueue, QueuedMission
from igris_os.application.kernel import IgrisKernel
from igris_os.domain.models import Mission, ExecutionResult


class MissionRunner:
    def __init__(
        self,
        mission_queue: MissionQueue,
        kernel: IgrisKernel,
        assistant: Any,
        executor: Any,
        chat: Any,
    ) -> None:
        self.mission_queue = mission_queue
        self.kernel = kernel
        self.assistant = assistant
        self.executor = executor
        self.chat = chat
        self.active_job: QueuedMission | None = None

    def dispatch_next(self) -> None:
        try:
            self._dispatch_next_impl()
        except Exception as exc:
            traceback.print_exc()
            self.chat.append(f"\n[SISTEMA] Error en dispatch: {exc}")
            self.active_job = None

    def _dispatch_next_impl(self) -> None:
        if self.active_job is not None:
            return
        job = self.mission_queue.next()
        if job is None:
            return
        self.active_job = job
        self.executor.submit(self._run_job_thread, job)

    def run_job(self, job: QueuedMission) -> Any:
        def report_progress(percent: int, message: str) -> None:
            try:
                self.mission_queue.update_progress(job.id, percent, message)
            except (KeyError, ValueError):
                pass

        try:
            if job.kind == "capability":
                reply = self.kernel.execute(
                    Mission(job.objective),
                    job.capability,
                    job.payload,
                    approval=job.payload.get("__approval"),
                    on_progress=report_progress,
                )
            elif job.kind == "agentic":
                context = ""
                reply = self.assistant.respond_agentic(job.objective, context)
            else:
                context = ""
                reply = self.assistant.respond(job.objective, context)
        except Exception as exc:
            reply = ExecutionResult.failure(
                str(exc), "PANEL_ERROR",
                stack_trace=traceback.format_exc(),
            )
        return reply

    def _run_job_thread(self, job: QueuedMission) -> None:
        try:
            reply = self.run_job(job)
            self.mission_queue.finish(
                job.id,
                reply.ok if hasattr(reply, "ok") else True,
                getattr(reply, "message", ""),
            )
        except Exception as exc:
            traceback.print_exc()
            self.mission_queue.finish(job.id, False, str(exc))
        finally:
            self.active_job = None
