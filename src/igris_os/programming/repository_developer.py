import difflib
import json
import tomllib
import os
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath
from typing import Callable

from igris_os.files import RepositoryAnalyzer, RepositoryStager
from igris_os.programming.languages import MultiLanguageVerifier
from igris_os.tools import safe_output
from igris_os.programming.preflight import ProgrammingPreflight
from igris_os.programming.engineering_workflow import EngineeringWorkflow


REPAIR_SYSTEM = (
    "Eres ingeniero senior de reparacion autonoma. "
    "Corrige el archivo con cambios minimos. Devuelve SOLO JSON: "
    '{"path":"ruta","content":"contenido completo corregido"}. Sin markdown. '
    "No inventes resultados: conserva el comportamiento probado, identifica el "
    "riesgo principal y no elimines validaciones ni controles de seguridad."
)

CHANGE_PACKAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "changes": {
            "type": "array",
            "minItems": 1,
            "maxItems": 12,
            "items": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    "required": ["changes"],
}

_BLOCKED_PARTS = frozenset({
    ".git", ".staging", "runtime", "node_modules", "__pycache__",
    ".pytest_cache", ".venv", "venv", "build", "dist",
})


@dataclass(frozen=True, slots=True)
class RepositoryDevelopmentResult:
    ok: bool
    message: str
    staged_root: str = ""
    report: str = ""
    changed_files: tuple[str, ...] = ()
    attempts: int = 0
    diagnostics: tuple[str, ...] = field(default_factory=tuple)


class RepositoryDeveloper:
    def __init__(self, client, workspace: Path, model: str, *,
                 fallback_models: tuple[str, ...] = ()) -> None:
        self.client = client
        try:
            self.workspace = Path(str(workspace).strip()).resolve()
        except Exception:
            self.workspace = Path(os.getcwd()).resolve()
        self.model = model
        self.models = tuple(dict.fromkeys((model, *fallback_models)))

    def propose(self, source: Path, objective: str, *,
                confirmed: bool = False,
                on_progress: Callable[[int, str], None] | None = None
                ) -> RepositoryDevelopmentResult:
        if not confirmed:
            return RepositoryDevelopmentResult(False, "Se necesita confirmacion")
        preflight = ProgrammingPreflight().inspect(source)
        critical = [item for item in preflight.findings
                     if item.severity == "critical" and item.category != "syntax"]
        if critical:
            diagnostics = "; ".join(
                f"{item.path}: {item.message} ({item.evidence})"
                for item in critical[:8])
            return RepositoryDevelopmentResult(
                False, "Preflight bloqueado: " + diagnostics,
                diagnostics=("preflight_critical",))
        if on_progress:
            on_progress(15, "Creando copia aislada")
        staged = RepositoryStager(self.workspace).stage(source, confirmed=True)
        root = Path(staged.root)
        if on_progress:
            on_progress(40, "Analizando repositorio aislado")
        analysis = RepositoryAnalyzer(self.workspace).analyze(root, objective)
        selected = {item["path"] for item in analysis.matches[:8]}
        records = sorted(analysis.records, key=lambda item: (
            item["path"] not in selected, not item["path"].startswith("test"), item["path"]))
        parts, size = [], 0
        for item in records:
            content = (root / item["path"]).read_text(encoding="utf-8")
            block = "ARCHIVO " + item["path"] + "\n" + content
            if size + len(block) <= 60000:
                parts.append(block)
                size += len(block)
        context = "\n\n".join(parts)
        prompt = (
            "Devuelve solo JSON UTF-8 con cambios minimos sobre copia aislada: "
            '{"summary":"resumen","changes":[{"path":"ruta relativa",'
            '"content":"archivo completo"}]}. Maximo 12 archivos, sin borrar. '
            "\nOBJETIVO:\n" + objective + "\nCONTEXTO:\n" + context +
            "\nDIAGNOSTICO PREFLIGHT:\n" + "; ".join(
                f"{item.severity}: {item.path}: {item.message}"
                for item in preflight.findings[:12]) +
            "\nConsidera HECHO VERIFICADO, INFERENCIA, RIESGO, CAMBIO PROPUESTO "
            "y PRUEBA NECESARIA. No afirmes que funciona sin verificacion.")
        if on_progress:
            on_progress(60, "Generando propuesta de cambios")
        try:
            package = self._request_change_package(prompt)
            changes = package.get("changes")
            if not isinstance(changes, list) or not 1 <= len(changes) <= 12:
                raise ValueError("Paquete de cambios invalido")
            if on_progress:
                on_progress(80, "Aplicando y verificando cambios")
            return self._apply(root, package)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            return RepositoryDevelopmentResult(False, str(exc), staged.root)

    def repair(self, staged_root: Path, objective: str,
               diagnostics: str, max_attempts: int = 3,
               on_progress: Callable[[int, str], None] | None = None,
               immutable_paths: frozenset[str] = frozenset(),
               ) -> RepositoryDevelopmentResult:
        root = Path(staged_root).resolve()
        if not root.is_dir():
            return RepositoryDevelopmentResult(False, "Staging no valido")
        last_diag = diagnostics
        for attempt in range(1, min(5, max(1, max_attempts)) + 1):
            if on_progress:
                on_progress(40, f"Reparacion intento {attempt}")
            context = self._build_repair_context(
                root, objective, last_diag, immutable_paths)
            prompt = (
                REPAIR_SYSTEM +
                '\nTambien puedes devolver {"changes":[{"path":"ruta","content":"archivo completo"}]}. '
                "Conserva las pruebas de aceptacion. No sustituyas aserciones por True "
                "ni elimines pruebas para esconder fallos. Los archivos enumerados como "
                "PRUEBAS INMUTABLES no se pueden modificar.\nOBJETIVO:\n" + objective +
                "\nCODIGO ACTUAL PRIORIZADO:\n" + context +
                "\nDIAGNOSTICO:\n" + last_diag[-12000:])
            try:
                data = self._request_change_package(prompt)
                if "changes" not in data:
                    data = {"changes": [{"path": data["path"], "content": data["content"]}]}
                result = self._apply(root, data, immutable_paths=immutable_paths)
                return RepositoryDevelopmentResult(
                    True, "Cambios aplicados; pruebas pendientes", str(root),
                    result.report, result.changed_files, attempt, ("verification_pending",))
            except (ValueError, KeyError, TypeError, OSError) as exc:
                last_diag = str(exc)
        return RepositoryDevelopmentResult(
            False, "Reparacion fallida", str(root), diagnostics=(last_diag,))

    def _apply(self, root: Path, package: dict, *,
               immutable_paths: frozenset[str] = frozenset()
               ) -> RepositoryDevelopmentResult:
        backups, changed, diffs = {}, [], []
        changes = package.get("changes")
        if not isinstance(changes, list) or not 1 <= len(changes) <= 12:
            raise ValueError("Paquete de cambios invalido")
        seen = set()
        try:
            for item in package["changes"]:
                raw_path = str(item["path"]).replace("\\", "/")
                windows_path = PureWindowsPath(raw_path)
                if Path(raw_path).is_absolute() or windows_path.drive or ".." in Path(raw_path).parts:
                    raise ValueError("Ruta de cambio no permitida")
                relative = Path(raw_path).as_posix()
                if relative.casefold() in seen:
                    raise ValueError("Ruta de cambio duplicada")
                seen.add(relative.casefold())
                if not isinstance(item["content"], str):
                    raise ValueError("Contenido no textual")
                content = item["content"]
                if not relative or len(content.encode("utf-8")) > 1_000_000:
                    raise ValueError("Cambio fuera de limites")
                target = (root / relative).resolve()
                if not target.is_relative_to(root) or any(
                        part.casefold() in _BLOCKED_PARTS
                        for part in Path(relative).parts):
                    raise ValueError("Ruta de cambio no permitida")
                previous = (target.read_text(encoding="utf-8", errors="replace")
                            if target.is_file() else None)
                if relative.casefold() in immutable_paths and previous != content:
                    raise ValueError(
                        "Prueba de aceptacion inmutable: " + relative)
                if previous == content:
                    continue
                backups[target] = previous
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
                self._verify(target)
                changed.append(relative)
                diffs.extend(difflib.unified_diff(
                    (previous or "").splitlines(), content.splitlines(),
                    fromfile="a/" + relative, tofile="b/" + relative,
                    lineterm=""))
        except Exception:
            for path, previous in backups.items():
                if previous is None:
                    if path.is_file() and path.resolve().is_relative_to(root):
                        path.unlink()
                else:
                    path.write_text(previous, encoding="utf-8")
            raise
        if not changed:
            raise ValueError("El paquete no contiene cambios efectivos")
        report = safe_output(self.workspace, "output/proposed_changes.diff")
        report.write_text("\n".join(diffs) + "\n", encoding="utf-8")
        return RepositoryDevelopmentResult(
            True, str(package.get("summary", "Cambios propuestos")),
            str(root), str(report), tuple(changed))

    def verify_staged(self, staged_root: Path, *, timeout: int = 60
                      ) -> RepositoryDevelopmentResult:
        root = Path(staged_root).resolve()
        if not root.is_dir():
            return RepositoryDevelopmentResult(False, "Staging no valido")
        test_files = list(root.rglob("test_*.py")) + list(root.rglob("*_test.py"))
        if not test_files:
            return RepositoryDevelopmentResult(
                False, "No hay pruebas en el staging", str(root),
                diagnostics=("tests_missing",))
        result = EngineeringWorkflow().run(
            root, ("python", "-m", "pytest", "-q"),
            confirmed=True, timeout=timeout)
        if result.run is None:
            return RepositoryDevelopmentResult(
                False, result.reason, str(root),
                diagnostics=("tests_not_executed",))
        report = root / "verification_report.txt"
        report.write_text(
            "COMMAND: python -m pytest -q\n"
            f"RETURNCODE: {result.run.returncode}\n"
            f"TIMED_OUT: {result.run.timed_out}\n"
            f"SANDBOXED: {result.run.sandboxed}\n\n"
            "STDOUT:\n" + result.run.stdout[-12000:] +
            "\nSTDERR:\n" + result.run.stderr[-12000:],
            encoding="utf-8")
        ok = result.run.returncode == 0 and not result.run.timed_out
        return RepositoryDevelopmentResult(
            ok, "Pruebas del staging " + ("aprobadas" if ok else "fallidas"),
            str(root), str(report), (),
            diagnostics=("tests_passed" if ok else "tests_failed",))

    def repair_until_verified(self, staged_root: Path, objective: str,
                              diagnostics: str, *, max_attempts: int = 3,
                              timeout: int = 60,
                              on_progress: Callable[[int, str], None] | None = None
                              ) -> RepositoryDevelopmentResult:
        root = Path(staged_root).resolve()
        if not root.is_dir():
            return RepositoryDevelopmentResult(False, "Staging no valido")
        snapshot = {
            path.relative_to(root): path.read_bytes()
            for path in root.rglob("*") if path.is_file() and not path.is_symlink()
            and path.resolve().is_relative_to(root)
        }
        immutable_paths = frozenset(
            relative.as_posix().casefold()
            for relative in snapshot
            if self._is_acceptance_test(relative)
        )
        last = diagnostics
        for attempt in range(1, max(1, max_attempts) + 1):
            if on_progress:
                on_progress(
                    min(90, 55 + int(30 * attempt / max(1, max_attempts))),
                    f"Reparando y verificando intento {attempt}")
            repaired = self.repair(
                root, objective, last, max_attempts=1,
                immutable_paths=immutable_paths)
            if not repaired.ok:
                last = repaired.message + "\n" + "; ".join(repaired.diagnostics)
                continue
            checked = self.verify_staged(root, timeout=timeout)
            if checked.ok:
                changed = tuple(
                    relative for relative in self._detect_changes(root)
                    if relative not in {"verification_report.txt", "repair_report.diff"}
                    and snapshot.get(Path(relative)) != (root / relative).read_bytes()
                )
                report = self._build_diff_report(root, snapshot, changed)
                return RepositoryDevelopmentResult(
                    True, "Reparacion verificada", str(root),
                    str(report), changed, attempt,
                    ("tests_passed",))
            last = ((Path(checked.report).read_text(encoding="utf-8")[-12000:]
                     if checked.report else "; ".join(checked.diagnostics))
                    + "\n" + repaired.message + "\n" + "; ".join(repaired.diagnostics))
        for path in list(root.rglob("*")):
            if path.is_file() and path.relative_to(root) not in snapshot:
                path.unlink()
        for relative, content in snapshot.items():
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        return RepositoryDevelopmentResult(
            False, "Reparacion no verificada; staging restaurado", str(root),
            diagnostics=("rollback", last))

    @staticmethod
    def _verify(path: Path) -> None:
        if path.suffix.casefold() == ".json":
            json.loads(path.read_text(encoding="utf-8"))
            return
        if path.suffix.casefold() == ".toml":
            tomllib.loads(path.read_text(encoding="utf-8"))
            return
        if path.suffix.casefold() in {".md", ".txt", ".yaml", ".yml", ".ini", ".cfg"}:
            return
        verifier = MultiLanguageVerifier(path.parent)
        result = verifier.verify(path)
        if not result.ok:
            raise ValueError(result.message)

    def _request_change_package(self, prompt: str) -> dict:
        from igris_os.utils.json_parser import StrictJSONParser

        generate_json = getattr(self.client, "generate_json", None)
        generate = getattr(self.client, "generate", None)
        errors: list[str] = []
        for model in self.models:
            active_prompt = prompt
            if callable(generate_json):
                reply = generate_json(
                    active_prompt, model, CHANGE_PACKAGE_SCHEMA)
                if reply.ok:
                    try:
                        return StrictJSONParser.extract(reply.text)
                    except (TypeError, ValueError, json.JSONDecodeError) as exc:
                        errors.append(f"{model}: JSON estructurado invalido: {exc}")
                        active_prompt += (
                            "\nLa respuesta estructurada anterior era invalida. "
                            "Devuelve un unico objeto JSON valido sin markdown.")
                else:
                    errors.append(f"{model}: {reply.error or 'sin respuesta estructurada'}")
            if not callable(generate):
                continue
            reply = generate(active_prompt, model)
            if not reply.ok:
                errors.append(f"{model}: {reply.error or 'modelo no disponible'}")
                continue
            try:
                return StrictJSONParser.extract(reply.text)
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                errors.append(f"{model}: JSON invalido: {exc}")
        if not callable(generate_json) and not callable(generate):
            raise ValueError("El cliente no puede generar cambios")
        raise ValueError(
            "Ningun modelo instalado produjo cambios validos: " +
            " | ".join(errors[-8:]))

    def _build_repair_context(
            self, root: Path, objective: str, diagnostics: str,
            immutable_paths: frozenset[str]) -> str:
        analysis = RepositoryAnalyzer(self.workspace).analyze(
            root, objective + "\n" + diagnostics[-4000:])
        match_order = {
            item["path"]: index for index, item in enumerate(analysis.matches)
        }
        tests = set(analysis.tests)
        records = sorted(
            analysis.records,
            key=lambda item: (
                0 if item["path"] in match_order else 1,
                match_order.get(item["path"], 999),
                0 if item["path"] in tests else 1,
                item["path"],
            ),
        )
        parts: list[str] = []
        size = 0
        if immutable_paths:
            listed = "\n".join(sorted(immutable_paths))
            parts.append("PRUEBAS INMUTABLES:\n" + listed)
            size += len(parts[-1])
        for item in records:
            path = root / item["path"]
            if path.suffix.casefold() not in {
                    ".py", ".json", ".toml", ".md", ".txt",
                    ".js", ".ts", ".yaml", ".yml", ".ini", ".cfg"}:
                continue
            if path.stat().st_size > 200_000:
                continue
            content = path.read_text(encoding="utf-8", errors="replace")
            block = "ARCHIVO " + item["path"] + "\n" + content
            if size + len(block) > 60_000:
                continue
            parts.append(block)
            size += len(block)
        return "\n\n".join(parts)

    @staticmethod
    def _detect_changes(root: Path) -> list[str]:
        changed = []
        for path in root.rglob("*"):
            if (path.is_file() and not path.is_symlink()
                    and path.resolve().is_relative_to(root)
                    and not any(part in {".git", "__pycache__", ".pytest_cache", ".venv", "node_modules"}
                                for part in path.relative_to(root).parts)):
                changed.append(str(path.relative_to(root)).replace("\\", "/"))
        return sorted(changed)[:100]

    @staticmethod
    def _is_acceptance_test(relative: Path) -> bool:
        parts = tuple(part.casefold() for part in relative.parts)
        name = relative.name.casefold()
        return (
            any(part in {"test", "tests"} for part in parts[:-1])
            or name.startswith("test_")
            or name.endswith("_test.py")
            or ".test." in name
            or ".spec." in name
        )

    def _build_diff_report(
            self, root: Path, snapshot: dict[Path, bytes],
            changed: tuple[str, ...]) -> Path:
        report = safe_output(self.workspace, "output/repository_repair.diff")
        lines: list[str] = []
        for rel in changed:
            path = root / rel
            if path.is_file():
                before = snapshot.get(Path(rel), b"")
                after = path.read_bytes()
                try:
                    before_lines = before.decode("utf-8").splitlines()
                    after_lines = after.decode("utf-8").splitlines()
                except UnicodeDecodeError:
                    lines.append(f"BINARY CHANGED: {rel}")
                    continue
                lines.extend(difflib.unified_diff(
                    before_lines, after_lines,
                    fromfile="a/" + rel, tofile="b/" + rel,
                    lineterm=""))
        report.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return report
