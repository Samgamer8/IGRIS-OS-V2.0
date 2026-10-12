from __future__ import annotations

import json
import math
import uuid
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

from igris_os.ai import ModelReply, OllamaClient
from igris_os.domain import Mission, MissionBranch
from igris_os.programming.languages import Language, MultiLanguageVerifier, UniversalQualityGate
from igris_os.programming.specialists import (
    SpecialistOutput,
    SpecialistRegistry,
    SpecialistRole,
)
from igris_os.programming.workshop import PythonWorkshop, RepairResult


@dataclass(frozen=True, slots=True)
class LanguageDevelopmentResult:
    ok: bool
    message: str
    language: str = ""
    artifacts: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = field(default_factory=tuple)
    attempts: int = 0
    project: str = ""


class MultiLanguageCoordinator:
    LANGUAGE_PROMPTS: dict[Language, str] = {
        Language.PYTHON: (
            "Eres programador Python senior. Genera codigo completo con type hints, "
            "manejo de errores y tests unittest. Devuelve SOLO JSON: "
            '{"source":"codigo","tests":"tests","explanation":"cambios"}. Sin markdown.'
        ),
        Language.RUST: (
            "Eres programador Rust senior. Genera codigo con ownership correcto, "
            "tests unitarios y Cargo.toml. Devuelve SOLO JSON: "
            '{"source":"main.rs","tests":"tests.rs","cargo":"[package]...","explanation":"cambios"}. Sin markdown.'
        ),
        Language.CPP: (
            "Eres programador C++ senior. Genera codigo moderno C++17, tests Catch2 "
            "y CMakeLists.txt. Devuelve SOLO JSON: "
            '{"source":"main.cpp","tests":"test_main.cpp","cmake":"...","explanation":"cambios"}. Sin markdown.'
        ),
        Language.JAVA: (
            "Eres programador Java senior. Genera clases con tests JUnit 5 y pom.xml. "
            "Devuelve SOLO JSON: "
            '{"source":"Main.java","tests":"MainTest.java","pom":"...","explanation":"cambios"}. Sin markdown.'
        ),
        Language.GDSCRIPT: (
            "Eres programador Godot senior. Genera un proyecto ejecutable y pruebas reales. "
            "El test_runner.gd debe extender SceneTree, ejecutar casos que comprueben el "
            "comportamiento de main.gd, terminar con quit(1) si algo falla y escribir "
            "IGRIS_TESTS_PASSED solo despues de que todos los casos pasen. "
            "Devuelve SOLO JSON: "
            '{"source":"main.gd","tests":"test_runner.gd","scene":"test.tscn",'
            '"project":"project.godot","explanation":"cambios"}. Sin markdown.'
        ),
        Language.TYPESCRIPT: (
            "Eres programador TypeScript senior para Node.js 24 o posterior. "
            "Genera TypeScript con sintaxis eliminable por Node (sin enum, namespace "
            "ni parameter properties) y tests usando node:test y node:assert/strict. "
            "El package.json debe declarar type=module. No uses paquetes externos "
            "ni dependencias que haya que instalar. "
            "Devuelve SOLO JSON: "
            '{"source":"main.ts","tests":"main.test.ts","package":"...","explanation":"cambios"}. Sin markdown.'
        ),
        Language.JAVASCRIPT: (
            "Eres programador JavaScript senior para Node.js. Usa node:test y "
            "node:assert/strict; no añadas dependencias externas. "
            "Devuelve SOLO JSON: "
            '{"source":"main.js","tests":"main.test.js","package":"...","explanation":"cambios"}. Sin markdown.'
        ),
    }

    def __init__(self, client, workspace: Path, default_model: str = "qwen2.5-coder:7b") -> None:
        self.client = client
        self.workspace = workspace.resolve()
        self.default_model = default_model
        self.registry = SpecialistRegistry(client)

    def develop(self, objective: str, language: Language | str, *,
                confirmed: bool = False,
                on_progress: Callable[[int, str], None] | None = None
                ) -> LanguageDevelopmentResult:
        if not confirmed:
            return LanguageDevelopmentResult(False, "Se necesita confirmacion")
        if not objective.strip():
            return LanguageDevelopmentResult(False, "Falta el objetivo")
        try:
            lang = Language(language) if isinstance(language, str) else language
        except ValueError:
            return LanguageDevelopmentResult(False, "Lenguaje no soportado: " + str(language),
                                             str(language), diagnostics=("unsupported_language",))
        self._staging = self.workspace / ".staging" / (lang.value + "_" + uuid.uuid4().hex)
        self._last_diagnostic = ""

        if on_progress:
            on_progress(10, f"Fase 1: Diseno {lang.value}")
        design = self._design(objective, lang)
        if design is None:
            return LanguageDevelopmentResult(False, "Fallo en diseno", lang.value)
        if on_progress:
            on_progress(30, f"Fase 2: Implementacion {lang.value}")
        implementation = self._implement(objective, design, lang)
        if implementation is None:
            return LanguageDevelopmentResult(False, "Fallo en implementacion", lang.value)
        if on_progress:
            on_progress(60, f"Fase 3: Verificacion {lang.value}")
        verified = self._verify_and_repair(implementation, lang, on_progress)
        if verified is None:
            return LanguageDevelopmentResult(False, "No supero verificacion", lang.value,
                                             diagnostics=(self._last_diagnostic,), attempts=2)
        if on_progress:
            on_progress(90, f"Fase 4: Revision {lang.value}")
        review = self._review(verified, objective, design, lang)
        if review is not True:
            return LanguageDevelopmentResult(False, "Revision no aprobada", lang.value,
                                             diagnostics=("review_rejected",))
        if on_progress:
            on_progress(100, "Completado")
        return LanguageDevelopmentResult(True, "Mision completada", lang.value,
                                         tuple(str(p.relative_to(self._staging)) for p in self._staging.rglob("*")
                                               if p.is_file() and not any(x in p.parts for x in ("build", "target", "__pycache__"))),
                                         (), 1, str(self._staging))

    def _design(self, objective: str, language: Language) -> dict | None:
        prompt = (
            f"OBJETIVO:\n{objective}\nLENGUAJE: {language.value}\n\n"
            "Disena arquitectura JSON."
        )
        output = self.registry.execute(SpecialistRole.ARCHITECT, prompt)
        if not output.ok:
            return None
        try:
            return self._extract_json(output.text)
        except (ValueError, TypeError, KeyError):
            return None

    def _implement(self, objective: str, design: dict, language: Language) -> dict | None:
        system = self.LANGUAGE_PROMPTS.get(language, self.LANGUAGE_PROMPTS[Language.PYTHON])
        prompt = (
            system + "\n\nOBJETIVO:\n" + objective +
            "\n\nDISEÑO:\n" + json.dumps(design, ensure_ascii=False) +
            "\n\nImplementa y devuelve JSON."
        )
        output = self.registry.execute(SpecialistRole.PROGRAMMER, prompt)
        if not output.ok:
            return None
        try:
            return self._extract_json(output.text)
        except (ValueError, TypeError, KeyError):
            return None

    def _verify_and_repair(self, implementation: dict, language: Language,
                           on_progress: Callable[[int, str], None] | None
                           ) -> dict | None:
        if language == Language.PYTHON:
            return self._verify_python(implementation, on_progress)
        current = implementation
        for attempt in range(2):
            staging = self._staging / f"attempt_{attempt + 1}"
            staging.mkdir(parents=True, exist_ok=True)
            self._write_artifacts(staging, current, language)
            if self._run_project_tests(staging, language):
                self._staging = staging
                return current
            if attempt == 0:
                repaired = self._repair(current, language, self._last_diagnostic)
                if repaired is None:
                    break
                current = repaired
        return None

    def _run_project_tests(self, staging: Path, language: Language) -> bool:
        from igris_os.security.sandbox import JobObjectSandbox
        from igris_os.security.restricted import _filtered_env
        commands = {
            Language.RUST: [("cargo", "test", "--offline")],
            Language.CPP: [("cmake", "-S", ".", "-B", "build", "-DFETCHCONTENT_FULLY_DISCONNECTED=ON"),
                           ("cmake", "--build", "build"),
                           ("ctest", "--test-dir", "build", "--output-on-failure", "--no-tests=error")],
            Language.JAVA: [("mvn", "--offline", "-DfailIfNoTests=true", "test")],
            Language.GDSCRIPT: [("godot", "--headless", "--path", ".", "--script", "tests/test_runner.gd")],
            Language.TYPESCRIPT: [("node", "--experimental-strip-types", "--test",
                                   "--test-reporter=tap", "src/main.test.ts")],
            Language.JAVASCRIPT: [("node", "--test", "--test-reporter=tap", "src/main.test.js")],
        }.get(language)
        if not commands:
            self._last_diagnostic = "Sin verificador de pruebas para esta ruta; usa la capacidad especifica del lenguaje"
            return False
        evidence = []
        env = _filtered_env()
        env.update({"CARGO_NET_OFFLINE": "true", "NPM_CONFIG_OFFLINE": "true"})
        for command in commands:
            run = JobObjectSandbox().run(list(command), cwd=str(staging), timeout=60, env=env)
            output = (run.stdout + "\n" + run.stderr)[-16000:]
            evidence.append({"command": command, "returncode": run.returncode,
                             "timed_out": run.timed_out, "output": output})
            self._last_diagnostic = json.dumps(evidence, ensure_ascii=False)
            (staging / "VERIFICATION.json").write_text(self._last_diagnostic, encoding="utf-8")
            if run.returncode != 0 or run.timed_out:
                return False
        output = evidence[-1]["output"]
        if language == Language.RUST:
            return bool(re.search(r"running [1-9][0-9]* tests?", output))
        if language == Language.JAVASCRIPT:
            return bool(re.search(r"# pass [1-9][0-9]*", output))
        if language == Language.TYPESCRIPT:
            return bool(re.search(r"# pass [1-9][0-9]*", output))
        if language == Language.GDSCRIPT:
            return "IGRIS_TESTS_PASSED" in output and "SCRIPT ERROR" not in output
        return True

    def _verify_python(self, implementation: dict,
                       on_progress: Callable[[int, str], None] | None
                       ) -> dict | None:
        source = str(implementation.get("source", ""))
        tests = str(implementation.get("tests", ""))
        if not source or not tests:
            return None
        staging = self._staging
        staging.mkdir(parents=True, exist_ok=True)
        workshop = PythonWorkshop(staging, repair_model=self.default_model)
        result: RepairResult = workshop.verify_with_repair(
            source, tests, self.client, max_attempts=3, on_progress=on_progress)
        if not result.ok:
            self._last_diagnostic = result.message + "; " + "; ".join(result.diagnostics)
            return None
        return {**implementation,
                "source": (staging / "solution.py").read_text(encoding="utf-8"),
                "tests": (staging / "test_solution.py").read_text(encoding="utf-8")}

    def _repair(self, implementation: dict, language: Language, diagnostics: str) -> dict | None:
        system = self.LANGUAGE_PROMPTS.get(language, "")
        prompt = (
            "Repara este codigo. Devuelve SOLO JSON con el mismo formato.\n\n"
            "DIAGNOSTICO:\n" + diagnostics[:3000] +
            "\n\nCODIGO ACTUAL:\n" + json.dumps(implementation, ensure_ascii=False)
        )
        reply: ModelReply = self.client.generate(system + "\n\n" + prompt, self.default_model)
        if not reply.ok:
            return None
        try:
            cleaned = re.sub(r"^\s*```(?:json)?|```\s*$", "", reply.text,
                             flags=re.IGNORECASE).strip()
            data = json.loads(cleaned, strict=False)
            return data if data.get("source") else None
        except (ValueError, TypeError, KeyError):
            return None

    def _review(self, implementation: dict, objective: str, design: dict,
                language: Language) -> bool | None:
        prompt = (
            f"OBJETIVO:\n{objective}\nLENGUAJE: {language.value}\n\n"
            "CODIGO:\n" + json.dumps(implementation, ensure_ascii=False)[:8000] +
            "\n\nPuntua del 0 al 1. Devuelve JSON: {\"score\":0.9,\"approved\":true,\"issues\":[]}"
        )
        output = self.registry.execute(SpecialistRole.REVIEWER, prompt)
        if not output.ok:
            return None
        try:
            data = self._extract_json(output.text)
            score = float(data.get("score", 0.0))
            return data.get("approved") is True and math.isfinite(score) and 0.7 <= score <= 1.0
        except (ValueError, TypeError, KeyError):
            return None

    @staticmethod
    def _write_artifacts(staging: Path, implementation: dict, language: Language) -> None:
        mapping = {
            Language.RUST: [("source", "src/main.rs"), ("tests", "tests/tests.rs"), ("cargo", "Cargo.toml")],
            Language.CPP: [("source", "src/main.cpp"), ("tests", "tests/test_main.cpp"), ("cmake", "CMakeLists.txt")],
            Language.JAVA: [("source", "src/main/java/Main.java"), ("tests", "src/test/java/MainTest.java"), ("pom", "pom.xml")],
            Language.GDSCRIPT: [("source", "main.gd"), ("tests", "tests/test_runner.gd"),
                                ("scene", "test.tscn"), ("project", "project.godot")],
            Language.TYPESCRIPT: [("source", "src/main.ts"), ("tests", "src/main.test.ts"), ("package", "package.json")],
            Language.JAVASCRIPT: [("source", "src/main.js"), ("tests", "src/main.test.js"), ("package", "package.json")],
        }
        for key, rel in mapping.get(language, []):
            if key in implementation:
                target = staging / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(str(implementation[key]), encoding="utf-8")

    @staticmethod
    def _extract_json(text: str) -> dict:
        fenced = re.fullmatch(r"\s*```(?:json)?\s*(.*?)\s*```\s*", text,
                              re.DOTALL | re.IGNORECASE)
        candidate = fenced.group(1) if fenced else text
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("Sin JSON")
        return json.loads(candidate[start:end + 1], strict=False)
