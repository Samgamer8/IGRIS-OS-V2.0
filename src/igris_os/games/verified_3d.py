from __future__ import annotations

import json
from pathlib import Path

from igris_os.games.runtime import GodotRuntime
from igris_os.tools import safe_output


PROJECT = """[application]
config/name="{name}"
run/main_scene="res://main.tscn"
[display]
window/size/viewport_width=960
window/size/viewport_height=540
window/size/window_width_override=960
window/size/window_height_override=540
[rendering]
renderer/rendering_method="gl_compatibility"
renderer/rendering_method.mobile="gl_compatibility"
environment/defaults/default_clear_color=Color(0.025, 0.035, 0.08, 1)
"""

SCENE = """[gd_scene load_steps=7 format=3]

[ext_resource type="Script" path="res://main.gd" id="1"]

[sub_resource type="StandardMaterial3D" id="RedMaterial"]
albedo_color = Color(0.82, 0.03, 0.08, 1)
metallic = 0.25
roughness = 0.35

[sub_resource type="BoxMesh" id="CubeMesh"]
material = SubResource("RedMaterial")
size = Vector3(2.2, 2.2, 2.2)

[sub_resource type="StandardMaterial3D" id="FloorMaterial"]
albedo_color = Color(0.08, 0.1, 0.18, 1)
metallic = 0.1
roughness = 0.8

[sub_resource type="PlaneMesh" id="FloorMesh"]
material = SubResource("FloorMaterial")
size = Vector2(18, 18)

[sub_resource type="Environment" id="Environment"]
background_mode = 1
background_color = Color(0.025, 0.035, 0.08, 1)
ambient_light_source = 3
ambient_light_color = Color(0.25, 0.3, 0.55, 1)
ambient_light_energy = 0.65

[node name="Main" type="Node3D"]
script = ExtResource("1")

[node name="WorldEnvironment" type="WorldEnvironment" parent="."]
environment = SubResource("Environment")

[node name="Cube" type="MeshInstance3D" parent="."]
mesh = SubResource("CubeMesh")

[node name="Floor" type="MeshInstance3D" parent="."]
position = Vector3(0, -1.45, 0)
mesh = SubResource("FloorMesh")

[node name="Camera3D" type="Camera3D" parent="."]
position = Vector3(0, 2.2, 7.2)
rotation_degrees = Vector3(-12, 0, 0)
current = true

[node name="KeyLight" type="DirectionalLight3D" parent="."]
rotation_degrees = Vector3(-50, -30, 0)
light_color = Color(1, 0.88, 0.72, 1)
light_energy = 1.4

[node name="FillLight" type="OmniLight3D" parent="."]
position = Vector3(-3, 2, 3)
light_color = Color(0.2, 0.35, 1, 1)
light_energy = 3.0
omni_range = 10.0
"""

SCRIPT = """extends Node3D

var _frames := 0
var _capture_path := ""

func _ready() -> void:
    _capture_path = _capture_arg()
    print("IGRIS_3D_READY")

func _capture_arg() -> String:
    for arg in OS.get_cmdline_user_args():
        var prefix := "--igris-capture="
        if arg.begins_with(prefix):
            return arg.substr(prefix.length())
    return ""

func _process(delta: float) -> void:
    _frames += 1
    $Cube.rotate_y(delta * 0.7)
    $Cube.rotate_x(delta * 0.25)
    if _capture_path != "" and _frames == 10:
        await RenderingServer.frame_post_draw
        var image := get_viewport().get_texture().get_image()
        var error := image.save_png(_capture_path)
        if error == OK:
            print("IGRIS_3D_CAPTURE_SAVED")
        else:
            push_error("No se pudo guardar la captura: %s" % error)
        get_tree().quit()
"""


class VerifiedGodot3DFactory:
    """Genera un starter 3D que puede arrancar, renderizar y exportarse."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = Path(workspace).resolve()

    def create(self, name: str, *, confirmed: bool = False) -> Path:
        if not confirmed:
            raise PermissionError("Se necesita confirmación")
        safe_name = "".join(
            char for char in name if char.isalnum() or char in " _-").strip()
        if not safe_name:
            raise ValueError("Nombre inválido")
        root = safe_output(self.workspace, safe_name.replace(" ", "_"))
        root.mkdir(parents=True, exist_ok=False)
        (root / "project.godot").write_text(
            PROJECT.format(name=safe_name), encoding="utf-8")
        (root / "main.tscn").write_text(SCENE, encoding="utf-8")
        (root / "main.gd").write_text(SCRIPT, encoding="utf-8")
        runtime = GodotRuntime()
        report = {
            "dimension": "3D",
            "files_present": True,
            "godot_checked": runtime.available,
            "godot_ok": None,
        }
        if runtime.available:
            imported = runtime.import_project(root)
            report.update(
                godot_version=runtime.version(),
                godot_ok=imported.ok,
                diagnostic=imported.output[-1200:],
            )
        (root / "VERIFICATION.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return root
