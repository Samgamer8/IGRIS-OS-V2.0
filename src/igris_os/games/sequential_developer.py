from __future__ import annotations

import json
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from igris_os.games.runtime import GodotRun, GodotRuntime
from igris_os.games.verified_3d import VerifiedGodot3DFactory
from igris_os.multi_agent.hierarchy import (
    Evidence,
    HierarchicalOrchestrator,
    Specialist,
    WorkOrder,
)
from igris_os.skills import build_engineering_catalog
from igris_os.utils.json_parser import StrictJSONParser

CONTENT_SCHEMA = {
    "type": "object",
    "properties": {"content": {"type": "string"}},
    "required": ["content"],
}


@dataclass(frozen=True, slots=True)
class GodotComponent:
    path: str
    purpose: str
    dependencies: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SequentialGameResult:
    ok: bool
    message: str
    project: Path | None = None
    files: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()


CHESS_COMPONENTS = (
    GodotComponent("chess_state.gd",
                   "Board storage, standard 32-piece setup, lookup, move, capture and turn switching."),
    GodotComponent("pawn_rules.gd",
                   "Pure pawn movement and capture validation using a supplied board."),
    GodotComponent("sliding_rules.gd",
                   "Pure rook, bishop and queen movement with path obstruction checks."),
    GodotComponent("jump_rules.gd",
                   "Pure knight and king movement validation."),
    GodotComponent("chess_rules.gd",
                   "Small facade dispatching legal move validation to pawn, sliding and jump rules.",
                   ("chess_state.gd", "pawn_rules.gd", "sliding_rules.gd",
                    "jump_rules.gd")),
    GodotComponent("pawn_visual.gd",
                   "Original low-poly winged pawn built from native primitives."),
    GodotComponent("rook_visual.gd",
                   "Original massive fortress rook with four battlements."),
    GodotComponent("knight_visual.gd",
                   "Original asymmetric armored knight silhouette."),
    GodotComponent("bishop_visual.gd",
                   "Original narrow mystic bishop with mitre and staff."),
    GodotComponent("queen_visual.gd",
                   "Original tall warrior queen with ring crown and points."),
    GodotComponent("king_visual.gd",
                   "Original tallest ceremonial king with a two-box cross."),
    GodotComponent("piece_factory.gd",
                   "Small facade providing PBR side materials and dispatching six visual builders.",
                   ("pawn_visual.gd", "rook_visual.gd", "knight_visual.gd",
                    "bishop_visual.gd", "queen_visual.gd", "king_visual.gd")),
    GodotComponent("board_view.gd",
                   "8x8 board, 32 piece nodes, picking and highlights.",
                   ("chess_state.gd", "chess_rules.gd", "piece_factory.gd")),
    GodotComponent("camera_controller.gd",
                   "Smooth orbit, clamped zoom and camera reset."),
    GodotComponent("game_controller.gd",
                   "Selection, legal move execution, capture, turns and tween animation.",
                   ("chess_state.gd", "chess_rules.gd", "board_view.gd")),
    GodotComponent("main.gd",
                   "Compose scene, PBR lighting, HUD and screenshot capture hook.",
                   ("game_controller.gd", "camera_controller.gd")),
)

REQUIRED_TOKENS: dict[str, tuple[str, ...]] = {
    "chess_state.gd": (
        "pawn", "rook", "knight", "bishop", "queen", "king",
        "current_turn", "move_piece", "setup_board", "side", "type"),
    "pawn_rules.gd": (
        "pawn", "is_valid_pawn_move", "direction", "start_row"),
    "sliding_rules.gd": (
        "rook", "bishop", "queen", "is_path_clear"),
    "jump_rules.gd": ("knight", "king"),
    "chess_rules.gd": (
        "is_valid_move",
        "res://pawn_rules.gd", "res://sliding_rules.gd",
        "res://jump_rules.gd", "is_valid_pawn_move",
        ".rook(", ".bishop(", ".queen(",
        "is_valid_knight_move", "is_valid_king_move"),
    "pawn_visual.gd": ("func build", "spheremesh.new", "add_child"),
    "rook_visual.gd": ("func build", "boxmesh.new", "add_child"),
    "knight_visual.gd": ("func build", "rotation", "add_child"),
    "bishop_visual.gd": ("func build", "spheremesh.new", "rotation", "add_child"),
    "queen_visual.gd": ("func build", "torusmesh.new", "add_child"),
    "king_visual.gd": ("func build", "boxmesh.new", "add_child"),
    "piece_factory.gd": (
        "pawn", "rook", "knight", "bishop", "queen", "king",
        "standardmaterial3d", "create_piece", "albedo_color",
        "metallic", "roughness",
        "res://pawn_visual.gd", "res://rook_visual.gd",
        "res://knight_visual.gd", "res://bishop_visual.gd",
        "res://queen_visual.gd", "res://king_visual.gd"),
    "board_view.gd": ("board_size", "range(", "ray"),
    "game_controller.gd": ("is_valid_move",),
    "main.gd": ("--igris-capture", "label"),
}

STRUCTURE_RULES: dict[str, str] = {
    "chess_state.gd": (
        "Extend RefCounted. At class scope only declare variables/constants. "
        "Declare board as an empty Array; allocate its eight rows inside func "
        "_init() using nested for loops and append(). Every loop variable must "
        "be a named identifier such as row_index, never a bare underscore. "
        "Call setup_board() at the end of _init(); RefCounted never receives "
        "_ready(). Store every occupied square as a Dictionary with exact keys "
        "'type' and 'side', where side is 'white' or 'black'. White starts on "
        "rows 0 and 1 and moves toward increasing y; black starts on rows 7 and "
        "6 and moves toward decreasing y. get_piece returns the dictionary or "
        "null. move_piece must move the same dictionary to the destination, "
        "clear the origin and switch the turn exactly once; capture is the same "
        "mutation because replacing the destination removes the captured piece. "
        "Use exact public signatures get_piece(x, y) and "
        "move_piece(from_x, from_y, to_x, to_y), indexing board[y][x]. "
        "Do not implement move validation in state. "
        "Never put a for loop or "
        "assignment statement directly in the class body."
    ),
    "chess_rules.gd": (
        "Extend RefCounted. Keep validation functions pure and receive the state "
        "or board as an argument; do not instantiate scene nodes. This is only a "
        "small facade: delegate pawn, sliding and jump rules to dependencies. "
        "Load dependencies explicitly with preload('res://pawn_rules.gd'), "
        "preload('res://sliding_rules.gd') and preload('res://jump_rules.gd'), "
        "then call new(). Never use PawnRules, SlidingRules or JumpRules as "
        "type annotations because global classes may not be registered yet. "
        "Dispatch sliding pieces through rook(), bishop() and queen(). "
        "is_valid_move(board, side, from_x, from_y, to_x, to_y) must reject "
        "coordinates outside 0..7, a zero-length move, an empty origin, a piece "
        "whose side differs from side, and a destination occupied by that side "
        "before dispatching by piece['type']. "
        "Never declare or initialize a second board, turn, PieceType or Team."
    ),
    "pawn_rules.gd": (
        "Extend RefCounted. Implement only pawn movement and capture. Receive the "
        "board and side as arguments; never own or initialize board state. Use "
        "direction = 1 and start_row = 1 for white, -1 and 6 for black. A forward "
        "move requires an empty destination. A two-square first move requires both "
        "the intermediate and destination squares empty. A diagonal move requires "
        "an enemy destination. Never read object properties; pieces are Dictionaries."
        " The class constructor takes no arguments. Use the exact signature "
        "is_valid_pawn_move(board, side, from_x, from_y, to_x, to_y); derive "
        "direction and start_row inside that call. Empty squares are null, never "
        "a Dictionary whose type is 'empty'."
    ),
    "sliding_rules.gd": (
        "Extend RefCounted. Implement only rook, bishop and queen geometry plus "
        "func is_path_clear. Receive board; never own or initialize it. Check only "
        "squares strictly between origin and destination: the destination must not "
        "be included because ChessRules handles friendly/enemy occupancy. Reject a "
        "zero-length rook move. Pieces are Dictionaries or null."
    ),
    "jump_rules.gd": (
        "Extend RefCounted. Implement only knight and king movement geometry. "
        "Receive board; never own or initialize it. King must move exactly one "
        "square in at least one axis, so a zero-length move is invalid."
    ),
    "piece_factory.gd": (
        "Extend RefCounted. This is only an assembly facade. Explicitly preload the "
        "six res://*_visual.gd dependencies, instantiate them with new(), configure "
        "one light and one dark StandardMaterial3D in _init, and expose create_piece"
        "(piece_type, side) which selects a material and calls the matching builder's "
        "build(material). Do not create geometry here and do not load any non-script "
        "asset. Light is silver/ivory/blue; dark is aged gold/bronze/deep red."
    ),
}

for _visual_path, _visual_identity in {
        "pawn_visual.gd": "winged guardian: disc base, torso, sphere head and two wings",
        "rook_visual.gd": "fortress sentinel: broad base, trunk, crown and four battlements",
        "knight_visual.gd": "armored beast: base, tilted neck, offset rotated head and ears",
        "bishop_visual.gd": "hooded mystic: base, narrow robe, sphere mitre and diagonal detail",
        "queen_visual.gd": "warrior sovereign: base, tall body, TorusMesh crown and crown points",
        "king_visual.gd": "ceremonial ruler: broad base, tall body, shoulders and two-box cross",
}.items():
    STRUCTURE_RULES[_visual_path] = (
        "Extend RefCounted. Expose func build(material: Material) -> Node3D. "
        "Create an original " + _visual_identity + ". Compose several native "
        "PrimitiveMesh children through MeshInstance3D, scaled and positioned to "
        "fit one square. Use the supplied material. No assets, CSG, physics, input, "
        "animation loop, preload or load. Return the root Node3D. Godot 4 "
        "CylinderMesh uses top_radius and bottom_radius float properties; the "
        "property radii does not exist and is forbidden."
    )

COMPONENT_BLUEPRINTS: dict[str, str] = {
    "queen_visual.gd": (
        "Build a plain Node3D root with at least six direct MeshInstance3D "
        "children: disc base, tapered torso, shoulders, head, TorusMesh crown "
        "ring, and at least two separately named crown points. Create every "
        "PrimitiveMesh and MeshInstance3D with a unique variable name. Attach "
        "each part using root.add_child(part). Do not use ArrayMesh, arrays, "
        "loops, SurfaceTool, or add_child on a Resource. Do not overwrite a "
        "MeshInstance3D.mesh after assigning it. Use material_override."
    ),
    "king_visual.gd": (
        "Build a plain Node3D root with at least six direct MeshInstance3D "
        "children: broad disc base, tapered body, two shoulders, head, and a "
        "cross made from two separate BoxMesh parts. Use unique variable names, "
        "root.add_child(part), and material_override. Do not use ArrayMesh, "
        "arrays, loops, SurfaceTool, or add_child on a Resource."
    ),
    "piece_factory.gd": (
        "Keep this facade short: six preload constants, six builder instances, two "
        "PBR materials, and one match in create_piece that calls build(material). "
        "ART DIRECTION: create an original late-1990s dark-fantasy low-poly set, "
        "not a copy of any existing game. Read each abstract construction as a "
        "character silhouette: pawn is a small winged guardian; rook is a massive "
        "fortress sentinel; knight is an asymmetric armored beast; bishop is a "
        "narrow hooded mystic with diagonal staff/mitre; queen is a tall aggressive "
        "warrior sovereign; king is the tallest broad-shouldered ceremonial ruler. "
        "Light army uses silver/ivory/blue accents; dark army uses aged gold/bronze/"
        "deep red accents. Preserve chess readability from the elevated camera. "
        "All dimensions must fit approximately inside one board square and all "
        "parts must be children of the returned root. Do not compress functions "
        "onto one line."
    ),
}


class SequentialGodotGameDeveloper:
    """Generates and repairs a Godot game one component at a time."""

    def __init__(self, client, workspace: Path, model: str,
                 runtime: GodotRuntime | None = None) -> None:
        self.client = client
        self.workspace = Path(workspace).resolve()
        self.model = model
        self._active_model = model
        self._models_used: list[str] = []
        self.skill_catalog = build_engineering_catalog()
        self.runtime = runtime or GodotRuntime(timeout=180)

    def develop_chess_3d(self, objective: str, name: str, *,
                         confirmed: bool = False,
                         repair_rounds: int = 2,
                         resume: bool = False) -> SequentialGameResult:
        if not confirmed:
            return SequentialGameResult(False, "Se necesita confirmacion")
        target = self._project_path(name)
        project = target if resume and target.is_dir() else self._fresh_project(name)
        if resume and target.is_dir():
            resume_marker = target / "_igris_resume_manifest.json"
            try:
                manifest = json.loads(resume_marker.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                manifest = {}
            if str(target) not in {
                    entry.get("project") for entry in manifest.get("resumed", [])}:
                manifest.setdefault("resumed", []).append({
                    "project": str(target),
                    "resumed_at": "2026-08-31",
                    "resume": True,
                })
                resume_marker.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        files: list[str] = []
        interfaces: dict[str, str] = {}
        diagnostics: list[str] = []
        try:
            for component in CHESS_COMPONENTS:
                existing = project / component.path
                component_diagnostic = ""
                if resume and existing.is_file():
                    current = ""
                    try:
                        current = existing.read_text(encoding="utf-8")
                        self._validate(component.path, current)
                        checked = self.runtime.check_script(
                            project, component.path)
                        if checked.ok:
                            if component.path.endswith("_visual.gd"):
                                smoke = self._smoke_visual(
                                    project, component.path)
                                if not smoke.ok:
                                    component_diagnostic = (
                                        smoke.output +
                                        "\nCURRENT FILE TO REPAIR:\n" +
                                        current[-14000:])
                                    raise ValueError(component_diagnostic)
                            elif component.path in {
                                    "chess_state.gd", "pawn_rules.gd",
                                    "sliding_rules.gd", "jump_rules.gd",
                                    "chess_rules.gd"}:
                                smoke = self._smoke_logic(
                                    project, component.path)
                                if not smoke.ok:
                                    component_diagnostic = (
                                        smoke.output +
                                        "\nCURRENT FILE TO REPAIR:\n" +
                                        current[-14000:])
                                    raise ValueError(component_diagnostic)
                            files.append(component.path)
                            interfaces[component.path] = self._interfaces(current)
                            continue
                        component_diagnostic = (
                            checked.output + "\nCURRENT FILE TO REPAIR:\n" +
                            current[-14000:])
                    except (OSError, ValueError) as exc:
                        error = str(exc)
                        obsolete = any(marker in error for marker in (
                            "invade ChessState",
                            "class_name duplicado",
                            "operador ternario tipo C"))
                        if (component.path == "piece_factory.gd"
                                or component.path.endswith("_visual.gd")):
                            # A rejected visual factory is cheap to regenerate and
                            # old silhouettes strongly anchor model repairs.
                            obsolete = True
                        if component.path in {
                                "chess_state.gd", "pawn_rules.gd",
                                "sliding_rules.gd", "jump_rules.gd",
                                "chess_rules.gd"}:
                            obsolete = True
                        if obsolete:
                            existing.unlink(missing_ok=True)
                            clean_error = error.split(
                                "\nCURRENT FILE TO REPAIR:", 1)[0]
                            component_diagnostic = (
                                clean_error +
                                "\nOBSOLETE ARCHITECTURE: discard the current "
                                "file completely. Generate a small fresh "
                                "replacement from the current responsibility "
                                "and dependencies. Do not preserve its design.")
                        else:
                            component_diagnostic = (
                                error + "\nCURRENT FILE TO REPAIR:\n" +
                                current[-14000:])
                content = self._generate_with_tournament(
                    objective, component, interfaces,
                    component_diagnostic, project)
                files.append(component.path)
                interfaces[component.path] = self._interfaces(content)
        except (OSError, TypeError, ValueError) as exc:
            return SequentialGameResult(
                False, "Fallo generando componentes", project,
                tuple(files), (str(exc),))

        check = self._check(project)
        for _ in range(max(0, repair_rounds)):
            if check.ok:
                break
            diagnostic = check.output[-6000:]
            diagnostics.append(diagnostic)
            targets = self._targets(diagnostic, files)
            try:
                for path in targets:
                    component = next(c for c in CHESS_COMPONENTS
                                     if c.path == path)
                    current = (project / path).read_text(encoding="utf-8")
                    repaired = self._generate_with_tournament(
                        objective, component, interfaces,
                        diagnostic + "\nCURRENT FILE:\n" + current[-10000:],
                        project)
                    interfaces[path] = self._interfaces(repaired)
            except (OSError, TypeError, ValueError) as exc:
                diagnostics.append(str(exc))
                break
            check = self._check(project)
        if not check.ok:
            diagnostics.append(check.output[-6000:])
            return SequentialGameResult(
                False, "Godot no pudo verificar el juego", project,
                tuple(files), tuple(diagnostics))

        (project / "CODE_DELIVERY.json").write_text(json.dumps({
            "strategy": "sequential_godot_components",
            "model": self.model,
            "models_used": self._models_used,
            "skills_used": self.skill_catalog.loaded_names,
            "files": files,
            "godot_version": self.runtime.version(),
            "import_ok": True,
            "boot_ok": True,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        return SequentialGameResult(
            True, "Juego generado y verificado por componentes",
            project, tuple(files), tuple(diagnostics))

    def _fresh_project(self, name: str) -> Path:
        target = self._project_path(name)
        self.workspace.mkdir(parents=True, exist_ok=True)
        if target.exists():
            shutil.rmtree(target)
        return VerifiedGodot3DFactory(self.workspace).create(
            target.name, confirmed=True)

    def _project_path(self, name: str) -> Path:
        safe = "".join(c for c in name if c.isalnum() or c in " _-").strip()
        if not safe:
            raise ValueError("Nombre invalido")
        target = (self.workspace / safe.replace(" ", "_")).resolve()
        if not target.is_relative_to(self.workspace):
            raise ValueError("Proyecto fuera del workspace")
        return target

    def _generate(self, objective: str, component: GodotComponent,
                  interfaces: dict[str, str], diagnostic: str,
                  model: str | None = None) -> str:
        selected_model = model or self._active_model
        skill_name = "evidence-debug" if diagnostic else "component-build"
        skill = self.skill_catalog.load(skill_name)
        known = "\n".join(
            f"{path}: {summary}" for path, summary in interfaces.items())
        prompt = (
            "You are IGRIS, an autonomous senior Godot 4 programmer. Return ONLY "
            "JSON with key content containing the complete requested GDScript. "
            "No markdown or prose. Use typed Godot 4 GDScript and class_name for "
            "reusable components. Use Node3D, Camera3D, MeshInstance3D, "
            "StandardMaterial3D and create_tween(); never use Godot 3 APIs such as "
            "Spatial, Camera, MeshInstance, SpatialMaterial or Tween.new(). "
            "GDScript is not Python: NEVER use list/dictionary comprehensions, "
            "array multiplication, Python-style conditional expressions or tuple "
            "unpacking. Build nested arrays with explicit loops and append(). "
            "Every function must have valid indentation and every bracket must "
            "close. Prefer simple parse-safe code over clever compact syntax. "
            "No assets, addons, network, TODO, examples or placeholders.\n"
            f"OBJECTIVE: {objective}\nFILE: {component.path}\n"
            f"RESPONSIBILITY: {component.purpose}\n"
            f"DEPENDENCIES: {', '.join(component.dependencies) or 'none'}\n"
            f"FILE STRUCTURE RULE: {STRUCTURE_RULES.get(component.path, 'Use a simple valid Godot 4 class structure.')}\n"
            "MANDATORY CONTRACT TOKENS OR APIS: " +
            ", ".join(REQUIRED_TOKENS.get(component.path, ())) + "\n"
            "MANDATORY WORKFLOW: " + skill.compact_instructions() + "\n")
        blueprint = COMPONENT_BLUEPRINTS.get(component.path, "")
        if blueprint:
            prompt += "MANDATORY COMPONENT BLUEPRINT: " + blueprint + "\n"
        if known:
            prompt += "KNOWN INTERFACES:\n" + known[-8000:] + "\n"
        if diagnostic:
            prompt += ("GODOT ERROR TO REPAIR:\n" + diagnostic[-12000:] +
                       "\nReturn the complete corrected file.\n")
        generate_json = getattr(self.client, "generate_json", None)
        reply = (generate_json(prompt, selected_model, CONTENT_SCHEMA)
                 if callable(generate_json)
                 else self.client.generate(prompt, selected_model))
        content = ""
        if reply.ok:
            try:
                package = StrictJSONParser.extract(reply.text)
                content = str(package.get("content", "")).strip()
            except (TypeError, ValueError):
                pass
        else:
            # A transport/model failure cannot be repaired by asking the same
            # unavailable model for a different output wrapper. Escalate now.
            raise ValueError(reply.error or "Modelo sin respuesta")
        if not content:
            strict_generate = getattr(
                self.client, "generate_strict", None)
            if not callable(strict_generate):
                strict_generate = self.client.generate
            fallback = strict_generate(
                prompt + "\nThe structured response failed. Return the complete "
                "raw script between literal lines BEGIN_GDSCRIPT and "
                "END_GDSCRIPT. Do not JSON-escape it.", selected_model)
            if not fallback.ok:
                errors = "; ".join(
                    item for item in (reply.error, fallback.error) if item)
                raise ValueError(errors or "Modelo sin respuesta")
            content = self._extract_raw_script(fallback.text)
        if not content:
            raise ValueError("Componente vacio: " + component.path)
        return content + "\n"

    @staticmethod
    def _extract_raw_script(text: str) -> str:
        marked = re.search(
            r"BEGIN_GDSCRIPT\s*(.*?)\s*END_GDSCRIPT",
            text, re.DOTALL | re.IGNORECASE)
        if marked:
            return marked.group(1).strip()
        fenced = re.search(
            r"```(?:gdscript)?\s*(.*?)\s*```",
            text, re.DOTALL | re.IGNORECASE)
        if fenced:
            return fenced.group(1).strip()
        stripped = text.strip()
        starts = [
            index for marker in ("extends ", "class_name ")
            if (index := stripped.find(marker)) >= 0
        ]
        return stripped[min(starts):] if starts else ""

    def _generate_valid(self, objective: str, component: GodotComponent,
                        interfaces: dict[str, str],
                        diagnostic: str, *, model: str | None = None,
                        attempts: int = 3) -> str:
        feedback = diagnostic
        last_error = ""
        for attempt in range(1, max(1, attempts) + 1):
            try:
                content = self._generate(
                    objective, component, interfaces, feedback, model)
                self._validate(component.path, content)
                return content
            except (TypeError, ValueError) as exc:
                last_error = str(exc)
                feedback = (
                    diagnostic +
                    f"\nREPAIR ATTEMPT {attempt} FAILED. "
                    "Do not repeat the same implementation.\n"
                    "IGRIS VALIDATION ERROR: " + last_error
                ).strip()
        raise ValueError(last_error or "Componente no valido")

    def _generate_compilable(
            self, objective: str, component: GodotComponent,
            interfaces: dict[str, str], diagnostic: str,
            project: Path) -> str:
        feedback = diagnostic
        last_error = ""
        for attempt in range(1, 4):
            content = self._generate_valid(
                objective, component, interfaces, feedback,
                model=self._active_model)
            content = self._mechanical_repairs(content)
            (project / component.path).write_text(
                content, encoding="utf-8")
            checked = self.runtime.check_script(
                project, component.path)
            if checked.ok:
                return content
            last_error = checked.output[-6000:]
            feedback = (
                diagnostic +
                f"\nGODOT COMPILE ATTEMPT {attempt} FAILED:\n" +
                last_error +
                "\nCURRENT REJECTED FILE (repair this exact file):\n" +
                content[-14000:] +
                "\nReturn a complete replacement, preserving valid behavior.")
        raise ValueError(
            component.path + " no compila: " + last_error[-2000:])

    def _generate_with_tournament(
            self, objective: str, component: GodotComponent,
            interfaces: dict[str, str], diagnostic: str,
        project: Path) -> str:
        models = self._model_candidates()
        accumulated = diagnostic
        batches = [
            models[offset:offset + 2]
            for offset in range(0, len(models), 2)]
        if len(models) >= 2:
            # One bounded immediate trip back to the head of the micro-queue.
            # Repair with the fast pair before paying for larger specialists.
            batches.insert(1, models[:2])
        for round_index, batch in enumerate(batches, start=1):
            if len(batch) == 1:
                self._active_model = batch[0]
                return self._generate_compilable(
                    objective, component, interfaces, accumulated, project)

            specialists = tuple(
                Specialist(
                    model,
                    "godot_programmer",
                    lambda order, selected=model: self._generate(
                        objective, component, interfaces,
                        order.context, selected),
                )
                for model in batch)

            def evaluate(order: WorkOrder, proposal) -> Evidence:
                del order
                try:
                    content = self._mechanical_repairs(proposal.content)
                    self._validate(component.path, content)
                    with tempfile.TemporaryDirectory(
                            prefix="igris-candidate-",
                            dir=project.parent) as temporary:
                        candidate_project = Path(temporary) / "project"
                        shutil.copytree(
                            project, candidate_project,
                            ignore=shutil.ignore_patterns(".godot"))
                        (candidate_project / component.path).write_text(
                            content, encoding="utf-8")
                        checked = self.runtime.check_script(
                            candidate_project, component.path)
                        if checked.ok and component.path.endswith("_visual.gd"):
                            checked = self._smoke_visual(
                                candidate_project, component.path)
                        elif checked.ok and component.path in {
                                "chess_state.gd", "pawn_rules.gd",
                                "sliding_rules.gd", "jump_rules.gd",
                                "chess_rules.gd"}:
                            checked = self._smoke_logic(
                                candidate_project, component.path)
                    if not checked.ok:
                        return Evidence(
                            False, 0.0, ("semantic_contract",),
                            (checked.output[-3000:],))
                    return Evidence(
                        True, 1.0,
                        ("semantic_contract", "godot_compile"))
                except (OSError, TypeError, ValueError) as exc:
                    return Evidence(False, 0.0, diagnostics=(str(exc),))

            order = WorkOrder(
                objective=objective,
                acceptance_criteria=(
                    "semantic_contract", "godot_compile"),
                constraints=(component.purpose,),
                context=accumulated + "\nCOMPETITIVE CANDIDATE ROUND")
            decision = HierarchicalOrchestrator(
                specialists, evaluate, parallelism=2).execute(order)
            if decision.approved and decision.winner is not None:
                winner = decision.winner
                content = self._mechanical_repairs(
                    winner.proposal.content)
                (project / component.path).write_text(
                    content, encoding="utf-8")
                model = winner.proposal.specialist
                if model not in self._models_used:
                    self._models_used.append(model)
                return content
            failures = []
            for candidate in decision.candidates:
                details = "; ".join(candidate.evidence.diagnostics)
                failures.append(
                    candidate.proposal.specialist + ": " +
                    (details or candidate.proposal.error or "rechazado"))
            repairable = [
                item for item in decision.candidates
                if item.proposal.ok and item.proposal.content.strip()]
            best_rejected = min(
                repairable,
                key=lambda item: (
                    len("; ".join(item.evidence.diagnostics)),
                    -len(item.proposal.content)),
                default=None)
            rejected_context = ""
            if best_rejected is not None:
                rejected_context = (
                    "\nBEST REJECTED CANDIDATE TO REPAIR:\n" +
                    best_rejected.proposal.content[-12000:])
            accumulated = (
                accumulated[-6000:] +
                "\nPREVIOUS SPECIALIST PAIR FAILED:\n" +
                "\n".join(failures)[-6000:] +
                rejected_context +
                f"\nMICRO-QUEUE ROUND: {round_index}")
        raise ValueError(
            component.path + " agoto torneos de especialistas:\n" +
            accumulated[-6000:])

    def _generate_with_escalation(
            self, objective: str, component: GodotComponent,
            interfaces: dict[str, str], diagnostic: str,
            project: Path) -> str:
        failures: list[str] = []
        for model in self._model_candidates():
            self._active_model = model
            try:
                content = self._generate_compilable(
                    objective, component, interfaces,
                    diagnostic + "\nMODEL ESCALATION: " + model, project)
                if model not in self._models_used:
                    self._models_used.append(model)
                return content
            except (TypeError, ValueError) as exc:
                failures.append(model + ": " + str(exc))
        raise ValueError(
            component.path + " agoto modelos disponibles:\n" +
            "\n".join(failures)[-6000:])

    def _model_candidates(self) -> tuple[str, ...]:
        preferred = (
            self.model,
            "stable-code:3b-code-q4_0",
            "qwen2.5-coder:7b",
            "qwen2.5-coder:14b",
            "deepseek-coder-v2:16b",
            "devstral:24b",
            "gemma4:26b",
        )
        try:
            installed = set(self.client.models())
        except (AttributeError, TypeError, OSError):
            installed = {self.model}
        selected: list[str] = []
        for model in preferred:
            if (model in installed and "embed" not in model.casefold()
                    and model not in selected):
                selected.append(model)
        return tuple(selected) or (self.model,)

    @staticmethod
    def _mechanical_repairs(content: str) -> str:
        """Fix unambiguous model syntax slips without inventing behavior."""
        counter = 0

        def name_discarded_loop(match: re.Match[str]) -> str:
            nonlocal counter
            counter += 1
            return match.group(1) + f"unused_index_{counter}" + match.group(2)

        repaired = re.sub(
            r"(?m)^(\s*for\s+)_((?:\s+in\s+))",
            name_discarded_loop,
            content,
        )
        repaired = re.sub(
            r"(?m)^(\s*\w+)\.material\s*=\s*(material\s*)$",
            r"\1.material_override = \2",
            repaired,
        )
        repaired = re.sub(r"\btranslation\s*=", "position =", repaired)
        plane_names = re.findall(
            r"(?m)^\s*var\s+(\w+)\s*=\s*PlaneMesh\.new\(\)",
            repaired,
        )
        for plane_name in plane_names:
            repaired = re.sub(
                rf"\b{re.escape(plane_name)}\.size\s*=\s*"
                r"Vector3\(\s*([^,]+),\s*([^,]+),\s*[^)]+\)",
                rf"{plane_name}.size = Vector2(\1, \2)",
                repaired,
            )
        torus_targets = re.findall(
            r"(?m)^\s*(?:var\s+)?(\w+(?:\.mesh)?)\s*=\s*TorusMesh\.new\(\)",
            repaired,
        )
        for torus_target in torus_targets:
            escaped = re.escape(torus_target)
            for obsolete, current in (
                    ("major_radius", "outer_radius"),
                    ("radius", "outer_radius"),
                    ("minor_radius", "inner_radius"),
                    ("ring_radius", "inner_radius")):
                repaired = re.sub(
                    rf"\b{escaped}\.{obsolete}\s*=",
                    f"{torus_target}.{current} =",
                    repaired,
                )
        return repaired

    @staticmethod
    def _validate(path: str, content: str) -> None:
        if len(content.encode("utf-8")) > 256_000:
            raise ValueError("Componente demasiado grande: " + path)
        if not content.lstrip().startswith(("extends ", "class_name ")):
            raise ValueError("GDScript sin declaracion inicial: " + path)
        lowered = content.casefold()
        forbidden = [marker for marker in (
            "todo", "placeholder", "extends spatial",
            "spatialmaterial", "meshinstance.new", "extends camera",
            "tween.new()", "interpolate_property")
            if marker in lowered]
        if forbidden:
            raise ValueError(
                path + " usa APIs o marcadores prohibidos: " +
                ", ".join(forbidden))
        structural: list[str] = []
        if content.casefold().count("class_name ") > 1:
            structural.append("class_name duplicado")
        if "?" in content:
            structural.append(
                "operador ternario tipo C; use value_if_true if condition else value_if_false")
        if path in {
                "chess_rules.gd", "pawn_rules.gd",
                "sliding_rules.gd", "jump_rules.gd"}:
            for marker in ("func initialize_board", "var board", "func _ready"):
                if marker in lowered:
                    structural.append(
                        path + " invade ChessState con " + marker)
        if path == "chess_state.gd":
            if "func _ready" in lowered:
                structural.append(
                    "chess_state es RefCounted y no puede depender de _ready")
            init_match = re.search(
                r"func\s+_init\s*\([^)]*\)\s*:(.*?)(?=\nfunc\s|\Z)",
                content, re.DOTALL)
            if not init_match or "setup_board(" not in init_match.group(1):
                structural.append(
                    "chess_state debe llamar setup_board desde _init")
            if re.search(r"board\s*\[[^\n]+\]\s*=\s*['\"](?:pawn|rook|knight|bishop|queen|king)['\"]", content):
                structural.append(
                    "chess_state debe guardar diccionarios con type y side")
        if path == "chess_rules.gd" and re.search(
                r":\s*(PawnRules|SlidingRules|JumpRules)\b", content):
            structural.append(
                "chess_rules usa tipos globales no garantizados; use preload y new")
        if path == "piece_factory.gd":
            resource_paths = re.findall(
                r"\b(?:preload|load)\s*\(\s*[\"']([^\"']+)[\"']",
                content)
            if any(not item.endswith("_visual.gd")
                   for item in resource_paths):
                structural.append(
                    "piece_factory solo puede cargar sus seis scripts visuales")
            if re.search(r"\bCSG(?:Combiner|Box|Sphere|Cylinder|Mesh|Shape)3D\b",
                         content):
                structural.append(
                    "piece_factory no debe usar CSG en piezas de ejecucion")
            if re.search(r"\b(?:FastNoiseLite|NoiseTexture2D|StaticBody3D)\b",
                         content):
                structural.append(
                    "piece_factory usa textura o cuerpo pesado para piezas moviles")
            if re.search(r"func\s+_(?:process|physics_process)\s*\(", content):
                structural.append(
                    "piece_factory no debe regenerar geometria por fotograma")
            if re.search(r"(?m)^\s*var\s+\w+\s*:\s*MeshInstance3D\b", content):
                structural.append(
                    "piece_factory no debe cachear nodos MeshInstance3D")
        if path.endswith("_visual.gd"):
            if re.search(r"\b(?:preload|load)\s*\(", content):
                structural.append(path + " no puede cargar recursos externos")
            if re.search(r"\b(?:CSG\w*3D|StaticBody3D|NoiseTexture2D)\b", content):
                structural.append(path + " usa nodos pesados prohibidos")
            if re.search(r"func\s+_(?:process|physics_process)\s*\(", content):
                structural.append(path + " regenera geometria por fotograma")
            if re.search(r"\.radii\s*=", content):
                structural.append(
                    path + " usa CylinderMesh.radii inexistente; use top_radius y bottom_radius")
            if re.search(r"\b(?:ArrayMesh|SurfaceTool)\.new\s*\(", content):
                structural.append(
                    path + " debe usar solo PrimitiveMesh en nodos MeshInstance3D")
            declared_names = re.findall(
                r"(?m)^\s*var\s+(\w+)\b", content)
            duplicate_names = sorted({
                name for name in declared_names
                if declared_names.count(name) > 1})
            if duplicate_names:
                structural.append(
                    path + " repite variables: " + ", ".join(duplicate_names))
            minimum_parts = {
                "pawn_visual.gd": 4,
                "rook_visual.gd": 6,
                "knight_visual.gd": 4,
                "bishop_visual.gd": 4,
                "queen_visual.gd": 6,
                "king_visual.gd": 5,
            }[path]
            if content.count("add_child(") < minimum_parts:
                structural.append(
                    path + f" necesita al menos {minimum_parts} partes")
        if structural:
            raise ValueError(path + " estructura invalida: " + "; ".join(structural))
        missing = [item for item in REQUIRED_TOKENS.get(path, ())
                   if item not in lowered]
        if missing:
            raise ValueError(
                path + " no cumple: " + ", ".join(missing))
        if path == "game_controller.gd" and not any(
                marker in lowered for marker in (
                    "create_tween", "tween_property", "lerp(",
                    "move_toward", "animationplayer")):
            raise ValueError(
                path + " no implementa animacion de movimiento")

    @staticmethod
    def _interfaces(content: str) -> str:
        lines = [line.strip()[:240] for line in content.splitlines()
                 if line.strip().startswith(
                     ("class_name ", "signal ", "func ", "var ", "const "))]
        return " | ".join(lines[:30])

    def _check(self, project: Path) -> GodotRun:
        for component in CHESS_COMPONENTS:
            checked = self.runtime.check_script(project, component.path)
            if not checked.ok:
                return checked
        imported = self.runtime.import_project(project)
        if not imported.ok:
            return imported
        return self.runtime.run(project, frames=30, headless=True)

    def _smoke_visual(self, project: Path, path: str) -> GodotRun:
        minimum = {
            "pawn_visual.gd": 4,
            "rook_visual.gd": 6,
            "knight_visual.gd": 4,
            "bishop_visual.gd": 4,
            "queen_visual.gd": 6,
            "king_visual.gd": 5,
        }[path]
        harness_name = "_igris_visual_smoke.gd"
        harness = project / harness_name
        harness.write_text(
            "extends SceneTree\n"
            "func _init():\n"
            f"    var builder = load('res://{path}').new()\n"
            "    var material = StandardMaterial3D.new()\n"
            "    var root = builder.build(material)\n"
            "    if root == null:\n"
            "        push_error('visual builder returned null')\n"
            "        quit(1)\n"
            "        return\n"
            "    var count = _mesh_count(root)\n"
            f"    if count < {minimum}:\n"
            "        push_error('visual builder has too few runtime meshes')\n"
            "        root.free()\n"
            "        quit(1)\n"
            "        return\n"
            "    root.free()\n"
            "    print('IGRIS_VISUAL_SMOKE_OK:', count)\n"
            "    quit(0)\n"
            "func _mesh_count(node: Node) -> int:\n"
            "    var count := 1 if node is MeshInstance3D else 0\n"
            "    for child in node.get_children():\n"
            "        count += _mesh_count(child)\n"
            "    return count\n",
            encoding="utf-8")
        try:
            runner = getattr(self.runtime, "run_script", None)
            if not callable(runner):
                return GodotRun(True, 0, "runtime smoke unsupported by test double")
            return runner(project, harness_name)
        finally:
            harness.unlink(missing_ok=True)

    def _smoke_rules(self, project: Path) -> GodotRun:
        harness_name = "_igris_rules_smoke.gd"
        harness = project / harness_name
        harness.write_text(
            "extends SceneTree\n"
            "func _require(value: bool, label: String) -> bool:\n"
            "    if not value:\n"
            "        push_error('IGRIS_RULE_FAILED:' + label)\n"
            "        return false\n"
            "    return true\n"
            "func _init() -> void:\n"
            "    var state = load('res://chess_state.gd').new()\n"
            "    var rules = load('res://chess_rules.gd').new()\n"
            "    if not _require(state.board.size() == 8, 'board_rows'): quit(1); return\n"
            "    var white_pawn = state.board[1][4]\n"
            "    if not _require(white_pawn is Dictionary, 'piece_dictionary'): quit(1); return\n"
            "    if not _require(white_pawn.get('type') == 'pawn' and white_pawn.get('side') == 'white', 'piece_identity'): quit(1); return\n"
            "    if not _require(rules.is_valid_move(state.board, 'white', 4, 1, 4, 3), 'pawn_double'): quit(1); return\n"
            "    if not _require(not rules.is_valid_move(state.board, 'white', 4, 1, 4, 4), 'pawn_too_far'): quit(1); return\n"
            "    state.board[2][4] = {'type': 'knight', 'side': 'black'}\n"
            "    if not _require(not rules.is_valid_move(state.board, 'white', 4, 1, 4, 3), 'pawn_blocked'): quit(1); return\n"
            "    state.board[2][4] = null\n"
            "    state.board[2][5] = {'type': 'pawn', 'side': 'black'}\n"
            "    if not _require(rules.is_valid_move(state.board, 'white', 4, 1, 5, 2), 'pawn_capture_enemy'): quit(1); return\n"
            "    state.board[2][5] = {'type': 'pawn', 'side': 'white'}\n"
            "    if not _require(not rules.is_valid_move(state.board, 'white', 4, 1, 5, 2), 'reject_friendly_target'): quit(1); return\n"
            "    state.board[2][5] = null\n"
            "    if not _require(rules.is_valid_move(state.board, 'white', 1, 0, 2, 2), 'knight_jump'): quit(1); return\n"
            "    if not _require(not rules.is_valid_move(state.board, 'white', 0, 0, 0, 3), 'rook_blocked'): quit(1); return\n"
            "    state.board[1][0] = null\n"
            "    if not _require(rules.is_valid_move(state.board, 'white', 0, 0, 0, 3), 'rook_clear'): quit(1); return\n"
            "    if not _require(not rules.is_valid_move(state.board, 'white', 4, 0, 4, 0), 'king_zero'): quit(1); return\n"
            "    state.move_piece(4, 1, 4, 3)\n"
            "    if not _require(state.board[1][4] == null and state.board[3][4].get('type') == 'pawn', 'state_move'): quit(1); return\n"
            "    if not _require(state.current_turn == 'black', 'turn_switch'): quit(1); return\n"
            "    print('IGRIS_RULE_SMOKE_OK')\n"
            "    quit(0)\n",
            encoding="utf-8")
        try:
            return self.runtime.run_script(project, harness_name)
        finally:
            harness.unlink(missing_ok=True)

    def _smoke_logic(self, project: Path, path: str) -> GodotRun:
        if path == "chess_rules.gd":
            return self._smoke_rules(project)
        harness_name = f"_igris_{path.replace('.', '_')}_logic_smoke.gd"
        harness = project / harness_name
        harness.write_text(
            self._logic_smoke_for(path),
            encoding="utf-8")
        try:
            runner = getattr(self.runtime, "run_script", None)
            if not callable(runner):
                return GodotRun(True, 0, "runtime smoke unsupported by test double")
            result = runner(project, harness_name)
            if result.ok and "IGRIS_LOGIC_SMOKE_OK" not in (result.output or ""):
                result = GodotRun(False, result.returncode,
                                  result.output +
                                  "\nIGRIS_LOGIC_SMOKE_OK no se imprimio en salida estandar")
            return result
        finally:
            harness.unlink(missing_ok=True)

    @staticmethod
    def _logic_smoke_for(path: str) -> str:
        if path == "chess_state.gd":
            return (
                "extends SceneTree\n"
                "func _require(value: bool, label: String) -> bool:\n"
                "    if not value:\n"
                "        push_error('IGRIS_RULE_FAILED:' + label)\n"
                "        return false\n"
                "    return true\n"
                "func _init() -> void:\n"
                "    var state = load('res://chess_state.gd').new()\n"
                "    if not _require(state.board.size() == 8, 'board_rows'): quit(1); return\n"
                "    var white_pawn = state.board[1][4]\n"
                "    if white_pawn == null:\n"
                "        push_error('IGRIS_RULE_FAILED:piece_identity_null')\n"
                "        quit(1)\n"
                "        return\n"
                "    if not _require(white_pawn.get('type') == 'pawn' and white_pawn.get('side') == 'white', 'piece_identity'): quit(1); return\n"
                "    var black_king = state.board[7][4]\n"
                "    if black_king == null:\n"
                "        push_error('IGRIS_RULE_FAILED:black_king_null')\n"
                "        quit(1)\n"
                "        return\n"
                "    if not _require(black_king.get('type') == 'king' and black_king.get('side') == 'black', 'black_king'): quit(1); return\n"
                "    var current_turn = state.current_turn\n"
                "    if not _require(current_turn == 'white', 'current_turn'): quit(1); return\n"
                "    var piece = state.get_piece(4, 1)\n"
                "    if piece == null:\n"
                "        push_error('IGRIS_RULE_FAILED:get_piece_null')\n"
                "        quit(1)\n"
                "        return\n"
                "    if not _require(piece.get('type') == 'pawn', 'get_piece'): quit(1); return\n"
                "    state.move_piece(4, 1, 4, 3)\n"
                "    if not _require(state.board[1][4] == null, 'move_piece_clear'): quit(1); return\n"
                "    if not _require(state.board[3][4] is Dictionary, 'move_piece_set'): quit(1); return\n"
                "    if not _require(state.current_turn == 'black', 'turn_switch'): quit(1); return\n"
                "    print('IGRIS_LOGIC_SMOKE_OK')\n"
                "    quit(0)\n"
            )
        if path == "pawn_rules.gd":
            return (
                "extends SceneTree\n"
                "func _require(value: bool, label: String) -> bool:\n"
                "    if not value:\n"
                "        push_error('IGRIS_RULE_FAILED:' + label)\n"
                "        return false\n"
                "    return true\n"
                "func _init() -> void:\n"
                "    var state = load('res://chess_state.gd').new()\n"
                "    var pawn = load('res://pawn_rules.gd').new()\n"
                "    var board = state.board\n"
                "    if not _require(pawn.is_valid_pawn_move(board, 'white', 4, 1, 4, 3), 'pawn_double'): quit(1); return\n"
                "    if not _require(not pawn.is_valid_pawn_move(board, 'white', 4, 1, 4, 4), 'pawn_too_far'): quit(1); return\n"
                "    board[2][4] = {'type': 'knight', 'side': 'black'}\n"
                "    if not _require(not pawn.is_valid_pawn_move(board, 'white', 4, 1, 4, 3), 'pawn_blocked'): quit(1); return\n"
                "    board[2][4] = null\n"
                "    board[2][5] = {'type': 'pawn', 'side': 'black'}\n"
                "    if not _require(pawn.is_valid_pawn_move(board, 'white', 4, 1, 5, 2), 'pawn_capture'): quit(1); return\n"
                "    board[2][5] = {'type': 'pawn', 'side': 'white'}\n"
                "    if not _require(not pawn.is_valid_pawn_move(board, 'white', 4, 1, 5, 2), 'pawn_capture_friendly'): quit(1); return\n"
                "    board[2][5] = null\n"
                "    if not _require(not pawn.is_valid_pawn_move(board, 'white', 4, 1, 4, 1), 'pawn_zero'): quit(1); return\n"
                "    print('IGRIS_LOGIC_SMOKE_OK')\n"
                "    quit(0)\n"
            )
        if path == "sliding_rules.gd":
            return (
                "extends SceneTree\n"
                "func _require(value: bool, label: String) -> bool:\n"
                "    if not value:\n"
                "        push_error('IGRIS_RULE_FAILED:' + label)\n"
                "        return false\n"
                "    return true\n"
                "func _init() -> void:\n"
                "    var state = load('res://chess_state.gd').new()\n"
                "    var sliding = load('res://sliding_rules.gd').new()\n"
                "    var board = state.board\n"
                "    if not _require(sliding.rook(board, 'white', 0, 0, 0, 3), 'rook_nocapture'): quit(1); return\n"
                "    if not _require(not sliding.rook(board, 'white', 0, 0, 0, 0), 'rook_zero'): quit(1); return\n"
                "    board[1][0] = {'type': 'pawn', 'side': 'white'}\n"
                "    if not _require(not sliding.rook(board, 'white', 0, 0, 0, 3), 'rook_blocked'): quit(1); return\n"
                "    board[1][0] = null\n"
                "    if not _require(sliding.bishop(board, 'white', 2, 2, 4, 4), 'bishop_nocapture'): quit(1); return\n"
                "    board[3][3] = {'type': 'pawn', 'side': 'white'}\n"
                "    if not _require(not sliding.bishop(board, 'white', 2, 2, 4, 4), 'bishop_blocked'): quit(1); return\n"
                "    board[3][3] = null\n"
                "    if not _require(sliding.queen(board, 'white', 3, 3, 3, 5), 'queen_nocapture'): quit(1); return\n"
                "    if not _require(not sliding.queen(board, 'white', 3, 3, 3, 3), 'queen_zero'): quit(1); return\n"
                "    print('IGRIS_LOGIC_SMOKE_OK')\n"
                "    quit(0)\n"
            )
        if path == "jump_rules.gd":
            return (
                "extends SceneTree\n"
                "func _require(value: bool, label: String) -> bool:\n"
                "    if not value:\n"
                "        push_error('IGRIS_RULE_FAILED:' + label)\n"
                "        return false\n"
                "    return true\n"
                "func _init() -> void:\n"
                "    var state = load('res://chess_state.gd').new()\n"
                "    var jump = load('res://jump_rules.gd').new()\n"
                "    var board = state.board\n"
                "    if not _require(jump.is_knight_move(board, 'white', 1, 0, 2, 2), 'knight_jump'): quit(1); return\n"
                "    if not _require(not jump.is_knight_move(board, 'white', 1, 0, 1, 2), 'knight_gap'): quit(1); return\n"
                "    if not _require(jump.is_king_move(board, 'white', 4, 4, 4, 5), 'king_one'): quit(1); return\n"
                "    if not _require(not jump.is_king_move(board, 'white', 4, 4, 4, 4), 'king_zero'): quit(1); return\n"
                "    print('IGRIS_LOGIC_SMOKE_OK')\n"
                "    quit(0)\n"
            )
        return ""

    def _smoke_logic(self, project: Path, path: str) -> GodotRun:
        if path == "chess_rules.gd":
            return self._smoke_rules(project)
        harness_name = f"_igris_{path.replace('.', '_')}_logic_smoke.gd"
        harness = project / harness_name
        harness.write_text(
            self._logic_smoke_for(path),
            encoding="utf-8")
        try:
            runner = getattr(self.runtime, "run_script", None)
            if not callable(runner):
                return GodotRun(True, 0, "runtime smoke unsupported by test double")
            result = runner(project, harness_name)
            if result.ok and "IGRIS_LOGIC_SMOKE_OK" not in (result.output or ""):
                result = GodotRun(False, result.returncode,
                                  result.output +
                                  "\nIGRIS_LOGIC_SMOKE_OK no se imprimio en salida estandar")
            return result
        finally:
            harness.unlink(missing_ok=True)

    @staticmethod
    def _logic_smoke_for(path: str) -> str:
        if path == "chess_state.gd":
            return (
                "extends SceneTree\n"
                "func _require(value: bool, label: String) -> bool:\n"
                "    if not value:\n"
                "        push_error('IGRIS_RULE_FAILED:' + label)\n"
                "        return false\n"
                "    return true\n"
                "func _init() -> void:\n"
                "    var state = load('res://chess_state.gd').new()\n"
                "    if not _require(state.board.size() == 8, 'board_rows'): quit(1); return\n"
                "    var white_pawn = state.board[1][4]\n"
                "    if white_pawn == null:\n"
                "        push_error('IGRIS_RULE_FAILED:piece_identity_null')\n"
                "        quit(1)\n"
                "        return\n"
                "    if not _require(white_pawn.get('type') == 'pawn' and white_pawn.get('side') == 'white', 'piece_identity'): quit(1); return\n"
                "    var black_king = state.board[7][4]\n"
                "    if black_king == null:\n"
                "        push_error('IGRIS_RULE_FAILED:black_king_null')\n"
                "        quit(1)\n"
                "        return\n"
                "    if not _require(black_king.get('type') == 'king' and black_king.get('side') == 'black', 'black_king'): quit(1); return\n"
                "    var current_turn = state.current_turn\n"
                "    if not _require(current_turn == 'white', 'current_turn'): quit(1); return\n"
                "    var piece = state.get_piece(4, 1)\n"
                "    if piece == null:\n"
                "        push_error('IGRIS_RULE_FAILED:get_piece_null')\n"
                "        quit(1)\n"
                "        return\n"
                "    if not _require(piece.get('type') == 'pawn', 'get_piece'): quit(1); return\n"
                "    state.move_piece(4, 1, 4, 3)\n"
                "    if not _require(state.board[1][4] == null, 'move_piece_clear'): quit(1); return\n"
                "    if not _require(state.board[3][4] is Dictionary, 'move_piece_set'): quit(1); return\n"
                "    if not _require(state.current_turn == 'black', 'turn_switch'): quit(1); return\n"
                "    print('IGRIS_LOGIC_SMOKE_OK')\n"
                "    quit(0)\n"
            )
        if path == "pawn_rules.gd":
            return (
                "extends SceneTree\n"
                "func _require(value: bool, label: String) -> bool:\n"
                "    if not value:\n"
                "        push_error('IGRIS_RULE_FAILED:' + label)\n"
                "        return false\n"
                "    return true\n"
                "func _init() -> void:\n"
                "    var state = load('res://chess_state.gd').new()\n"
                "    var pawn = load('res://pawn_rules.gd').new()\n"
                "    var board = state.board\n"
                "    if not _require(pawn.is_valid_pawn_move(board, 'white', 4, 1, 4, 3), 'pawn_double'): quit(1); return\n"
                "    if not _require(not pawn.is_valid_pawn_move(board, 'white', 4, 1, 4, 4), 'pawn_too_far'): quit(1); return\n"
                "    board[2][4] = {'type': 'knight', 'side': 'black'}\n"
                "    if not _require(not pawn.is_valid_pawn_move(board, 'white', 4, 1, 4, 3), 'pawn_blocked'): quit(1); return\n"
                "    board[2][4] = null\n"
                "    board[2][5] = {'type': 'pawn', 'side': 'black'}\n"
                "    if not _require(pawn.is_valid_pawn_move(board, 'white', 4, 1, 5, 2), 'pawn_capture'): quit(1); return\n"
                "    board[2][5] = {'type': 'pawn', 'side': 'white'}\n"
                "    if not _require(not pawn.is_valid_pawn_move(board, 'white', 4, 1, 5, 2), 'pawn_capture_friendly'): quit(1); return\n"
                "    board[2][5] = null\n"
                "    if not _require(not pawn.is_valid_pawn_move(board, 'white', 4, 1, 4, 1), 'pawn_zero'): quit(1); return\n"
                "    print('IGRIS_LOGIC_SMOKE_OK')\n"
                "    quit(0)\n"
            )
        if path == "sliding_rules.gd":
            return (
                "extends SceneTree\n"
                "func _require(value: bool, label: String) -> bool:\n"
                "    if not value:\n"
                "        push_error('IGRIS_RULE_FAILED:' + label)\n"
                "        return false\n"
                "    return true\n"
                "func _init() -> void:\n"
                "    var state = load('res://chess_state.gd').new()\n"
                "    var sliding = load('res://sliding_rules.gd').new()\n"
                "    var board = state.board\n"
                "    if not _require(sliding.rook(board, 'white', 0, 0, 0, 3), 'rook_nocapture'): quit(1); return\n"
                "    if not _require(not sliding.rook(board, 'white', 0, 0, 0, 0), 'rook_zero'): quit(1); return\n"
                "    board[1][0] = {'type': 'pawn', 'side': 'white'}\n"
                "    if not _require(not sliding.rook(board, 'white', 0, 0, 0, 3), 'rook_blocked'): quit(1); return\n"
                "    board[1][0] = null\n"
                "    if not _require(sliding.bishop(board, 'white', 2, 2, 4, 4), 'bishop_nocapture'): quit(1); return\n"
                "    board[3][3] = {'type': 'pawn', 'side': 'white'}\n"
                "    if not _require(not sliding.bishop(board, 'white', 2, 2, 4, 4), 'bishop_blocked'): quit(1); return\n"
                "    board[3][3] = null\n"
                "    if not _require(sliding.queen(board, 'white', 3, 3, 3, 5), 'queen_nocapture'): quit(1); return\n"
                "    if not _require(not sliding.queen(board, 'white', 3, 3, 3, 3), 'queen_zero'): quit(1); return\n"
                "    print('IGRIS_LOGIC_SMOKE_OK')\n"
                "    quit(0)\n"
            )
        if path == "jump_rules.gd":
            return (
                "extends SceneTree\n"
                "func _require(value: bool, label: String) -> bool:\n"
                "    if not value:\n"
                "        push_error('IGRIS_RULE_FAILED:' + label)\n"
                "        return false\n"
                "    return true\n"
                "func _init() -> void:\n"
                "    var state = load('res://chess_state.gd').new()\n"
                "    var jump = load('res://jump_rules.gd').new()\n"
                "    var board = state.board\n"
                "    if not _require(jump.is_knight_move(board, 'white', 1, 0, 2, 2), 'knight_jump'): quit(1); return\n"
                "    if not _require(not jump.is_knight_move(board, 'white', 1, 0, 1, 2), 'knight_gap'): quit(1); return\n"
                "    if not _require(jump.is_king_move(board, 'white', 4, 4, 4, 5), 'king_one'): quit(1); return\n"
                "    if not _require(not jump.is_king_move(board, 'white', 4, 4, 4, 4), 'king_zero'): quit(1); return\n"
                "    print('IGRIS_LOGIC_SMOKE_OK')\n"
                "    quit(0)\n"
            )
        return ""

    @staticmethod
    def _targets(diagnostic: str, files: list[str]) -> list[str]:
        found = [path for path in files
                 if re.search(r"(^|[\\/])" + re.escape(path) + r"(:|\s|$)",
                              diagnostic, re.MULTILINE)]
        return found or ["main.gd"]
