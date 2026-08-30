from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from igris_os.games.factory import GodotProjectFactory
from igris_os.games.runtime import GodotRuntime
from igris_os.games.verified_3d import VerifiedGodot3DFactory
from igris_os.utils.json_parser import StrictJSONParser


@dataclass(frozen=True, slots=True)
class GameDevelopmentResult:
    ok: bool
    message: str
    project: Path | None = None
    changed_files: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()


class GodotGameDeveloper:
    """Genera código Godot completo en un staging y rechaza texto no aplicable."""

    _ALLOWED_SUFFIXES = frozenset({".gd", ".tscn", ".md"})
    _MAX_FILES = 48
    _MAX_FILE_BYTES = 256_000
    _MAX_ATTEMPTS = 2

    def __init__(self, client, workspace: Path, model: str) -> None:
        self.client = client
        self.workspace = workspace.resolve()
        self.model = model

    def develop(self, objective: str, name: str, *, genre: str = "top_down",
                confirmed: bool = False) -> GameDevelopmentResult:
        if not confirmed:
            return GameDevelopmentResult(False, "Se necesita confirmacion")
        normalized_genre = genre.casefold().strip().replace("-", "_")
        if normalized_genre.endswith("_3d") or normalized_genre == "3d":
            project = VerifiedGodot3DFactory(self.workspace).create(
                name, confirmed=True)
        else:
            project = GodotProjectFactory(self.workspace).create(
                name, genre=genre, confirmed=True)
        prompt = (
            "Eres el programador de un proyecto Godot 4. Entrega código, no una explicación. "
            "Completa el proyecto inicial para cumplir exactamente el encargo. "
            "Devuelve SOLO JSON con formato "
            '{"files":[{"path":"main.gd","content":"codigo completo"}]}. '
            "Incluye todos los scripts y escenas necesarios, reglas y estados del juego. "
            "No incluyas assets binarios, rutas absolutas, .godot ni project.godot. "
            "Los archivos permitidos son .gd, .tscn y README.md. "
            "El archivo main.gd debe ser una implementación funcional, no pseudocódigo.\n\n"
            "ENCARGO:\n" + objective + "\nGENERO:\n" + genre
        )
        schema = {
            "type": "object",
            "properties": {"files": {"type": "array", "items": {
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"],
            }}},
            "required": ["files"],
        }
        generate_json = getattr(self.client, "generate_json", None)
        diagnostics: list[str] = []
        changed: list[str] = []
        for attempt in range(1, self._MAX_ATTEMPTS + 1):
            attempt_prompt = prompt
            if diagnostics:
                attempt_prompt += (
                    "\n\nLA ENTREGA ANTERIOR FALLO: " + diagnostics[-1] +
                    "\nCorrige el paquete completo. No expliques nada fuera del JSON.")
            reply = (generate_json(attempt_prompt, self.model, schema)
                     if callable(generate_json)
                     else self.client.generate(attempt_prompt, self.model))
            if not reply.ok:
                diagnostics.append(reply.error or "model_unavailable")
                continue
            try:
                package = StrictJSONParser.extract(reply.text)
                files = package.get("files")
                if isinstance(files, dict):
                    files = [{"path": path, "content": content}
                             for path, content in files.items()]
                if not isinstance(files, list) or not 1 <= len(files) <= self._MAX_FILES:
                    raise ValueError(
                        "files debe contener entre 1 y " + str(self._MAX_FILES) +
                        " archivos")
                changed = self._write_files(project, files)
                if "main.gd" not in changed:
                    raise ValueError("Falta main.gd en la entrega")
                break
            except (ValueError, TypeError, KeyError) as exc:
                diagnostics.append(f"intento {attempt}: {exc}")
        else:
            return GameDevelopmentResult(
                False, "El modelo no entrego código Godot aplicable", project,
                diagnostics=tuple(diagnostics))
        runtime = GodotRuntime()
        if runtime.available:
            check = runtime.run(project, frames=2)
            if not check.ok:
                return GameDevelopmentResult(
                    False, "El código generado no inicia en Godot", project,
                    tuple(changed), tuple(diagnostics + [check.output[-1200:]]))
        (project / "CODE_DELIVERY.json").write_text(json.dumps({
            "model": self.model,
            "generated_files": changed,
            "godot_checked": runtime.available,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        return GameDevelopmentResult(
            True, "Código Godot generado", project, tuple(changed))

    def _write_files(self, project: Path, files: list[object]) -> list[str]:
        changed: list[str] = []
        for item in files:
            if not isinstance(item, dict):
                raise ValueError("Elemento de archivo inválido")
            relative = Path(str(item.get("path", "")).replace("\\", "/"))
            content = str(item.get("content", ""))
            target = (project / relative).resolve()
            if (not relative.name or relative.is_absolute() or
                    not target.is_relative_to(project) or
                    target.suffix.casefold() not in self._ALLOWED_SUFFIXES or
                    relative.as_posix() == "project.godot"):
                raise ValueError("Ruta de código no permitida: " + relative.as_posix())
            if not content.strip() or len(content.encode("utf-8")) > self._MAX_FILE_BYTES:
                raise ValueError("Contenido inválido: " + relative.as_posix())
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            changed.append(relative.as_posix())
        return changed
