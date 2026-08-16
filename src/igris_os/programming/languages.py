from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Sequence

from igris_os.programming.workshop import PythonWorkshop


class Language(str, Enum):
    PYTHON = "python"
    RUST = "rust"
    CPP = "cpp"
    JAVA = "java"
    GDSCRIPT = "gdscript"
    TYPESCRIPT = "typescript"
    JAVASCRIPT = "javascript"


@dataclass(frozen=True, slots=True)
class LanguageProfile:
    language: Language
    extensions: tuple[str, ...]
    test_command: tuple[str, ...]
    build_command: tuple[str, ...] | None = None
    lint_command: tuple[str, ...] | None = None
    requires_network: bool = False


@dataclass(frozen=True, slots=True)
class VerificationResult:
    ok: bool
    message: str
    language: Language
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""


class MultiLanguageVerifier:
    PROFILES: dict[Language, LanguageProfile] = {
        Language.PYTHON: LanguageProfile(
            Language.PYTHON, (".py",),
            test_command=("python", "-m", "pytest", "-q"),
            lint_command=("python", "-m", "py_compile"),
        ),
        Language.RUST: LanguageProfile(
            Language.RUST, (".rs",),
            test_command=("cargo", "test", "--quiet"),
            build_command=("cargo", "build", "--quiet"),
            lint_command=("cargo", "clippy", "-q", "--", "-D", "warnings"),
        ),
        Language.CPP: LanguageProfile(
            Language.CPP, (".cpp", ".cc", ".cxx", ".h", ".hpp"),
            test_command=("ctest", "--output-on-failure"),
            build_command=("cmake", "--build", ".", "--config", "Release"),
            lint_command=("clang-tidy", "-quiet", "src/*"),
        ),
        Language.JAVA: LanguageProfile(
            Language.JAVA, (".java",),
            test_command=("mvn", "test", "-q"),
            build_command=("mvn", "compile", "-q"),
            lint_command=("mvn", "checkstyle:check", "-q"),
        ),
        Language.GDSCRIPT: LanguageProfile(
            Language.GDSCRIPT, (".gd",),
            test_command=("godot", "--headless", "--quit", "--path", "."),
            build_command=None,
            lint_command=None,
            requires_network=False,
        ),
        Language.TYPESCRIPT: LanguageProfile(
            Language.TYPESCRIPT, (".ts",),
            test_command=("npx", "jest", "--silent"),
            build_command=("npx", "tsc", "--noEmit"),
            lint_command=("npx", "eslint", "src"),
        ),
        Language.JAVASCRIPT: LanguageProfile(
            Language.JAVASCRIPT, (".js",),
            test_command=("npx", "jest", "--silent"),
            build_command=("node", "--check", "src"),
            lint_command=("npx", "eslint", "src"),
        ),
    }

    def __init__(self, root: Path, *, timeout: int = 60) -> None:
        self.root = root.resolve()
        self.timeout = timeout

    def detect_language(self, path: Path) -> Language | None:
        suffix = path.suffix.casefold()
        for language, profile in self.PROFILES.items():
            if suffix in profile.extensions:
                return language
        return None

    def verify(self, path: Path) -> VerificationResult:
        language = self.detect_language(path)
        if language is None:
            return VerificationResult(False, "Lenguaje no soportado", Language.PYTHON)
        profile = self.PROFILES[language]
        if language == Language.PYTHON:
            return self._verify_python(path)
        return self._verify_toolchain(path, profile)

    def _verify_python(self, path: Path) -> VerificationResult:
        try:
            compile(path.read_text(encoding="utf-8"), path.name, "exec")
        except SyntaxError as exc:
            return VerificationResult(False, f"SyntaxError: {exc}", Language.PYTHON)
        return VerificationResult(True, "Python OK", Language.PYTHON)

    def _verify_toolchain(self, path: Path, profile: LanguageProfile) -> VerificationResult:
        if profile.lint_command:
            ok, msg, code, out, err = self._run(profile.lint_command, cwd=self.root)
            if not ok:
                return VerificationResult(False, f"Lint: {msg}", profile.language,
                                          code, out, err)
        if profile.build_command:
            ok, msg, code, out, err = self._run(profile.build_command, cwd=self.root)
            if not ok:
                return VerificationResult(False, f"Build: {msg}", profile.language,
                                          code, out, err)
        return VerificationResult(True, f"{profile.language.value} verificado", profile.language)

    def _run(self, cmd: Sequence[str], *, cwd: Path) -> tuple[bool, str, int, str, str]:
        try:
            result = subprocess.run(
                list(cmd),
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
            return (result.returncode == 0,
                    "OK" if result.returncode == 0 else result.stderr.strip(),
                    result.returncode,
                    result.stdout.strip(),
                    result.stderr.strip())
        except subprocess.TimeoutExpired:
            return False, "timeout", -1, "", "timeout"
        except FileNotFoundError as exc:
            return False, f"toolchain no encontrada: {exc}", -1, "", str(exc)
        except Exception as exc:
            return False, str(exc), -1, "", str(exc)


class UniversalQualityGate:
    def __init__(self, workspace: Path, *, timeout: int = 60) -> None:
        self.workspace = workspace.resolve()
        self.timeout = timeout
        self.verifier = MultiLanguageVerifier(workspace, timeout=timeout)

    def check(self, path: Path, *, run_tests: bool = True,
              run_security: bool = True) -> VerificationResult:
        language = self.verifier.detect_language(path)
        if language is None:
            return VerificationResult(False, "Lenguaje no soportado", Language.PYTHON)
        verifier_result = self.verifier.verify(path)
        if not verifier_result.ok:
            return verifier_result
        if run_tests:
            test_result = self._run_tests(path, language)
            if not test_result.ok:
                return test_result
        if run_security:
            sec_result = self._security_scan(path, language)
            if not sec_result.ok:
                return sec_result
        return VerificationResult(True, "Quality gate OK", language)

    def _run_tests(self, path: Path, language: Language) -> VerificationResult:
        profile = MultiLanguageVerifier.PROFILES[language]
        if not profile.test_command:
            return VerificationResult(True, "Sin tests", language)
        ok, msg, code, out, err = self.verifier._run(profile.test_command, cwd=self.workspace)
        if not ok:
            return VerificationResult(False, f"Tests fallidos: {msg}", language,
                                      code, out, err)
        return VerificationResult(True, "Tests OK", language)

    def _security_scan(self, path: Path, language: Language) -> VerificationResult:
        if language == Language.PYTHON:
            return self._python_security(path)
        return VerificationResult(True, "Security scan omitido", language)

    def _python_security(self, path: Path) -> VerificationResult:
        forbidden = {"eval", "exec", "compile", "__import__"}
        try:
            tree = compile(path.read_text(encoding="utf-8"), path.name, "exec")
        except SyntaxError as exc:
            return VerificationResult(False, f"SyntaxError: {exc}", Language.PYTHON)
        import ast
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in forbidden:
                    return VerificationResult(False, "Uso de eval/exec detectado",
                                              Language.PYTHON)
        return VerificationResult(True, "Security OK", Language.PYTHON)
