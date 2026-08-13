import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class LanguageProfile:
    name: str
    extensions: tuple[str, ...]
    executable: str
    check_args: tuple[str, ...]


PROFILES = {
    "python": LanguageProfile("python", (".py",), sys.executable,
                              ("-I", "-m", "py_compile")),
    "javascript": LanguageProfile("javascript", (".js",), "node", ("--check",)),
    "typescript": LanguageProfile("typescript", (".ts", ".tsx"), "npx",
                                  ("tsc", "--noEmit", "--pretty", "false")),
    "rust": LanguageProfile("rust", (".rs",), "rustc",
                            ("--crate-type", "lib", "--emit", "metadata")),
    "cpp": LanguageProfile("cpp", (".cpp", ".cc"), "g++",
                           ("-fsyntax-only",)),
    "java": LanguageProfile("java", (".java",), "javac", ("-Xlint",)),
}


@dataclass(frozen=True, slots=True)
class LanguageCheck:
    ok: bool
    available: bool
    message: str


class LanguageVerifier:
    def profiles(self) -> tuple[LanguageProfile, ...]:
        return tuple(PROFILES.values())

    def check(self, language: str, source: Path,
              *, timeout: int = 30) -> LanguageCheck:
        profile = PROFILES.get(language.casefold())
        if profile is None:
            return LanguageCheck(False, False, "Lenguaje no registrado")
        executable = profile.executable if Path(profile.executable).is_file() else shutil.which(profile.executable)
        if not executable:
            return LanguageCheck(False, False, "Herramienta no instalada")
        if source.suffix.casefold() not in profile.extensions or not source.is_file():
            return LanguageCheck(False, True, "Fuente incompatible")
        command = [executable, *profile.check_args, str(source.resolve())]
        try:
            run = subprocess.run(command, cwd=source.parent, capture_output=True,
                                 text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return LanguageCheck(False, True, "Verificacion agotó el tiempo")
        return LanguageCheck(run.returncode == 0, True,
                             "Sintaxis valida" if run.returncode == 0
                             else (run.stdout + run.stderr)[-1500:])
