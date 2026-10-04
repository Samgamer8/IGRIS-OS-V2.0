"""Build a reproducible playable chess baseline, verified by the installed Godot.

A fixed game family must not spend LLM calls reinventing its foundational rules.
Unrelated generators keep their model-based workflows. User edits are retained
on subsequent baseline resumes and must pass the same integration checks.
"""
from __future__ import annotations

import hashlib
from importlib.resources import files
import json
import os
from pathlib import Path
from uuid import uuid4

from igris_os.games.chess_state import CHESS_STATE_SOURCE
from igris_os.games.runtime import GodotRuntime
from igris_os.games.sequential_developer import CHESS_COMPONENTS, SequentialGameResult

BASELINE_ID = "igris_medieval_chess_1"


def baseline_sources() -> dict[str, str]:
    root = files("igris_os.games").joinpath("chess_baseline")
    result = {p.name: p.read_text(encoding="utf-8") for p in root.iterdir()
              if p.is_file() and p.name != "__init__.py" and p.name.endswith((".gd", ".godot", ".tscn", ".md"))}
    result["chess_state.gd"] = CHESS_STATE_SOURCE
    return result


class BundledChessDeveloper:
    def __init__(self, workspace, runtime=None, on_progress=None):
        self.workspace = Path(workspace).resolve()
        self.runtime = runtime or GodotRuntime(timeout=180)
        self.on_progress = on_progress
        self.task_payload = {}

    def _project_path(self, name):
        safe = "".join(c for c in name if c.isalnum() or c in " _-").strip().replace(" ", "_")
        if not safe:
            raise ValueError("Nombre de proyecto invalido")
        return self.workspace / safe

    def develop_chess_3d(self, objective, name, *, confirmed=False, resume=False):
        if not confirmed:
            return SequentialGameResult(False, "Se necesita confirmacion")
        if not self.runtime.available:
            return SequentialGameResult(False, "Falta Godot para comprobar el proyecto")
        project = self._project_path(name)
        if project.exists() and not resume:
            return SequentialGameResult(False,"Ya existe el proyecto; reanuda para conservarlo",project)
        state = {"version":2, "strategy":BASELINE_ID,"complete":False,"components":{},
                 "budget":{"calls":0},"state":"preparing","current_component":""}
        written = []
        evidence = []

        def progress(percentage, message, component=""):
            state.update(state="working",current_component=component,message=message)
            self._save(project / "IGRIS_PROGRESS.json",state)
            if self.on_progress: self.on_progress(percentage,message)

        try:
            project.mkdir(parents=True,exist_ok=True)
            manifest_path = project / "IGRIS_BASELINE.json"
            old = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
            if old and (old.get("id") != BASELINE_ID or not isinstance(old.get("hashes"),dict)):
                raise ValueError("El manifiesto de la base es incompatible; se conserva el proyecto")
            sources = baseline_sources()
            backup = project / "IGRIS_PREVIOUS" / uuid4().hex
            replaced = []

            def preserve(path):
                if path.is_symlink(): raise ValueError("No se sustituye un enlace: " + str(path))
                relative = path.relative_to(project).as_posix()
                saved = backup / (relative + ".previous")
                saved.parent.mkdir(parents=True,exist_ok=True)
                saved.write_bytes(path.read_bytes())
                replaced.append(relative)

            # Legacy six visual files are superseded by the shared articulated
            # factory. Archive only these owned names, so Godot cannot import
            # rejected obsolete scripts from the old project.
            if not old:
                for component in CHESS_COMPONENTS:
                    path = project / component.path
                    if component.path not in sources and path.is_file():
                        preserve(path)
                        path.unlink()
            hashes = {}
            for index, (relative, text) in enumerate(sorted(sources.items())):
                path = project / relative
                data = text.encode("utf-8")
                digest = hashlib.sha256(data).hexdigest()
                if path.is_symlink(): raise ValueError("No se sustituye un enlace: " + str(path))
                current = path.read_bytes() if path.exists() else None
                previous_hash = old.get("hashes",{}).get(relative)
                modified = current is not None and previous_hash and hashlib.sha256(current).hexdigest() != previous_hash
                if modified:
                    state["components"][relative] = "user_change_preserved_pending_check"
                    # Retain the old base hash so future resumes still detect edits.
                    hashes[relative] = previous_hash
                else:
                    if current is not None and current != data: preserve(path)
                    if current != data: path.write_bytes(data)
                    state["components"][relative] = "existing" if current == data else "bundled"
                    hashes[relative] = digest
                written.append(relative)
                progress(5 + int(index*25/len(sources)),"Preparando base jugable: " + relative,relative)
            self._save(manifest_path,{"id":BASELINE_ID,"hashes":hashes,"preserved_previous":str(backup) if replaced else ""})
            self._save(project / "IGRIS_TASK.json",{"objective":objective,"payload":self.task_payload})
            # Use the checked source. The export capability switches this to the
            # EXE only after a successful fresh export (never an old build).
            executable = str(self.runtime.executable) if getattr(self.runtime,"executable",None) else ""
            self._save(project / "IGRIS_GODOT.json",{"executable":executable})
            launcher = """@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0"
powershell -NoProfile -Command "$c=Get-Content -LiteralPath 'IGRIS_GODOT.json' -Raw | ConvertFrom-Json; if (-not (Test-Path -LiteralPath $c.executable)) { throw 'No se encuentra Godot; abre project.godot desde el editor' }; & $c.executable --path (Get-Location).Path"
if errorlevel 1 pause
""".replace("\n", "\r\n")
            (project / "JUGAR.cmd").write_bytes(launcher.encode("utf-8"))
            checks = [("import", lambda: self.runtime.import_project(project), "Importando el proyecto completo"),
                      ("gameplay", lambda: self._verify_game(project,sources["verify_game.gd"]), "Comprobando reglas, seleccion, captura animada y guardado"),
                      ("boot", lambda: self.runtime.run(project,frames=30,headless=True), "Comprobando el arranque del juego")]
            for index,(phase, check, message) in enumerate(checks):
                progress(45+index*20,message,phase)
                result = check()
                evidence.append({"phase":phase,"ok":result.ok,"output":result.output[-12000:]})
                self._save(project / "IGRIS_VERIFICATION.json",{"godot_version":self.runtime.version(),"checks":evidence,"full_artistic_acceptance":False})
                if not result.ok or (phase == "gameplay" and "IGRIS_CHESS_ACCEPTANCE_OK" not in result.output):
                    raise ValueError("No se supero " + phase + ":\n" + result.output[-6000:])
            for key in state["components"]:
                state["components"][key] += "_verified"
            state.update(state="playable_verified",current_component="",complete=True,message="Ajedrez jugable comprobado; listo para abrir",
                         playable_verified=True,full_artistic_acceptance=False)
            self._save(project / "IGRIS_PROGRESS.json",state)
            self._save(project / "CODE_DELIVERY.json",{"strategy":BASELINE_ID,"files":written,
                "models_used":[],"llm_calls":0,"godot_version":self.runtime.version(),
                "import_ok":True,"boot_ok":True,"playable_verified":True,"acceptance_verified":False,
                "pending":["Aprobacion visual y de los combates por el usuario; animaciones procedurales sencillas"]})
            if self.on_progress: self.on_progress(100,"Ajedrez jugable comprobado; listo para abrir")
            return SequentialGameResult(True,"Ajedrez 3D jugable preparado y comprobado; abre JUGAR.cmd. Base incluida con animaciones sencillas.",project,tuple(written))
        except (OSError, ValueError, TypeError) as exc:
            if project.is_dir():
                state.update(state="blocked",error=str(exc),complete=False)
                self._save(project / "IGRIS_PROGRESS.json",state)
            return SequentialGameResult(False,"No se pudo verificar el ajedrez; avance conservado",project,tuple(written),(str(exc),))

    def _verify_game(self, project, source):
        name = "_igris_verify_" + uuid4().hex + ".gd"
        harness = project / name
        harness.write_text(source,encoding="utf-8")
        try:
            return self.runtime.run_script(project,name)
        finally:
            harness.unlink(missing_ok=True)

    @staticmethod
    def _save(path, data):
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
        os.replace(temporary,path)
