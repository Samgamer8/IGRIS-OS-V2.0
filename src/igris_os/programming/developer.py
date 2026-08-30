import ast
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from igris_os.ai import ModelReply
from igris_os.programming.workshop import PythonWorkshop
from igris_os.tools import safe_output
from igris_os.utils.json_parser import StrictJSONParser


SYSTEM = """Actua como ingeniero senior. Devuelve solo JSON UTF-8 con:
{"name":"nombre","source":"codigo Python completo","tests":"unittest completo",
"readme":"uso"}. Sin markdown. Biblioteca estandar. Sin red, subprocess, eval,
exec, ctypes ni efectos destructivos. Implementa casos limite.
Cuestiona requisitos ambiguos y prioriza seguridad, rendimiento y mantenibilidad.
Aplica KISS, DRY y SOLID sin sobreingenieria. No uses placeholders.
Solo entrega codigo que pueda verificarse con tests y documenta riesgos,
optimizaciones futuras y estrategia de pruebas en el readme. Los tests deben
importar siempre desde `solution`, porque ese es el modulo verificado."""

PACKAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "source": {"type": "string"},
        "tests": {"type": "string"},
        "readme": {"type": "string"},
    },
    "required": ["name", "source", "tests", "readme"],
}


@dataclass(frozen=True, slots=True)
class DevelopmentResult:
    ok: bool
    message: str
    project: str = ""
    attempts: int = 0


def _package(text: str) -> dict:
    fenced = re.fullmatch(r"\s*```(?:json)?\s*(.*?)\s*```\s*",
                          text, re.DOTALL | re.IGNORECASE)
    raw = fenced.group(1) if fenced else text
    try:
        value = StrictJSONParser.extract(raw)
    except ValueError:
        try:
            value = _recover_code_package(raw)
        except ValueError:
            value = _recover_fenced_python_package(raw)
    if not isinstance(value, dict) or not {"name", "source", "tests"} <= value.keys():
        raise ValueError("Paquete incompleto")
    source = value["source"]
    tests = value["tests"]
    if not isinstance(source, str) or not source.strip():
        raise ValueError("Codigo fuente vacio")
    if not isinstance(tests, str) or not tests.strip():
        raise ValueError("Pruebas vacias")
    try:
        ast.parse(source, filename="generated_source.py")
        ast.parse(tests, filename="generated_tests.py")
    except SyntaxError as exc:
        raise ValueError(
            f"Paquete truncado o con sintaxis invalida: linea {exc.lineno}: {exc.msg}") from exc
    if source.rstrip().endswith((".", ":", ",", "=", "(", "[", "{")):
        raise ValueError("Codigo fuente parece truncado")
    if tests.rstrip().endswith((".", ":", ",", "=", "(", "[", "{")):
        raise ValueError("Pruebas parecen truncadas")
    files = value.get("files", {})
    if files and not isinstance(files, dict):
        raise ValueError("Archivos adicionales invalidos")
    for relative, content in files.items():
        relative_path = Path(str(relative))
        if (not str(relative).strip() or relative_path.is_absolute()
                or ".." in relative_path.parts
                or relative_path.name in {"", ".", ".."}):
            raise ValueError("Ruta de archivo adicional no permitida")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Archivo adicional vacio")
        if relative_path.suffix.casefold() == ".py":
            try:
                ast.parse(content, filename=relative_path.as_posix())
            except SyntaxError as exc:
                raise ValueError(
                    f"Archivo adicional truncado: {relative_path}: {exc.msg}") from exc
    return value


def _recover_code_package(raw: str) -> dict:
    """Recupera código cuando el modelo solo rompe las comillas del JSON."""
    name = re.search(r'"name"\s*:\s*"([^"\\]+)', raw)
    source = re.search(
        r'"source"\s*:\s*"(.*?)(?<!\\)",\s*"tests"\s*:',
        raw, re.DOTALL)
    tests = re.search(
        r'"tests"\s*:\s*"(.*?)(?<!\\)",\s*"readme"\s*:',
        raw, re.DOTALL)
    readme = re.search(
        r'"readme"\s*:\s*"(.*?)(?<!\\)"\s*}', raw, re.DOTALL)
    if not name or not source or not tests:
        raise ValueError("Paquete JSON invalido y no recuperable")
    return {
        "name": name.group(1),
        "source": _decode_code_field(source.group(1)),
        "tests": _decode_code_field(tests.group(1)),
        "readme": _decode_code_field(readme.group(1)) if readme else "",
    }


def _decode_code_field(value: str) -> str:
    return (value.replace("\\r\\n", "\n").replace("\\n", "\n")
            .replace('\\"', '"').replace("\\\\", "\\"))


def _recover_fenced_python_package(raw: str) -> dict:
    """Acepta dos bloques Python solo si aportan fuente y pruebas completas."""
    blocks = re.findall(
        r"```(?:python|py)\s*\n(.*?)```", raw,
        flags=re.DOTALL | re.IGNORECASE)
    if len(blocks) < 2:
        raise ValueError("No hay bloques Python suficientes para recuperar la entrega")
    return {
        "name": "proyecto_generado",
        "source": blocks[0].strip(),
        "tests": blocks[1].strip(),
        "readme": "Entrega recuperada de bloques Python; revisa el uso documentado.",
    }


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
            generate_json = getattr(self.client, "generate_json", None)
            if callable(generate_json):
                reply: ModelReply = generate_json(prompt, self.model, PACKAGE_SCHEMA)
            else:
                reply = self.client.generate(prompt, self.model)
            if not reply.ok:
                last_error = reply.error or "Modelo no disponible"
                continue
            try:
                package = _package(reply.text)
                name = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(package["name"])).strip("_")
                if not name:
                    raise ValueError("Nombre invalido")
                staging = safe_output(self.workspace, ".staging/" + name)
                tests = re.sub(
                    r"from\s+[A-Za-z_][A-Za-z0-9_]*\s+import",
                    "from solution import", str(package["tests"]))
                if "from solution import" not in tests:
                    tests = "from solution import *\n" + tests
                workshop = PythonWorkshop(staging, repair_model=self.model)
                verified = workshop.verify_with_repair(
                    package["source"], tests, self.client,
                    max_attempts=attempts, on_progress=on_progress)
                if not verified.ok:
                    last_error = verified.message
                    feedback = "; ".join(verified.diagnostics)
                    continue
                if on_progress:
                    on_progress(95, "Entregando proyecto verificado")
                target = safe_output(self.workspace, "projects/" + name)
                if target.exists():
                    name += "_v2"
                    target = safe_output(self.workspace, "projects/" + name)
                target.mkdir(parents=True)
                source = verified.source
                tests_out = tests
                (target / "main.py").write_text(source, encoding="utf-8")
                (target / "test_main.py").write_text(
                    tests_out.replace("from solution import", "from main import"),
                    encoding="utf-8")
                for relative, content in package.get("files", {}).items():
                    extra = (target / str(relative)).resolve()
                    if not extra.is_relative_to(target):
                        raise ValueError("Ruta de archivo adicional fuera del proyecto")
                    extra.parent.mkdir(parents=True, exist_ok=True)
                    extra.write_text(str(content), encoding="utf-8")
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
