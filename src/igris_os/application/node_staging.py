from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
from pathlib import Path

from igris_os.application.project_development import StagedProject
from igris_os.application.project_planning import PlannedProjectMission
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


class StrictNodeStagingDeveloper:
    """Genera JS/TS aislado y solo devuelve paquetes compilados y probados."""

    MAX_FILES = 20
    FORBIDDEN = re.compile(
        r"\b(eval|Function)\s*\(|(?:node:)?child_process|\bexecSync\b|\bspawnSync\b")

    def __init__(self, client, workspace: Path, model: str,
                 timeout: int = 60) -> None:
        self.client = client
        self.workspace = Path(workspace).resolve()
        self.model = model
        self.timeout = min(120, max(5, int(timeout)))

    def stage(self, mission: PlannedProjectMission) -> StagedProject:
        language = mission.mission.contract.technology
        if language not in {"javascript", "typescript", "web"}:
            raise ValueError("Tecnología Node no soportada: " + language)
        if shutil.which("node") is None:
            raise ValueError("Node.js no está disponible")
        if language == "typescript" and shutil.which("tsc") is None:
            raise ValueError("TypeScript no está disponible")
        reply = self._generate(mission, language)
        if not reply.ok:
            raise ValueError(reply.error or "El modelo no produjo el proyecto")
        package = StrictJSONParser.extract(reply.text)
        root, files = self._write(package, language)
        self._verify(root, language)
        (root / "VERIFICATION.json").write_text(json.dumps({
            "language": language,
            "tests_passed": True,
            "files": files,
            "commands": self.commands(language),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        return StagedProject(root, tuple(files))

    def _generate(self, mission: PlannedProjectMission, language: str):
        contract = mission.mission.contract
        extension = "ts" if language == "typescript" else "js"
        prompt = (
            f"Genera un proyecto {language} completo sin dependencias externas. "
            "Devuelve SOLO JSON con name, files y readme. "
            f"Usa módulos ES y archivos .{extension}. "
            "Incluye al menos test_main." + extension + " con node:test y node:assert/strict. "
            "No uses Jest, npm install, red, eval, Function ni child_process. "
            "En TypeScript importa módulos locales usando sufijo .js para NodeNext.\n"
            "OBJETIVO:\n" + contract.objective + "\nACEPTACIÓN:\n" +
            "\n".join("- " + item for item in contract.acceptance))
        generate_json = getattr(self.client, "generate_json", None)
        return (generate_json(prompt, self.model, PACKAGE_SCHEMA)
                if callable(generate_json) else self.client.generate(prompt, self.model))

    def _write(self, package: dict, language: str) -> tuple[Path, list[str]]:
        name = re.sub(r"[^A-Za-z0-9_-]+", "_", str(package.get("name", ""))).strip("_")
        files = package.get("files")
        if not name or not isinstance(files, dict) or not 2 <= len(files) <= self.MAX_FILES:
            raise ValueError("Paquete Node incompleto")
        root = (self.workspace / ".staging" / name).resolve()
        suffix = 2
        while root.exists():
            root = (self.workspace / ".staging" / f"{name}_{suffix}").resolve()
            suffix += 1
        if not root.is_relative_to(self.workspace):
            raise ValueError("Staging Node fuera del workspace")
        root.mkdir(parents=True)
        expected = ".ts" if language == "typescript" else ".js"
        written: list[str] = []
        has_test = False
        for raw, value in files.items():
            relative = Path(str(raw).replace("\\", "/"))
            target = (root / relative).resolve()
            allowed_static = language == "web" and relative.suffix in {".html", ".css"}
            if (relative.is_absolute() or not target.is_relative_to(root)
                    or (relative.suffix != expected and not allowed_static)):
                raise ValueError("Ruta Node no permitida: " + str(raw))
            content = str(value)
            if not content.strip() or self.FORBIDDEN.search(content):
                raise ValueError("Contenido Node vacío o peligroso: " + str(raw))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            written.append(relative.as_posix())
            has_test = has_test or relative.name.startswith("test_")
        if not has_test:
            raise ValueError("Faltan pruebas node:test")
        (root / "package.json").write_text(
            json.dumps({"name": name.casefold(), "private": True, "type": "module"}, indent=2),
            encoding="utf-8")
        (root / "README.md").write_text(str(package.get("readme", "")), encoding="utf-8")
        return root, written

    def _verify(self, root: Path, language: str) -> None:
        for command in self.commands(language):
            completed = subprocess.run(
                command, cwd=root, capture_output=True, text=True,
                timeout=self.timeout, check=False)
            if completed.returncode != 0:
                detail = (completed.stdout + completed.stderr)[-3000:]
                raise ValueError("Verificación Node fallida: " + detail)

    @staticmethod
    def commands(language: str) -> tuple[tuple[str, ...], ...]:
        if language == "typescript":
            return (
                ("tsc", "--strict", "--module", "nodenext", "--target", "ES2022",
                 "--outDir", "dist", "--rootDir", "."),
                ("node", "--test", "dist/test_*.js"),
            )
        return (("node", "--check", "main.js"),
                ("node", "--test", "test_*.js"))
