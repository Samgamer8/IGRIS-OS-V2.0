import difflib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from igris_os.files import RepositoryAnalyzer, RepositoryStager
from igris_os.programming.languages import PROFILES, LanguageVerifier
from igris_os.tools import safe_output


@dataclass(frozen=True, slots=True)
class RepositoryDevelopmentResult:
    ok: bool
    message: str
    staged_root: str = ""
    report: str = ""
    changed_files: tuple[str, ...] = ()


class RepositoryDeveloper:
    def __init__(self, client, workspace: Path, model: str) -> None:
        self.client, self.workspace, self.model = client, workspace.resolve(), model

    def propose(self, source: Path, objective: str, *,
                confirmed: bool = False,
                on_progress: Callable[[int, str], None] | None = None) -> RepositoryDevelopmentResult:
        if not confirmed:
            return RepositoryDevelopmentResult(False, "Se necesita confirmacion")
        if on_progress:
            on_progress(15, "Creando copia aislada")
        staged = RepositoryStager(self.workspace).stage(source, confirmed=True)
        root = Path(staged.root)
        if on_progress:
            on_progress(40, "Analizando repositorio aislado")
        analysis = RepositoryAnalyzer(self.workspace).analyze(root, objective)
        context = "\n\n".join(
            "ARCHIVO " + item["path"] + "\n" + item["excerpt"]
            for item in analysis.matches[:6])
        prompt = (
            "Devuelve solo JSON UTF-8 con cambios mínimos sobre copia aislada: "
            '{"summary":"resumen","changes":[{"path":"ruta relativa",'
            '"content":"archivo completo"}]}. Máximo 12 archivos, sin borrar. '
            "\nOBJETIVO:\n" + objective + "\nCONTEXTO:\n" + context)
        if on_progress:
            on_progress(60, "Generando propuesta de cambios")
        reply = self.client.generate(prompt, self.model)
        if not reply.ok:
            return RepositoryDevelopmentResult(
                False, reply.error or "Modelo no disponible", staged.root)
        try:
            raw = re.sub(r"^\s*```(?:json)?|```\s*$", "", reply.text,
                         flags=re.IGNORECASE).strip()
            package = json.loads(raw, strict=False)
            changes = package.get("changes")
            if not isinstance(changes, list) or not 1 <= len(changes) <= 12:
                raise ValueError("Paquete de cambios invalido")
            if on_progress:
                on_progress(80, "Aplicando y verificando cambios")
            return self._apply(root, package)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            return RepositoryDevelopmentResult(False, str(exc), staged.root)

    def _apply(self, root: Path, package: dict) -> RepositoryDevelopmentResult:
        backups, changed, diffs = {}, [], []
        try:
            for item in package["changes"]:
                relative = Path(str(item["path"])).as_posix().strip("/")
                content = str(item["content"])
                if not relative or len(content.encode("utf-8")) > 1_000_000:
                    raise ValueError("Cambio fuera de limites")
                target = (root / relative).resolve()
                if not target.is_relative_to(root) or any(
                        part in {".git", "runtime", "node_modules"}
                        for part in Path(relative).parts):
                    raise ValueError("Ruta de cambio no permitida")
                previous = (target.read_text(encoding="utf-8", errors="replace")
                            if target.is_file() else None)
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
        report = safe_output(self.workspace, "output/proposed_changes.diff")
        report.write_text("\n".join(diffs) + "\n", encoding="utf-8")
        return RepositoryDevelopmentResult(
            True, str(package.get("summary", "Cambios propuestos")),
            str(root), str(report), tuple(changed))

    @staticmethod
    def _verify(path: Path) -> None:
        language = next((name for name, profile in PROFILES.items()
                         if path.suffix.casefold() in profile.extensions), None)
        if not language:
            return
        check = LanguageVerifier().check(language, path)
        if not check.available:
            raise ValueError("Toolchain no disponible para " + language)
        if not check.ok:
            raise ValueError(check.message)
