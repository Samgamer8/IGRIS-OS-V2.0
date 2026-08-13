import ast
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


FORBIDDEN = {"eval", "exec", "compile", "__import__"}
FORBIDDEN_IMPORTS = {"subprocess", "socket", "ctypes", "shutil"}
FORBIDDEN_ATTRIBUTES = {
    "system", "popen", "spawn", "remove", "removedirs", "rmdir",
    "unlink", "rmtree", "rename", "replace", "chmod", "chown",
}


@dataclass(frozen=True, slots=True)
class Verification:
    ok: bool
    message: str
    sha256: str = ""


class PythonWorkshop:
    def __init__(self, root: Path, timeout: int = 20) -> None:
        self.root = root.resolve()
        self.timeout = timeout

    def verify(self, source: str, tests: str) -> Verification:
        try:
            trees = (ast.parse(source), ast.parse(tests))
        except SyntaxError as exc:
            return Verification(False, f"SyntaxError: {exc}")
        for tree in trees:
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    names = ([a.name.split(".")[0] for a in node.names]
                             if isinstance(node, ast.Import)
                             else [str(node.module).split(".")[0]])
                    if FORBIDDEN_IMPORTS.intersection(names):
                        return Verification(False, "Importacion peligrosa")
                if isinstance(node, ast.Call):
                    if (isinstance(node.func, ast.Name) and
                            node.func.id in FORBIDDEN):
                        return Verification(
                            False, "Ejecucion dinamica bloqueada")
                    if (isinstance(node.func, ast.Attribute) and
                            node.func.attr in FORBIDDEN_ATTRIBUTES):
                        return Verification(
                            False, "Operacion de sistema bloqueada")
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "solution.py").write_text(source, encoding="utf-8")
        (self.root / "test_solution.py").write_text(tests, encoding="utf-8")
        try:
            runner = (
                "import sys,unittest;"
                f"sys.path.insert(0,{str(self.root)!r});"
                "suite=unittest.defaultTestLoader.discover(sys.path[0],pattern='test_solution.py');"
                "r=unittest.TextTestRunner().run(suite);"
                "raise SystemExit(0 if r.wasSuccessful() else 1)"
            )
            run = subprocess.run(
                [sys.executable, "-I", "-c", runner],
                cwd=self.root, capture_output=True, text=True, timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            return Verification(False, "Pruebas agotaron el tiempo")
        if run.returncode:
            return Verification(False, (run.stdout + run.stderr)[-2000:])
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
        (self.root / "verification.json").write_text(
            json.dumps({"sha256": digest, "tests_passed": True}, indent=2),
            encoding="utf-8",
        )
        return Verification(True, "Codigo verificado", digest)
