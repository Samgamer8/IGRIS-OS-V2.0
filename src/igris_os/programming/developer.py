import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from igris_os.ai import ModelReply
from igris_os.programming.coordinator import AutonomousProgrammingCoordinator
from igris_os.programming.workshop import PythonWorkshop
from igris_os.tools import safe_output


SYSTEM = """Actua como ingeniero senior. Devuelve solo JSON UTF-8 con:
{"name":"nombre","source":"codigo Python completo","tests":"unittest completo",
"readme":"uso"}. Sin markdown. Biblioteca estandar. Sin red, subprocess, eval,
exec, ctypes ni efectos destructivos. Implementa casos limite."""


@dataclass(frozen=True, slots=True)
class DevelopmentResult:
    ok: bool
    message: str
    project: str = ""
    attempts: int = 0


def _package(text: str) -> dict:
    fenced = re.fullmatch(r"\s*```(?:json)?\s*(.*?)\s*```\s*",
                          text, re.DOTALL | re.IGNORECASE)
    value = json.loads(fenced.group(1) if fenced else text, strict=False)
    if not isinstance(value, dict) or not {"name", "source", "tests"} <= value.keys():
        raise ValueError("Paquete incompleto")
    return value


class PythonProjectDeveloper:
    def __init__(self, client, workspace: Path, model: str) -> None:
        self.client = client
        self.workspace = workspace.resolve()
        self.model = model

    def develop(self, objective: str, *, confirmed: bool = False,
                attempts: int = 3,
                on_progress: Callable[[int, str], None] | None = None) -> DevelopmentResult:
        if not confirmed:
            return DevelopmentResult(False, "Se necesita confirmacion")
        if not objective.strip():
            return DevelopmentResult(False, "Falta el objetivo")
        feedback = ""
        last_error = ""
        for attempt in range(1, attempts + 1):
            if on_progress:
                on_progress(int(90 * attempt / attempts),
                            f"Intento {attempt}/{attempts} de generacion")
            prompt = SYSTEM + "\nOBJETIVO:\n" + objective
            if feedback:
                prompt += "\nERROR VERIFICADO ANTERIOR:\n" + feedback[-1500:]
            reply: ModelReply = self.client.generate(prompt, self.model)
            if not reply.ok:
                last_error = reply.error or "Modelo no disponible"
                continue
            try:
                package = _package(reply.text)
                name = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(package["name"])).strip("_")
                if not name:
                    raise ValueError("Nombre invalido")
                staging = safe_output(self.workspace, ".staging/" + name)
                tests = str(package["tests"])
                if "solution" not in tests:
                    tests = "from solution import *\n" + tests
                coordinator = AutonomousProgrammingCoordinator(
                    self.client, staging, default_model=self.model)
                result = coordinator.execute(
                    objective, confirmed=True, context=package["source"],
                    on_progress=on_progress)
                if not result.ok:
                    last_error = result.message
                    feedback = "; ".join(result.diagnostics)
                    continue
                if on_progress:
                    on_progress(95, "Entregando proyecto verificado")
                target = safe_output(self.workspace, "projects/" + name)
                if target.exists():
                    name += "_" + (result.proposal.sha256 if result.proposal and result.proposal.sha256 else "v2")
                    target = safe_output(self.workspace, "projects/" + name)
                target.mkdir(parents=True)
                source = result.proposal.source if result.proposal else package["source"]
                tests_out = result.proposal.tests if result.proposal else tests
                (target / "main.py").write_text(source, encoding="utf-8")
                (target / "test_main.py").write_text(
                    tests_out.replace("from solution import", "from main import"),
                    encoding="utf-8")
                (target / "README.md").write_text(
                    str(package.get("readme", objective)), encoding="utf-8")
                digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
                (target / "VERIFICATION.json").write_text(
                    json.dumps({"sha256": digest, "tests_passed": True},
                               indent=2), encoding="utf-8")
                return DevelopmentResult(True, "Proyecto generado y verificado",
                                         str(target), attempt)
            except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
                last_error = str(exc)
                feedback = last_error
        return DevelopmentResult(False, "No supero verificacion: " + last_error,
                                 attempts=attempts)
