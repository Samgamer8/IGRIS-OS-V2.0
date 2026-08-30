from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path

from igris_os.programming.component_plan import ComponentSpec, PythonComponentPlanner
from igris_os.programming.engineering_workflow import EngineeringWorkflow
from igris_os.utils.json_parser import StrictJSONParser


COMPONENT_SCHEMA = {
    "type": "object",
    "properties": {"content": {"type": "string"}},
    "required": ["content"],
}


@dataclass(frozen=True, slots=True)
class SequentialDevelopmentResult:
    ok: bool
    message: str
    project: Path | None = None
    files: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()


class SequentialPythonComponentDeveloper:
    """Genera módulos en orden de dependencias y pruebas después de las interfaces."""

    def __init__(self, client, workspace: Path, model: str) -> None:
        self.client = client
        self.workspace = workspace.resolve()
        self.model = model
        self.planner = PythonComponentPlanner()

    def develop(self, objective: str, *, confirmed: bool = False,
                attempts: int = 2) -> SequentialDevelopmentResult:
        if not confirmed:
            return SequentialDevelopmentResult(False, "Se necesita confirmacion")
        plan = self.planner.plan(objective)
        diagnostics = ""
        for attempt in range(1, max(1, attempts) + 1):
            root = self._new_staging(attempt)
            files: dict[str, str] = {}
            try:
                for component in plan.components:
                    content = self._generate_component(
                        plan.objective, component, files, diagnostics)
                    ast.parse(content, filename=component.path)
                    target = root / component.path
                    target.write_text(content, encoding="utf-8")
                    files[component.path] = content
                (root / "README.md").write_text(
                    "Proyecto generado por componentes y verificado con pytest.\n",
                    encoding="utf-8")
                checked = EngineeringWorkflow().run(
                    root, ("python", "-m", "pytest", "-q"),
                    confirmed=True, timeout=60)
                if checked.run and checked.run.returncode == 0 and not checked.run.timed_out:
                    (root / "VERIFICATION.json").write_text(json.dumps({
                        "tests_passed": True, "model": self.model,
                        "strategy": "sequential_components", "files": list(files),
                    }, ensure_ascii=False, indent=2), encoding="utf-8")
                    return SequentialDevelopmentResult(
                        True, "Proyecto por componentes verificado", root, tuple(files))
                diagnostics = ((checked.run.stdout + checked.run.stderr)[-4000:]
                               if checked.run else checked.reason)
            except (ValueError, OSError, SyntaxError) as exc:
                diagnostics = str(exc)
        return SequentialDevelopmentResult(
            False, "Proyecto por componentes no verificado", diagnostics=(diagnostics,))

    def _generate_component(self, objective: str, component: ComponentSpec,
                            files: dict[str, str], diagnostics: str) -> str:
        context = "\n\n".join(
            f"=== {path} ===\n{content}" for path, content in files.items())
        prompt = (
            "Genera SOLO JSON con la clave content y el contenido completo de un archivo Python. "
            "No incluyas markdown ni explicación.\n"
            f"OBJETIVO: {objective}\n"
            f"ARCHIVO: {component.path}\n"
            f"RESPONSABILIDAD: {component.purpose}\n"
            f"DEPENDENCIAS: {', '.join(component.depends_on) or 'ninguna'}\n"
            f"ACEPTACION: {'; '.join(component.acceptance)}\n"
            "Las pruebas deben importar exactamente las interfaces de los archivos previos. "
            "No inventes valores esperados; calcula ejemplos de prueba correctamente. "
            "Las pruebas deben ser autocontenidas: no uses fixtures que no estén definidas "
            "en el mismo archivo; prefiere crear los objetos directamente en cada test.")
        if context:
            prompt += "\nARCHIVOS YA ESCRITOS:\n" + context[-12000:]
        if diagnostics:
            prompt += "\nDIAGNOSTICO DEL INTENTO ANTERIOR:\n" + diagnostics[-3000:]
        generate_json = getattr(self.client, "generate_json", None)
        if callable(generate_json):
            reply = generate_json(prompt, self.model, COMPONENT_SCHEMA)
        else:
            reply = self.client.generate(prompt, self.model)
        if not reply.ok:
            raise ValueError(reply.error or "Modelo sin respuesta")
        data = StrictJSONParser.extract(reply.text)
        content = str(data.get("content", "")).strip()
        if not content:
            raise ValueError("Componente sin contenido: " + component.path)
        return content

    def _new_staging(self, attempt: int) -> Path:
        root = (self.workspace / ".staging" / f"components_{attempt}").resolve()
        if not root.is_relative_to(self.workspace):
            raise ValueError("Staging por componentes no disponible")
        root.mkdir(parents=True, exist_ok=False)
        return root