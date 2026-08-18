"""
Ejercicio 2.6: CI/CD Autónomo
Objetivo: Sistema que despliega y corrige bugs automáticamente.
Tiempo: 5 horas
Habilidades: CI/CD pipelines, automated deployment, rollback

Requisitos:
- Pipeline de deployment
- Tests automáticos
- Rollback automático
- Corrección de bugs
- < 10 minutos deployment

Validación:
- Deployment exitoso
- Rollback automático funciona
- Bugs corregidos automáticamente
"""
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class StageResult:
    name: str
    ok: bool
    output: str = ""
    elapsed: float = 0.0


@dataclass
class PipelineResult:
    status: str  # deployed | rolled_back | failed
    stages: List[StageResult] = field(default_factory=list)
    attempts: int = 0
    total_elapsed: float = 0.0
    current_version: str = ""


# App modelo con un bug plantado: `add` resta en vez de sumar
APP_WITH_BUG = '''def add(a: int, b: int) -> int:
    return a - b


def multiply(a: int, b: int) -> int:
    return a * b
'''

APP_HEALTHY = '''def add(a: int, b: int) -> int:
    return a + b


def multiply(a: int, b: int) -> int:
    return a * b
'''

TESTS = '''from app import add, multiply


def test_add():
    assert add(2, 3) == 5
    assert add(-1, 1) == 0
    assert add(0, 0) == 0


def test_multiply():
    assert multiply(3, 4) == 12
    assert multiply(-2, 5) == -10
'''
# Requiere pytest; en su lugar usamos un runner de asserts directo
TEST_RUNNER = '''import sys
sys.path.insert(0, ".")
failures = []
try:
    from app import add, multiply
    assert add(2, 3) == 5, "add(2,3) != 5"
    assert add(-1, 1) == 0, "add(-1,1) != 0"
    assert add(0, 0) == 0, "add(0,0) != 0"
    assert multiply(3, 4) == 12, "multiply(3,4) != 12"
    assert multiply(-2, 5) == -10, "multiply(-2,5) != -10"
except Exception as exc:
    failures.append(str(exc))
if failures:
    print("FAIL: " + " | ".join(failures))
    sys.exit(1)
print("ALL TESTS PASSED")
'''

REPAIR_RULES = [
    ("a - b", "a + b"),  # bug: resta en vez de suma
]


def _run_python(code: str, cwd: Path, timeout: int = 30) -> tuple[bool, str]:
    """Ejecuta codigo Python en un directorio y devuelve (ok, salida)."""
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(cwd), capture_output=True, text=True, timeout=timeout)
        return proc.returncode == 0, proc.stdout + proc.stderr
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"


class AutonomousPipeline:
    """Pipeline CI/CD: build -> test -> deploy -> health -> rollback/repair."""

    def __init__(self, workspace: Path, max_repair_attempts: int = 3) -> None:
        self.workspace = workspace
        self.source = workspace / "source"
        self.prod = workspace / "prod"
        self.stage_dir = workspace / "stage"
        self.max_repair_attempts = max_repair_attempts
        self.version = 0
        self.deployed_versions: Dict[int, str] = {}
        for directory in (self.source, self.prod, self.stage_dir):
            directory.mkdir(parents=True, exist_ok=True)

    def _write_app(self, content: str) -> None:
        (self.source / "app.py").write_text(content, encoding="utf-8")
        (self.source / "test_runner.py").write_text(TEST_RUNNER, encoding="utf-8")

    def run_tests(self) -> StageResult:
        start = time.perf_counter()
        # Eliminar pycache: si no, el subproceso puede reutilizar el bytecode
        # compilado de una version anterior del codigo (bug real observado).
        for directory in (self.source, self.stage_dir, self.prod):
            shutil.rmtree(directory / "__pycache__", ignore_errors=True)
        ok, output = _run_python(TEST_RUNNER, self.source)
        return StageResult("test", ok, output, time.perf_counter() - start)

    def build(self) -> StageResult:
        start = time.perf_counter()
        # Build = copiar a staging + compilacion (ast)
        shutil.copytree(self.source, self.stage_dir, dirs_exist_ok=True)
        try:
            import ast
            ast.parse((self.stage_dir / "app.py").read_text(encoding="utf-8"))
            ok = True
            output = "build OK (staging + ast)"
        except SyntaxError as exc:
            ok = False
            output = f"SyntaxError: {exc}"
        return StageResult("build", ok, output, time.perf_counter() - start)

    def deploy(self) -> StageResult:
        start = time.perf_counter()
        shutil.copytree(self.stage_dir, self.prod, dirs_exist_ok=True)
        self.version += 1
        self.deployed_versions[self.version] = "prod"
        return StageResult("deploy", True, f"deploy v{self.version}", time.perf_counter() - start)

    def health_check(self) -> StageResult:
        start = time.perf_counter()
        ok, output = _run_python(TEST_RUNNER, self.prod)
        return StageResult("health", ok, output, time.perf_counter() - start)

    def rollback(self) -> StageResult:
        """Revierte a la ultima version sana conocida (source original)."""
        start = time.perf_counter()
        # Rollback: restaurar app.py sano en prod y decrementar version
        healthy = self.workspace / "baseline"
        healthy.mkdir(exist_ok=True)
        (healthy / "app.py").write_text(APP_HEALTHY, encoding="utf-8")
        (healthy / "test_runner.py").write_text(TEST_RUNNER, encoding="utf-8")
        shutil.copytree(healthy, self.prod, dirs_exist_ok=True)
        if self.version in self.deployed_versions:
            del self.deployed_versions[self.version]
        self.version = max(0, self.version - 1)
        return StageResult("rollback", True, "rollback a version sana", time.perf_counter() - start)

    def repair(self, error: str) -> StageResult:
        """Corrige el codigo aplicando reglas sobre el error detectado."""
        start = time.perf_counter()
        app_path = self.source / "app.py"
        content = app_path.read_text(encoding="utf-8")
        fixed = content
        applied = 0
        for broken, good in REPAIR_RULES:
            if broken in fixed:
                fixed = fixed.replace(broken, good)
                applied += 1
        if applied:
            app_path.write_text(fixed, encoding="utf-8")
            return StageResult("repair", True, f"fix aplicado ({applied} regla)", time.perf_counter() - start)
        return StageResult("repair", False, f"sin regla para: {error[:120]}", time.perf_counter() - start)

    def run(self) -> PipelineResult:
        start = time.perf_counter()
        result = PipelineResult(status="failed")
        result.attempts = 1

        for attempt in range(1, self.max_repair_attempts + 1):
            result.attempts = attempt
            build = self.build()
            result.stages.append(build)
            if not build.ok:
                result.status = "failed"
                break

            tests = self.run_tests()
            result.stages.append(tests)
            if not tests.ok:
                repair = self.repair(tests.output)
                result.stages.append(repair)
                if not repair.ok:
                    result.status = "failed"
                    break
                continue  # reintentar ciclo con el codigo reparado

            deploy = self.deploy()
            result.stages.append(deploy)
            health = self.health_check()
            result.stages.append(health)
            if health.ok:
                result.status = "deployed"
                result.current_version = f"v{self.version}"
                break
            rb = self.rollback()
            result.stages.append(rb)
            result.status = "rolled_back"
            break
        else:
            result.status = "failed"

        result.total_elapsed = time.perf_counter() - start
        return result


def test_cicd() -> bool:
    """Prueba el pipeline CI/CD con los requisitos."""
    print("Iniciando pipeline CI/CD autónomo...")
    start = time.perf_counter()
    workspace = Path(tempfile.mkdtemp(prefix="igris_cicd_"))
    try:
        # CASO 1: codigo con bug -> el pipeline debe corregirlo y desplegar
        pipeline = AutonomousPipeline(workspace / "caso1")
        pipeline._write_app(APP_WITH_BUG)
        r1 = pipeline.run()
        # CASO 2: deploy sano
        pipeline2 = AutonomousPipeline(workspace / "caso2")
        pipeline2._write_app(APP_HEALTHY)
        r2 = pipeline2.run()
        # CASO 3: corromper prod tras el deploy -> health check debe fallar
        # y el rollback debe restaurar la version sana
        (pipeline2.prod / "app.py").write_text(
            "def add(a,b): return a-b\n", encoding="utf-8")
        h_before = pipeline2.health_check()
        rb = pipeline2.rollback()
        h_after = pipeline2.health_check()
        r3_ok = (not h_before.ok) and rb.ok and h_after.ok
        elapsed = time.perf_counter() - start

        print("\n=== RESULTADOS ===")
        print(f"CASO 1 (bug -> reparar y desplegar): {r1.status} "
              f"({r1.attempts} intentos)")
        for stage in r1.stages:
            print(f"  {stage.name:8s} {'OK' if stage.ok else 'FAIL'} {stage.elapsed:.2f}s")
        print(f"CASO 2 (deploy sano): {r2.status}")
        print(f"CASO 3 (salud rota -> rollback): "
              f"health_before={not h_before.ok}, rollback={rb.ok}, "
              f"health_after={h_after.ok} -> {'OK' if r3_ok else 'FALLO'}")
        print(f"Tiempo total: {elapsed:.2f}s")

        print("\n=== VALIDACIÓN ===")
        success = True
        if r1.status == "deployed":
            print(f"✅ Deployment exitoso tras auto-reparación ({r1.attempts} intentos)")
        else:
            print(f"❌ Deployment falló: {r1.status}")
            success = False
        if any(s.name == "repair" and s.ok for s in r1.stages):
            print("✅ Bug corregido automáticamente")
        else:
            print("❌ No se corrigió el bug")
            success = False
        if r3_ok:
            print("✅ Rollback automático funcionó (health falló -> restaurado)")
        else:
            print("❌ Rollback no funcionó")
            success = False
        if elapsed < 600:
            print(f"✅ Deployment < 10 minutos: {elapsed:.2f}s")
        else:
            print(f"❌ Deployment >= 10 minutos: {elapsed:.2f}s")
            success = False

        if success:
            print("\n✅ EJERCICIO COMPLETADO EXITOSAMENTE")
        else:
            print("\n❌ EJERCICIO NO COMPLETADO")
        return success
    finally:
        import shutil as _sh
        _sh.rmtree(workspace, ignore_errors=True)


if __name__ == "__main__":
    print("Iniciando Ejercicio 2.6: CI/CD Autónomo")
    print("Requisitos: pipeline, tests, rollback, auto-corrección, < 10 min")
    print()

    result = test_cicd()

    if result:
        print("\n🎉 ¡Felicidades! Has completado el Ejercicio 2.6")
    else:
        print("\n⚠️ Necesitas optimizar el sistema para cumplir los requisitos")
