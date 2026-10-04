from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from igris_os.programming.component_plan import ComponentPlan, PythonComponentPlanner
from igris_os.programming.engineering_workflow import EngineeringWorkflow
from igris_os.utils.json_parser import StrictJSONParser


PACKAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "files": {"type": "object", "additionalProperties": {"type": "string"}},
        "readme": {"type": "string"},
    },
    "required": ["name", "files", "readme"],
}


@dataclass(frozen=True, slots=True)
class MultiFileDevelopmentResult:
    ok: bool
    message: str
    project: Path | None = None
    files: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()
    models_tried: tuple[str, ...] = ()
    attempts: int = 0


class PythonMultiFileDeveloper:
    """Construye proyectos Python por archivos, con pruebas de integración reales."""

    MAX_FILES = 20
    MAX_FILE_BYTES = 256_000
    MAX_SYNTAX_REPAIRS = 2

    def __init__(self, client, workspace: Path, model: str) -> None:
        self.client = client
        self.workspace = workspace.resolve()
        self.model = model

    def develop(self, objective: str, *, confirmed: bool = False,
                attempts: int = 3,
                componentized: bool = False,
                domain_validator: Callable[[Path], str] | None = None,
                fallback_models: tuple[str, ...] = (),
                ) -> MultiFileDevelopmentResult:
        if not confirmed:
            return MultiFileDevelopmentResult(False, "Se necesita confirmacion")
        if not objective.strip():
            return MultiFileDevelopmentResult(False, "Falta el objetivo")
        diagnostics = ""
        plan = PythonComponentPlanner().plan(objective) if componentized else None
        previous_package: dict | None = None
        model_sequence = tuple(dict.fromkeys((self.model, *fallback_models)))
        model_index = 0
        active_model = model_sequence[model_index]
        models_tried: list[str] = []
        last_domain_diagnostic = ""
        for attempt in range(1, max(1, attempts) + 1):
            if active_model not in models_tried:
                models_tried.append(active_model)
            reply = self._generate(
                objective, diagnostics, plan, previous_package, active_model)
            if not reply.ok:
                diagnostics = reply.error or "Modelo sin respuesta"
                if model_index + 1 < len(model_sequence):
                    model_index += 1
                    active_model = model_sequence[model_index]
                continue
            try:
                package = StrictJSONParser.extract(reply.text)
                package = self._complete_missing_components(package, plan, active_model)
                package, syntax_errors = self._ensure_valid_syntax(package, active_model)
                if syntax_errors:
                    diagnostics = "ERRORES_SINTAXIS:\n" + "\n".join(
                        f"{path}: {error}" for path, error in syntax_errors.items())
                    if model_index + 1 < len(model_sequence):
                        model_index += 1
                        active_model = model_sequence[model_index]
                    continue
                previous_package = package
                root, files = self._write_package(package, plan)
                checked = EngineeringWorkflow().run(
                    root, ("python", "-m", "pytest", "-q"),
                    confirmed=True, timeout=60)
                if checked.run and checked.run.returncode == 0 and not checked.run.timed_out:
                    runtime_diagnostic = self._runtime_acceptance_diagnostic(
                        root, objective)
                    if runtime_diagnostic:
                        diagnostics = runtime_diagnostic
                        if (runtime_diagnostic == last_domain_diagnostic and
                                model_index + 1 < len(model_sequence)):
                            model_index += 1
                            active_model = model_sequence[model_index]
                        last_domain_diagnostic = runtime_diagnostic
                        continue
                    domain_diagnostic = (
                        domain_validator(root) if domain_validator else ""
                    )
                    if domain_diagnostic:
                        diagnostics = domain_diagnostic
                        if (domain_diagnostic == last_domain_diagnostic and
                                model_index + 1 < len(model_sequence)):
                            model_index += 1
                            active_model = model_sequence[model_index]
                        last_domain_diagnostic = domain_diagnostic
                        continue
                    (root / "VERIFICATION.json").write_text(json.dumps({
                        "tests_passed": True, "model": active_model,
                        "models_tried": models_tried,
                        "runtime_acceptance_passed": True,
                        "files": files,
                    }, ensure_ascii=False, indent=2), encoding="utf-8")
                    return MultiFileDevelopmentResult(
                        True, "Proyecto multiarchivo verificado", root, tuple(files),
                        models_tried=tuple(models_tried), attempts=attempt)
                diagnostics = ((checked.run.stdout + checked.run.stderr)[-4000:]
                               if checked.run else checked.reason)
            except (ValueError, TypeError, KeyError, OSError, SyntaxError) as exc:
                diagnostics = str(exc)
        return MultiFileDevelopmentResult(
            False, "Proyecto multiarchivo no verificado", diagnostics=(diagnostics,),
            models_tried=tuple(models_tried), attempts=attempt)

    @staticmethod
    def _runtime_acceptance_diagnostic(root: Path, objective: str) -> str:
        """Comprueba contratos de ejecución que pytest puede omitir."""
        normalized = objective.casefold()
        console_requested = any(term in normalized for term in (
            "interfaz de consola", "consola", "command-line", "command line",
            "terminal", "aplicación cli", "aplicacion cli",
        ))
        if not console_requested:
            return ""

        entry_functions: set[str] = set()
        guarded_entries: set[str] = set()
        for path in root.rglob("*.py"):
            relative = path.relative_to(root)
            if (relative.name.startswith("test_") or
                    "tests" in {part.casefold() for part in relative.parts}):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"),
                             filename=relative.as_posix())
            defined = {
                node.name for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            entry_functions.update(
                name for name in defined
                if name.casefold() in {"main", "run", "run_cli", "cli"})
            for node in tree.body:
                if not isinstance(node, ast.If) or not _is_main_guard(node.test):
                    continue
                called = {
                    call.func.id for call in ast.walk(node)
                    if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                }
                guarded_entries.update(called & defined)

        if not entry_functions:
            return (
                "ACEPTACION_RUNTIME: se pidió una interfaz de consola, pero no "
                "existe una función de entrada main/run_cli ejecutable.")
        if not guarded_entries:
            return (
                "ACEPTACION_RUNTIME: la interfaz de consola no arranca con "
                "`python -m modulo`; añade `if __name__ == \"__main__\": main()`.")

        tests = "\n".join(
            path.read_text(encoding="utf-8")
            for path in root.rglob("test_*.py")
        )
        exercised = any(
            re.search(rf"\b{re.escape(name)}\s*\(", tests)
            for name in guarded_entries
        )
        if not exercised:
            return (
                "ACEPTACION_RUNTIME: pytest no ejecuta la entrada de consola. "
                "Añade una prueba que simule input, invoque main/run_cli y compruebe "
                "el flujo principal y la salida.")
        return ""

    @staticmethod
    def _validate_syntax(files: dict) -> dict[str, str]:
        """Analiza TODOS los archivos .py antes de escribir nada a disco."""
        errors: dict[str, str] = {}
        if not isinstance(files, dict):
            return errors
        for raw_path, content in files.items():
            relative = str(raw_path).replace("\\", "/")
            if not relative.endswith(".py"):
                continue
            try:
                ast.parse(str(content), filename=relative)
            except SyntaxError as exc:
                errors[relative] = str(exc)
        return errors

    def _ensure_valid_syntax(self, package: dict,
                             model: str) -> tuple[dict, dict[str, str]]:
        """Valida el paquete completo y, si hace falta, pide hasta
        MAX_SYNTAX_REPAIRS correcciones acotadas antes de escribir a disco."""
        files = package.get("files")
        errors = self._validate_syntax(files)
        if not errors:
            return package, {}
        generate_json = getattr(self.client, "generate_json", None)
        for _ in range(self.MAX_SYNTAX_REPAIRS):
            broken = "\n".join(
                f"- {path}: {error}\n```\n{files[path]}\n```"
                for path, error in errors.items())
            prompt = (
                "Devuelve SOLO JSON valido con un objeto files ruta->contenido. "
                "Corrige UNICAMENTE los errores de sintaxis Python de estos "
                "archivos, sin cambiar su comportamiento ni otros archivos:\n" +
                broken)
            schema = {
                "type": "object",
                "properties": {"files": {"type": "object",
                                          "additionalProperties": {"type": "string"}}},
                "required": ["files"],
            }
            reply = (generate_json(prompt, model, schema)
                     if callable(generate_json) else self.client.generate(prompt, model))
            if not reply.ok:
                break
            try:
                fixed = StrictJSONParser.extract(reply.text)
            except (TypeError, ValueError):
                break
            additions = fixed.get("files")
            if not isinstance(additions, dict):
                break
            files = dict(files)
            files.update({str(path): str(content)
                          for path, content in additions.items()
                          if str(path).replace("\\", "/") in errors})
            package = dict(package)
            package["files"] = files
            errors = self._validate_syntax(files)
            if not errors:
                break
        return package, errors

    def _complete_missing_components(self, package: dict,
                                     plan: ComponentPlan | None,
                                     model: str) -> dict:
        if plan is None or not isinstance(package.get("files"), dict):
            return package
        expected = {component.path for component in plan.components}
        supplied = {str(path).replace("\\", "/") for path in package["files"]}
        missing = sorted(expected - supplied)
        if not missing:
            return package
        prompt = (
            "Devuelve SOLO JSON valido con un objeto files ruta->contenido. "
            "Genera unicamente estos archivos faltantes para un proyecto Python "
            "multiarchivo ya existente: " + ", ".join(missing) + ". "
            "Mantén importaciones coherentes con model.py, service.py y main.py. "
            "El test debe usar pytest y verificar el flujo principal.\n"
            "Contenido de los archivos existentes: " +
            json.dumps(package["files"], ensure_ascii=False)[:18000])
        schema = {
            "type": "object",
            "properties": {"files": {"type": "object",
                                       "additionalProperties": {"type": "string"}}},
            "required": ["files"],
        }
        generate_json = getattr(self.client, "generate_json", None)
        reply = (generate_json(prompt, model, schema)
                 if callable(generate_json) else self.client.generate(prompt, model))
        if not reply.ok:
            return package
        completed = StrictJSONParser.extract(reply.text)
        additions = completed.get("files")
        if not isinstance(additions, dict):
            return package
        merged = dict(package)
        merged["files"] = dict(package["files"])
        merged["files"].update({str(path): str(content)
                                 for path, content in additions.items()
                                 if str(path).replace("\\", "/") in missing})
        return merged

    def _generate(self, objective: str, diagnostics: str,
                  plan: ComponentPlan | None,
                  previous_package: dict | None, model: str):
        prompt = (
            "Genera un proyecto Python multiarchivo. Devuelve SOLO un JSON válido con "
            "name, files (ruta->contenido) y readme. Usa exactamente los componentes "
            "indicados, incluye pytest, no uses dependencias externas ni red, y no "
            "pongas markdown fuera del JSON. Si una prueba tiene una expectativa "
            "incorrecta, corrige la prueba y no rompas una implementacion correcta.\n"
            "OBJETIVO:\n" + objective)
        if any(term in objective.casefold() for term in (
                "interfaz de consola", "consola", "command-line", "command line",
                "terminal", "aplicación cli", "aplicacion cli")):
            prompt += (
                "\nCONTRATO DE CONSOLA OBLIGATORIO: el módulo ejecutable debe llamar "
                "a main/run_cli bajo `if __name__ == \"__main__\"`; el comando "
                "documentado `python -m modulo` debe iniciar la interfaz. Incluye una "
                "prueba pytest que simule input, invoque esa entrada y compruebe al "
                "menos un flujo funcional y su salida.")
        if plan is not None:
            components = "\n".join(
                f"{item.path}: {item.purpose}"
                for item in plan.components)
            prompt += (
                "\nCOMPONENTES OBLIGATORIOS:\n" + components +
                "\nDebes incluir exactamente estas cuatro rutas: model.py, service.py, "
                "main.py y test_service.py. test_service.py debe contener pruebas "
                "pytest ejecutables. Mantén las importaciones coherentes.")
        if diagnostics:
            prompt += (
                "\nDIAGNOSTICO DEL INTENTO ANTERIOR:\n" + diagnostics[-3000:] +
                "\nSi el diagnostico indica una expectativa de prueba incorrecta, "
                "corrige la prueba y no alteres una implementacion correcta solo "
                "para satisfacerla.")
        if previous_package is not None:
            prompt += (
                "\nPAQUETE ANTERIOR A REPARAR:\n" +
                json.dumps(previous_package, ensure_ascii=False)[:18000] +
                "\nConserva los módulos correctos y corrige solo los archivos afectados.")
        generate_json = getattr(self.client, "generate_json", None)
        if callable(generate_json):
            reply = generate_json(prompt, model, PACKAGE_SCHEMA)
            if reply.ok:
                try:
                    StrictJSONParser.extract(reply.text)
                    return reply
                except (TypeError, ValueError, json.JSONDecodeError):
                    logger_msg = 'JSON extraído inválido, ejecutando prompt de respaldo'
            fallback_prompt = (
                prompt + "\nLa respuesta anterior no era JSON utilizable. "
                "Devuelve ahora un unico objeto JSON valido, sin markdown, "
                "sin comentarios y con contenido completo en cada archivo."
            )
            return self.client.generate(fallback_prompt, model)
        return self.client.generate(prompt, model)

    def _write_package(self, package: dict,
                       plan: ComponentPlan | None = None) -> tuple[Path, list[str]]:
        name = "".join(char for char in str(package.get("name", ""))
                       if char.isalnum() or char in "_-").strip("_-")
        files = package.get("files")
        if not name or not isinstance(files, dict) or not 2 <= len(files) <= self.MAX_FILES:
            raise ValueError("Paquete multiarchivo incompleto")
        if plan is not None:
            expected_test = next((item.path for item in plan.components
                                  if item.path.startswith("test_")), None)
            test_files = [str(path).replace("\\", "/") for path in files
                          if Path(str(path)).name.startswith("test_")]
            if expected_test and expected_test not in files and len(test_files) == 1:
                files[expected_test] = files.pop(test_files[0])
            PythonComponentPlanner.validate_files(plan, {
                str(path).replace("\\", "/"): str(content)
                for path, content in files.items()})
        base = (self.workspace / ".staging").resolve()
        root = (base / name).resolve()
        suffix = 2
        while root.exists():
            root = (base / f"{name}_{suffix}").resolve()
            suffix += 1
        if not root.is_relative_to(self.workspace):
            raise ValueError("Staging multiarchivo no disponible")
        root.mkdir(parents=True)
        written: list[str] = []
        has_test = False
        for raw_path, content in files.items():
            relative = Path(str(raw_path).replace("\\", "/"))
            target = (root / relative).resolve()
            allowed_document = relative.as_posix().casefold() == "readme.md"
            if (relative.is_absolute() or not relative.name or
                    not target.is_relative_to(root) or
                    (target.suffix != ".py" and not allowed_document) or
                    len(str(content).encode("utf-8")) > self.MAX_FILE_BYTES):
                raise ValueError("Archivo multiarchivo no permitido: " + str(raw_path))
            text = str(content)
            if target.suffix == ".py":
                ast.parse(text, filename=relative.as_posix())
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
            written.append(relative.as_posix())
            has_test = has_test or relative.name.startswith("test_")
        if not has_test:
            raise ValueError("Falta test_*.py en el paquete multiarchivo")
        readme = str(package.get("readme", ""))
        if readme or not (root / "README.md").exists():
            (root / "README.md").write_text(readme, encoding="utf-8")
        return root, written


def _is_main_guard(test: ast.expr) -> bool:
    if not isinstance(test, ast.Compare) or len(test.ops) != 1:
        return False
    if not isinstance(test.ops[0], ast.Eq) or len(test.comparators) != 1:
        return False
    left, right = test.left, test.comparators[0]
    pairs = ((left, right), (right, left))
    return any(
        isinstance(name, ast.Name) and name.id == "__name__" and
        isinstance(value, ast.Constant) and value.value == "__main__"
        for name, value in pairs
    )
