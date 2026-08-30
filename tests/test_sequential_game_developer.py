import json

import pytest

from igris_os.ai import ModelReply
from igris_os.games.runtime import GodotRun
from igris_os.games.sequential_developer import (
    CHESS_COMPONENTS,
    SequentialGodotGameDeveloper,
)


def test_piece_factory_rejects_external_assets_and_runtime_csg():
    invalid = '''extends RefCounted
func create_piece(piece_type, side):
    var mesh = preload("res://path/to/pawn.mesh")
    var shape = CSGSphere3D.new()
    return shape
# pawn rook knight bishop queen king StandardMaterial3D MeshInstance3D
'''
    with pytest.raises(ValueError) as error:
        SequentialGodotGameDeveloper._validate("piece_factory.gd", invalid)
    message = str(error.value)
    assert "solo puede cargar sus seis scripts" in message
    assert "no debe usar CSG" in message


def test_piece_factory_accepts_small_visual_assembly_facade():
    valid = '''extends RefCounted
const PawnVisual = preload("res://pawn_visual.gd")
const RookVisual = preload("res://rook_visual.gd")
const KnightVisual = preload("res://knight_visual.gd")
const BishopVisual = preload("res://bishop_visual.gd")
const QueenVisual = preload("res://queen_visual.gd")
const KingVisual = preload("res://king_visual.gd")
func create_piece(piece_type, side):
    var builder = PawnVisual.new()
    var material = StandardMaterial3D.new()
    material.albedo_color = Color.WHITE
    material.metallic = 0.2
    material.roughness = 0.5
    return builder.build(material)
# pawn rook knight bishop queen king
'''
    SequentialGodotGameDeveloper._validate("piece_factory.gd", valid)


def test_piece_factory_rejects_per_piece_noise_and_static_bodies():
    invalid = '''extends RefCounted
func create_piece(piece_type, side):
    var body = StaticBody3D.new()
    var visual = MeshInstance3D.new()
    visual.mesh = SphereMesh.new()
    visual.material_override = StandardMaterial3D.new()
    var texture = NoiseTexture2D.new()
    return body
# pawn rook knight bishop queen king
'''
    with pytest.raises(ValueError) as error:
        SequentialGodotGameDeveloper._validate("piece_factory.gd", invalid)
    assert "cuerpo pesado" in str(error.value)


def test_visual_component_rejects_single_primitive_placeholders():
    invalid = '''extends RefCounted
func build(material):
    var root = Node3D.new()
    var visual = MeshInstance3D.new()
    visual.mesh = SphereMesh.new()
    root.add_child(visual)
    return root
'''
    with pytest.raises(ValueError) as error:
        SequentialGodotGameDeveloper._validate("pawn_visual.gd", invalid)
    message = str(error.value)
    assert "necesita al menos 4 partes" in message


def test_visual_component_rejects_nonexistent_cylinder_radii_property():
    invalid = '''extends RefCounted
func build(material):
    var root = Node3D.new()
    var mesh = CylinderMesh.new()
    mesh.radii = [0.2, 0.3]
    root.add_child(MeshInstance3D.new())
    root.add_child(MeshInstance3D.new())
    root.add_child(MeshInstance3D.new())
    root.add_child(MeshInstance3D.new())
    var sphere = SphereMesh.new()
    return root
'''
    with pytest.raises(ValueError) as error:
        SequentialGodotGameDeveloper._validate("pawn_visual.gd", invalid)
    assert "top_radius y bottom_radius" in str(error.value)


def test_resume_discards_obsolete_piece_factory_instead_of_prompt_anchoring(
        tmp_path):
    workspace = tmp_path / "workspace"
    project = workspace / "Chess_Test"
    project.mkdir(parents=True)
    obsolete = project / "piece_factory.gd"
    obsolete.write_text(
        'extends Node3D\nvar mesh = preload("res://missing.mesh")\n'
        '# pawn rook knight bishop queen king\n', encoding="utf-8")
    client = ComponentClient()
    developer = SequentialGodotGameDeveloper(
        client, workspace, "test", FakeRuntime())

    result = developer.develop_chess_3d(
        "original chess", "Chess Test", confirmed=True, resume=True)

    assert result.ok, result.diagnostics
    piece_prompts = [item for item in client.prompts
                     if "FILE: piece_factory.gd" in item]
    assert piece_prompts
    assert all("res://missing.mesh" not in item for item in piece_prompts)


class FakeRuntime:
    def __init__(self, failures=0):
        self.failures = failures
        self.imports = 0

    def import_project(self, project):
        self.imports += 1
        if self.imports <= self.failures:
            return GodotRun(False, 1, "res://main.gd:7 parse error")
        return GodotRun(True, 0, "import ok")

    def check_script(self, project, script):
        return GodotRun(True, 0, "script ok")

    def run(self, project, **kwargs):
        return GodotRun(True, 0, "boot ok")

    def run_script(self, project, script):
        name = str(script).replace("\\", "/").rsplit("/", 1)[-1]
        if name == "_igris_rules_smoke.gd":
            output = "IGRIS_RULE_SMOKE_OK\nfunctional smoke ok"
        elif name == "_igris_visual_smoke.gd":
            output = "IGRIS_VISUAL_SMOKE_OK: 6\nfunctional smoke ok"
        elif "logic_smoke" in name:
            output = "IGRIS_LOGIC_SMOKE_OK\nfunctional smoke ok"
        else:
            output = "functional smoke ok"
        return GodotRun(True, 0, output)

    def version(self):
        return "test-godot"


class ComponentClient:
    def __init__(self):
        self.prompts = []

    def generate_json(self, prompt, model, schema):
        self.prompts.append(prompt)
        path = next(
            component.path for component in CHESS_COMPONENTS
            if f"FILE: {component.path}" in prompt)
        class_name = path.removesuffix(".gd").title().replace("_", "")
        tokens = {
            "chess_state.gd": (
                "pawn rook knight bishop queen king current_turn move_piece "
                "setup_board side type"),
            "pawn_rules.gd": (
                "pawn is_valid_pawn_move direction start_row"),
            "sliding_rules.gd": "rook bishop queen is_path_clear",
            "jump_rules.gd": "knight king",
            "chess_rules.gd": (
                "is_valid_move res://pawn_rules.gd res://sliding_rules.gd "
                "res://jump_rules.gd is_valid_pawn_move .rook( .bishop( "
                ".queen( is_valid_knight_move is_valid_king_move"),
            "pawn_visual.gd": "func build SphereMesh.new add_child",
            "rook_visual.gd": "func build BoxMesh.new add_child",
            "knight_visual.gd": "func build rotation add_child",
            "bishop_visual.gd": "func build SphereMesh.new rotation add_child",
            "queen_visual.gd": "func build TorusMesh.new add_child",
            "king_visual.gd": "func build BoxMesh.new add_child",
            "piece_factory.gd": (
                "pawn rook knight bishop queen king StandardMaterial3D "
                "create_piece albedo_color metallic roughness "
                "res://pawn_visual.gd res://rook_visual.gd "
                "res://knight_visual.gd res://bishop_visual.gd "
                "res://queen_visual.gd res://king_visual.gd"),
            "board_view.gd": "board_size range(8) ray",
            "game_controller.gd": "is_valid_move create_tween",
            "main.gd": "--igris-capture Label",
        }.get(path, "camera controls")
        source = (
            "extends Node3D\n"
            f"class_name {class_name}\n"
            f"var acceptance_tokens := {tokens!r}\n"
            "func ready_for_test() -> bool:\n"
            "    return true\n"
        )
        if path == "chess_state.gd":
            source = (
                "extends RefCounted\n"
                "class_name ChessState\n"
                f"var acceptance_tokens := {tokens!r}\n"
                "var board = []\n"
                "var current_turn = 'white'\n"
                "func _init():\n"
                "    setup_board()\n"
                "func setup_board():\n"
                "    pass\n"
                "func move_piece(from_x, from_y, to_x, to_y):\n"
                "    pass\n"
            )
        if path.endswith("_visual.gd"):
            minimum = {
                "pawn_visual.gd": 4, "rook_visual.gd": 6,
                "knight_visual.gd": 4, "bishop_visual.gd": 4,
                "queen_visual.gd": 6, "king_visual.gd": 5,
            }[path]
            source += (
                "func build(material):\n"
                "    var root = Node3D.new()\n" +
                "".join("    root.add_child(MeshInstance3D.new())\n"
                        for _ in range(minimum)) +
                "    return root\n")
        if path == "piece_factory.gd":
            source += (
                "func create_piece(piece_type, side):\n"
                "    var material = StandardMaterial3D.new()\n"
                "    material.albedo_color = Color.WHITE\n"
                "    material.metallic = 0.2\n"
                "    material.roughness = 0.5\n"
                "    return Node3D.new()\n")
        return ModelReply(
            True, json.dumps({"content": source}), model)


class StrictFallbackClient(ComponentClient):
    def generate_json(self, prompt, model, schema):
        del schema
        self.prompts.append(prompt)
        return ModelReply(True, "valid transport but invalid structured body", model)

    def generate_strict(self, prompt, model):
        return ModelReply(
            True,
            "BEGIN_GDSCRIPT\nextends RefCounted\n"
            "class_name PawnRules\n"
            "var tokens = 'pawn is_valid_pawn_move direction start_row'\n"
            "END_GDSCRIPT",
            model,
        )


class TimedOutClient(ComponentClient):
    def __init__(self):
        super().__init__()
        self.strict_calls = 0

    def generate_json(self, prompt, model, schema):
        return ModelReply(False, "", model, "timed out")

    def generate_strict(self, prompt, model):
        self.strict_calls += 1
        return ModelReply(True, "BEGIN_GDSCRIPT\nextends Node\nEND_GDSCRIPT", model)


class RequeueClient(ComponentClient):
    def models(self):
        return ("qwen2.5-coder:7b", "stable-code:3b-code-q4_0")

    def generate_json(self, prompt, model, schema):
        del schema
        self.prompts.append(prompt)
        invalid = "MICRO-QUEUE ROUND" not in prompt
        source = (
            "extends RefCounted\n"
            "class_name PawnRules\n"
            "var tokens = 'pawn is_valid_pawn_move direction start_row'\n" +
            ("func _ready():\n    pass\n" if invalid else
             "func is_valid_pawn_move() -> bool:\n    return true\n")
        )
        return ModelReply(
            True, json.dumps({"content": source}), model)


def test_sequential_game_developer_generates_dependency_order(tmp_path):
    client = ComponentClient()
    result = SequentialGodotGameDeveloper(
        client, tmp_path, "test", FakeRuntime()).develop_chess_3d(
            "original chess game", "Chess Test", confirmed=True)

    assert result.ok, result.diagnostics
    piece_prompt = next(
        prompt for prompt in client.prompts if "FILE: piece_factory.gd" in prompt)
    assert "MANDATORY COMPONENT BLUEPRINT" in piece_prompt
    assert "six preload constants" in piece_prompt
    assert "original late-1990s dark-fantasy low-poly set" in piece_prompt
    assert "silver/ivory/blue" in piece_prompt
    assert result.files == tuple(item.path for item in CHESS_COMPONENTS)
    assert [prompt.split("FILE: ", 1)[1].splitlines()[0]
            for prompt in client.prompts] == list(result.files)
    assert (result.project / "CODE_DELIVERY.json").is_file()


def test_sequential_game_developer_repairs_reported_file(tmp_path):
    client = ComponentClient()
    runtime = FakeRuntime(failures=1)
    result = SequentialGodotGameDeveloper(
        client, tmp_path, "test", runtime).develop_chess_3d(
            "original chess game", "Chess Repair", confirmed=True)

    assert result.ok, result.diagnostics
    assert runtime.imports == 2
    assert len(client.prompts) == len(CHESS_COMPONENTS) + 1
    assert "GODOT ERROR TO REPAIR" in client.prompts[-1]
    assert "FILE: main.gd" in client.prompts[-1]


def test_sequential_game_developer_requires_confirmation(tmp_path):
    result = SequentialGodotGameDeveloper(
        ComponentClient(), tmp_path, "test", FakeRuntime()
    ).develop_chess_3d("chess", "Denied")
    assert not result.ok


def test_mechanical_repairs_names_discarded_loop_variables():
    source = (
        "extends RefCounted\n"
        "func build():\n"
        "    for _ in range(8):\n"
        "        pass\n"
    )

    repaired = SequentialGodotGameDeveloper._mechanical_repairs(source)

    assert "for unused_index_1 in range(8):" in repaired
    assert "for _ in" not in repaired


def test_mechanical_repairs_visual_mesh_api_slips():
    source = (
        "extends RefCounted\n"
        "func build(material: Material):\n"
        "    var detail_mesh = PlaneMesh.new()\n"
        "    var detail = MeshInstance3D.new()\n"
        "    detail_mesh.size = Vector3(0.1, 0.2, 0.3)\n"
        "    detail.material = material\n"
        "    detail.translation = Vector3.ZERO\n"
        "    var crown_mesh = TorusMesh.new()\n"
        "    crown_mesh.major_radius = 0.6\n"
        "    crown_mesh.minor_radius = 0.2\n"
        "    var crown = MeshInstance3D.new()\n"
        "    crown.mesh = TorusMesh.new()\n"
        "    crown.mesh.radius = 0.5\n"
        "    crown.mesh.ring_radius = 0.1\n"
    )

    repaired = SequentialGodotGameDeveloper._mechanical_repairs(source)

    assert "detail_mesh.size = Vector2(0.1, 0.2)" in repaired
    assert "detail.material_override = material" in repaired
    assert "detail.position = Vector3.ZERO" in repaired
    assert "crown_mesh.outer_radius = 0.6" in repaired
    assert "crown_mesh.inner_radius = 0.2" in repaired
    assert "crown.mesh.outer_radius = 0.5" in repaired
    assert "crown.mesh.inner_radius = 0.1" in repaired


def test_visual_validator_rejects_array_mesh_and_duplicate_variables():
    invalid = (
        "extends RefCounted\n"
        "func build(material: Material) -> Node3D:\n"
        "    var root = Node3D.new()\n"
        "    var point = MeshInstance3D.new()\n"
        "    var point = ArrayMesh.new()\n"
        "    var crown = TorusMesh.new()\n"
        + "    root.add_child(point)\n" * 6
        + "    return root\n"
    )

    with pytest.raises(ValueError) as error:
        SequentialGodotGameDeveloper._validate("queen_visual.gd", invalid)

    message = str(error.value)
    assert "PrimitiveMesh" in message
    assert "repite variables: point" in message


def test_extract_raw_script_accepts_marker_protocol():
    reply = (
        "BEGIN_GDSCRIPT\n"
        "extends RefCounted\n"
        "func ok() -> bool:\n"
        "    return true\n"
        "END_GDSCRIPT"
    )

    script = SequentialGodotGameDeveloper._extract_raw_script(reply)

    assert script.startswith("extends RefCounted")
    assert script.endswith("return true")


def test_generation_uses_strict_channel_after_structured_failure(tmp_path):
    developer = SequentialGodotGameDeveloper(
        StrictFallbackClient(), tmp_path, "test", FakeRuntime())
    component = next(
        item for item in CHESS_COMPONENTS
        if item.path == "pawn_rules.gd")

    content = developer._generate_valid(
        "chess", component, {}, "", attempts=1)

    assert content.startswith("extends RefCounted")
    assert "modo local offline" not in content
    assert developer.skill_catalog.loaded_names == ("component-build",)


def test_transport_failure_escalates_without_duplicate_format_request(tmp_path):
    client = TimedOutClient()
    developer = SequentialGodotGameDeveloper(
        client, tmp_path, "test", FakeRuntime())
    with pytest.raises(ValueError, match="timed out"):
        developer._generate(
            "objective", CHESS_COMPONENTS[0], {}, "", "test")
    assert client.strict_calls == 0


def test_rejected_microsector_returns_once_to_fast_queue(tmp_path):
    client = RequeueClient()
    developer = SequentialGodotGameDeveloper(
        client, tmp_path, "qwen2.5-coder:7b", FakeRuntime())
    project = tmp_path / "project"
    project.mkdir()
    component = next(
        item for item in CHESS_COMPONENTS
        if item.path == "pawn_rules.gd")

    content = developer._generate_with_tournament(
        "chess", component, {}, "", project)

    assert "func _ready" not in content
    assert any(
        "BEST REJECTED CANDIDATE TO REPAIR" in prompt
        for prompt in client.prompts)


def test_obsolete_component_is_not_recycled_into_prompt(tmp_path):
    client = ComponentClient()
    developer = SequentialGodotGameDeveloper(
        client, tmp_path, "test", FakeRuntime())
    project = tmp_path / "Legacy"
    project.mkdir()
    legacy = (
        "extends Node\nclass_name ChessRules\nclass_name ChessRules\n"
        "var board = []\nfunc _ready():\n    pass\n"
        "func initialize_board():\n    pass\n"
        "var tokens = 'is_valid_move res://pawn_rules.gd "
        "res://sliding_rules.gd res://jump_rules.gd is_valid_pawn_move "
        ".rook( .bishop( .queen( is_valid_knight_move "
        "is_valid_king_move'\n"
    )
    (project / "chess_rules.gd").write_text(legacy, encoding="utf-8")
    developer._project_path = lambda name: project

    developer.develop_chess_3d(
        "chess", "Legacy", confirmed=True, resume=True)

    facade_prompts = [
        prompt for prompt in client.prompts
        if "FILE: chess_rules.gd" in prompt]
    assert facade_prompts
    assert "OBSOLETE ARCHITECTURE" in facade_prompts[0]
    assert "class_name ChessRules\nclass_name ChessRules" not in facade_prompts[0]
    assert "CURRENT FILE TO REPAIR" not in facade_prompts[0]
