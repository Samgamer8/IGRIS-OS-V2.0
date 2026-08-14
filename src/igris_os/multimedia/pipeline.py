import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from igris_os.multimedia.engine import MediaEngine, MediaResult
from igris_os.tools import safe_output


@dataclass(frozen=True, slots=True)
class PipelineResult:
    ok: bool
    message: str
    outputs: tuple[str, ...] = ()
    report: str = ""
    rolled_back: bool = False


class MediaPipeline:
    def __init__(self, workspace: Path,
                 engine_factory: Callable[[Path], MediaEngine] = MediaEngine) -> None:
        self.workspace = workspace.resolve()
        self.engine = engine_factory(self.workspace)

    def execute(self, source: Path, operations: list[dict], *,
                confirmed: bool = False,
                on_progress: Callable[[int, str], None] | None = None) -> PipelineResult:
        if not confirmed:
            return PipelineResult(False, "Se necesita confirmacion")
        if not source.is_file() or source.is_symlink():
            return PipelineResult(False, "Archivo fuente no disponible")
        if not operations or len(operations) > 8:
            return PipelineResult(False, "Plan multimedia invalido")
        created: list[Path] = []
        evidence = []
        for index, operation in enumerate(operations, 1):
            kind = str(operation.get("kind", ""))
            output = str(operation.get("output", f"paso_{index}.bin"))
            if on_progress:
                on_progress(int(100 * (index - 1) / len(operations)),
                            f"Paso {index}/{len(operations)}: {kind}")
            try:
                target = safe_output(self.workspace, output)
            except ValueError as exc:
                return self._failure(str(exc), evidence, created)
            result = self._run(kind, source, output, operation)
            evidence.append({"step": index, "kind": kind, "ok": result.ok,
                             "message": result.message,
                             "output": result.output})
            if not result.ok:
                return self._failure(result.message, evidence, created)
            if target.is_file():
                created.append(target)
        if on_progress:
            on_progress(98, "Generando informe")
        report = self._report(True, evidence, False)
        if on_progress:
            on_progress(100, "Plan multimedia completado")
        return PipelineResult(True, "Plan multimedia completado",
                              tuple(str(path) for path in created),
                              str(report), False)

    def _run(self, kind: str, source: Path, output: str,
             operation: dict) -> MediaResult:
        if kind == "thumbnail":
            return self.engine.thumbnail(
                source, output, float(operation.get("second", 0)),
                confirmed=True)
        if kind == "extract_audio":
            return self.engine.extract_audio(source, output, confirmed=True)
        if kind == "transcode":
            return self.engine.transcode(source, output, confirmed=True)
        if kind == "trim":
            return self.engine.trim(
                source, output, float(operation.get("start", 0)),
                float(operation.get("duration", 10)), confirmed=True)
        return MediaResult(False, "Operacion multimedia no permitida")

    def _failure(self, message: str, evidence: list[dict],
                 created: list[Path]) -> PipelineResult:
        rolled_back = False
        for path in reversed(created):
            if (path.is_file() and not path.is_symlink() and
                    path.resolve().is_relative_to(self.workspace)):
                path.unlink()
                rolled_back = True
        report = self._report(False, evidence, rolled_back)
        return PipelineResult(False, message, (), str(report), rolled_back)

    def _report(self, ok: bool, evidence: list[dict], rolled_back: bool) -> Path:
        path = safe_output(self.workspace, "logs/media_pipeline.json")
        path.write_text(json.dumps(
            {"ok": ok, "rolled_back": rolled_back, "steps": evidence},
            ensure_ascii=False, indent=2), encoding="utf-8")
        return path
