from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True, slots=True)
class CompilationResult:
    ok: bool
    message: str
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    diagnostics: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class DependencyResult:
    ok: bool
    message: str
    installed: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    sbom: str = ""


class RealToolchain:
    COMMANDS: dict[str, dict[str, Sequence[str]]] = {
        "rust": {
            "build": ("cargo", "build", "--release"),
            "test": ("cargo", "test", "--release"),
            "check": ("cargo", "check", "--message-format=short"),
            "clippy": ("cargo", "clippy", "-q", "--", "-D", "warnings"),
            "doc": ("cargo", "doc", "--no-deps"),
        },
        "cpp": {
            "configure": ("cmake", "-B", "build", "-S", ".", "-DCMAKE_BUILD_TYPE=Release"),
            "build": ("cmake", "--build", "build", "--config", "Release"),
            "test": ("ctest", "--test-dir", "build", "--output-on-failure"),
        },
        "java": {
            "compile": ("mvn", "compile", "-q"),
            "test": ("mvn", "test", "-q"),
            "package": ("mvn", "package", "-DskipTests", "-q"),
        },
        "node": {
            "install": ("npm", "install"),
            "build": ("npm", "run", "build"),
            "test": ("npm", "test", "--silent"),
            "typecheck": ("npx", "tsc", "--noEmit"),
        },
        "python": {
            "lint": ("python", "-m", "pylint", "."),
            "typecheck": ("python", "-m", "mypy", "."),
            "test": ("python", "-m", "pytest", "-q"),
            "build": ("python", "setup.py", "bdist_wheel"),
        },
    }

    def __init__(self, root: Path, *, timeout: int = 120) -> None:
        self.root = root.resolve()
        self.timeout = timeout

    def build(self, language: str) -> CompilationResult:
        cmd = self._command(language, "build")
        if not cmd:
            return CompilationResult(False, f"Lenguaje sin build: {language}")
        return self._run(cmd, f"Build {language}")

    def test(self, language: str) -> CompilationResult:
        cmd = self._command(language, "test")
        if not cmd:
            return CompilationResult(False, f"Lenguaje sin tests: {language}")
        return self._run(cmd, f"Tests {language}")

    def check(self, language: str) -> CompilationResult:
        cmd = self._command(language, "check")
        if not cmd:
            return CompilationResult(True, f"Sin check para {language}")
        return self._run(cmd, f"Check {language}")

    def lint(self, language: str) -> CompilationResult:
        cmd = self._command(language, "clippy") or self._command(language, "lint")
        if not cmd:
            return CompilationResult(True, f"Sin lint para {language}")
        return self._run(cmd, f"Lint {language}")

    def diagnose(self, language: str, stderr: str) -> dict:
        diagnostics = []
        if language == "rust":
            diagnostics.extend(self._parse_rust_errors(stderr))
        elif language == "cpp":
            diagnostics.extend(self._parse_cpp_errors(stderr))
        elif language == "java":
            diagnostics.extend(self._parse_java_errors(stderr))
        elif language in ("node", "typescript", "javascript"):
            diagnostics.extend(self._parse_node_errors(stderr))
        elif language == "python":
            diagnostics.extend(self._parse_python_errors(stderr))
        return {"diagnostics": diagnostics, "count": len(diagnostics)}

    def dependencies(self, language: str) -> DependencyResult:
        if language == "rust":
            return self._cargo_dependencies()
        if language == "node":
            return self._node_dependencies()
        if language == "python":
            return self._python_dependencies()
        return DependencyResult(True, f"Sin gestor para {language}")

    def _command(self, language: str, action: str) -> Sequence[str] | None:
        return self.COMMANDS.get(language, {}).get(action)

    def _run(self, cmd: Sequence[str], label: str) -> CompilationResult:
        try:
            result = subprocess.run(
                list(cmd),
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
            ok = result.returncode == 0
            msg = "OK" if ok else result.stderr.strip() or result.stdout.strip()
            diag = self._extract_diagnostics(result.stdout + result.stderr)
            return CompilationResult(ok, msg, result.stdout.strip(),
                                     result.stderr.strip(), result.returncode, diag)
        except subprocess.TimeoutExpired:
            return CompilationResult(False, "timeout", diagnostics=("timeout",))
        except FileNotFoundError as exc:
            return CompilationResult(False, f"toolchain no encontrada: {exc}",
                                     diagnostics=(f"missing:{cmd[0]}",))
        except Exception as exc:
            return CompilationResult(False, str(exc), diagnostics=(str(exc),))

    @staticmethod
    def _extract_diagnostics(text: str) -> tuple[str, ...]:
        patterns = [
            r"error\[E\d+\]:.*",
            r"error:.*",
            r"warning:.*",
            r"^\s*>\s*.*",
            r"undefined reference to.*",
            r"fatal error:.*",
            r"Exception in thread.*",
        ]
        matches = []
        for pattern in patterns:
            matches.extend(re.findall(pattern, text, re.IGNORECASE | re.MULTILINE))
        return tuple(matches[:20])

    @staticmethod
    def _parse_rust_errors(text: str) -> tuple[str, ...]:
        return tuple(re.findall(r"error\[E\d+\]:.*", text))[:10]

    @staticmethod
    def _parse_cpp_errors(text: str) -> tuple[str, ...]:
        return tuple(re.findall(r"error:.*", text))[:10]

    @staticmethod
    def _parse_java_errors(text: str) -> tuple[str, ...]:
        return tuple(re.findall(r"ERROR.*|FAILURE.*", text))[:10]

    @staticmethod
    def _parse_node_errors(text: str) -> tuple[str, ...]:
        return tuple(re.findall(r"Error:.*|FAIL.*", text))[:10]

    @staticmethod
    def _parse_python_errors(text: str) -> tuple[str, ...]:
        return tuple(re.findall(r"Error:.*|Traceback.*", text))[:10]

    def _cargo_dependencies(self) -> DependencyResult:
        try:
            result = subprocess.run(
                ["cargo", "tree", "--depth", "1", "--format", "json"],
                cwd=self.root, capture_output=True, text=True, timeout=30, check=False,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                packages = [p["name"] for p in data if isinstance(p, dict)]
                return DependencyResult(True, "OK", tuple(packages), (),
                                        json.dumps(data, ensure_ascii=False))
            return DependencyResult(False, result.stderr.strip())
        except Exception as exc:
            return DependencyResult(False, str(exc))

    def _node_dependencies(self) -> DependencyResult:
        package = self.root / "package.json"
        if not package.exists():
            return DependencyResult(False, "Sin package.json")
        try:
            data = json.loads(package.read_text(encoding="utf-8"))
            deps = list(data.get("dependencies", {}).keys())
            dev_deps = list(data.get("devDependencies", {}).keys())
            return DependencyResult(True, "OK", tuple(deps + dev_deps), (),
                                    json.dumps(data, ensure_ascii=False))
        except Exception as exc:
            return DependencyResult(False, str(exc))

    def _python_dependencies(self) -> DependencyResult:
        requirements = self.root / "requirements.txt"
        if not requirements.exists():
            return DependencyResult(False, "Sin requirements.txt")
        try:
            lines = requirements.read_text(encoding="utf-8").splitlines()
            deps = [line.strip() for line in lines if line.strip() and not line.startswith("#")]
            return DependencyResult(True, "OK", tuple(deps), (),
                                    "\n".join(deps))
        except Exception as exc:
            return DependencyResult(False, str(exc))
