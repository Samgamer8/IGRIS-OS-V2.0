from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True, slots=True)
class Godot3DProject:
    root: Path
    project_name: str
    genre: str
    scenes: tuple[str, ...] = ()
    scripts: tuple[str, ...] = ()
    assets: tuple[str, ...] = ()
    physics: bool = True
    navigation: bool = True
    shaders: bool = True


class Godot4AdvancedFactory:
    PHYSICS_PRESETS = {
        "fps": ("CharacterBody3D", "first_person"),
        "third_person": ("CharacterBody3D", "third_person"),
        "racing": ("VehicleBody3D", "raycast"),
        "flight": ("RigidBody3D", "flight"),
    }

    SHADER_PRESETS = {
        "standard": "StandardMaterial3D",
        "toon": "ShaderMaterial",
        "water": "ShaderMaterial",
        "terrain": "ShaderMaterial",
    }

    def create_3d_project(self, root: Path, name: str, genre: str,
                          *, confirmed: bool = False) -> Godot3DProject:
        if not confirmed:
            raise PermissionError("Se necesita confirmacion")
        project_root = (root / name).resolve()
        project_root.mkdir(parents=True, exist_ok=True)
        (project_root / "project.godot").write_text(self._godot_config(name), encoding="utf-8")
        (project_root / "main.tscn").write_text(self._main_scene(genre), encoding="utf-8")
        (project_root / "player.gd").write_text(self._player_script(genre), encoding="utf-8")
        (project_root / "world.gd").write_text(self._world_script(genre), encoding="utf-8")
        if genre in self.PHYSICS_PRESETS:
            (project_root / "physics.gd").write_text(self._physics_script(genre), encoding="utf-8")
        if self.SHADER_PRESETS.get("standard"):
            (project_root / "materials.tres").write_text(self._materials_resource(), encoding="utf-8")
        return Godot3DProject(
            root=project_root, project_name=name, genre=genre,
            scenes=("main.tscn",), scripts=("player.gd", "world.gd", "physics.gd"),
            assets=("materials.tres",),
        )

    def _godot_config(self, name: str) -> str:
        return '[application]\n\nconfig/name="' + name + '"\nconfig/description="IGRIS 3D"\nrun/main_scene="res://main.tscn"\n\n[display]\n\nwindow/size/viewport_width=1920\nwindow/size/viewport_height=1080\nwindow/size/mode=2\n\n[rendering]\n\nrenderer/rendering_method="forward_plus"\n'

    def _main_scene(self, genre: str) -> str:
        return f"""[gd_scene load_steps=2 format=3]

[ext_resource type="Script" path="res://player.gd" id="1"]
[ext_resource type="Script" path="res://world.gd" id="2"]

[node name="Main" type="Node3D"]
script = ExtResource("2")

[node name="Player" type="CharacterBody3D" parent="."]
script = ExtResource("1")

[node name="Camera3D" type="Camera3D" parent="Player"]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 1.8, 0)

[node name="DirectionalLight3D" type="DirectionalLight3D" parent="."]
transform = Transform3D(0.866, -0.433, 0.25, 0, 0.5, 0.866, -0.5, -0.75, 0.433, 0, 10, 0)
light_color = Color(1, 0.95, 0.9, 1)
light_energy = 1.2
"""

    def _player_script(self, genre: str) -> str:
        return """extends CharacterBody3D

@export var speed = 5.0
@export var jump_velocity = 4.5
@export var mouse_sensitivity = 0.002

var gravity = ProjectSettings.get_setting("physics/3d/default_gravity")

func _ready():
    Input.mouse_mode = Input.MOUSE_MODE_CAPTURED

func _input(event):
    if event is InputEventMouseMotion:
        rotate_y(-event.relative.x * mouse_sensitivity)
        $Camera3D.rotate_x(-event.relative.y * mouse_sensitivity)
        $Camera3D.rotation.x = clamp($Camera3D.rotation.x, -PI/2, PI/2)

func _physics_process(delta):
    if not is_on_floor():
        velocity.y -= gravity * delta
    if Input.is_action_just_pressed("ui_accept") and is_on_floor():
        velocity.y = jump_velocity
    var input_dir = Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
    var forward = -global_transform.basis.z
    forward.y = 0
    forward = forward.normalized()
    var right = global_transform.basis.x
    var direction = forward * input_dir.y + right * input_dir.x
    if direction:
        velocity.x = direction.x * speed
        velocity.z = direction.z * speed
    else:
        velocity.x = move_toward(velocity.x, 0, speed)
        velocity.z = move_toward(velocity.z, 0, speed)
    move_and_slide()
"""

    def _world_script(self, genre: str) -> str:
        return """extends Node3D

func _ready():
    if OS.has_feature("editor"):
        print("IGRIS 3D ready in editor")
    else:
        print("IGRIS 3D running")
"""

    def _physics_script(self, genre: str) -> str:
        return """extends Node3D

func _process(delta):
    var fps = Engine.get_frames_per_second()
    if fps < 30:
        push_warning("FPS bajo: %d" % fps)
"""

    def _materials_resource(self) -> str:
        return """[gd_resource type="StandardMaterial3D" load_steps=2 format=3]

[ext_resource type="Texture2D" path="res://textures/default.png" id="1"]

[resource]
albedo_color = Color(0.6, 0.6, 0.6, 1)
metallic = 0.1
roughness = 0.8
"""


class GodotPlaytester:
    def __init__(self, godot_path: Path | None = None) -> None:
        self.godot_path = godot_path or self._find_godot()

    def run_headless(self, project: Path, *, timeout: int = 60) -> CompilationResult:
        if not self.godot_path:
            return CompilationResult(False, "Godot no encontrado",
                                     diagnostics=("godot_missing",))
        cmd = [str(self.godot_path), "--headless", "--quit", "--path", str(project)]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout, check=False,
            )
            return CompilationResult(
                result.returncode == 0,
                "Playtest headless completado",
                result.stdout.strip(),
                result.stderr.strip(),
                result.returncode,
            )
        except subprocess.TimeoutExpired:
            return CompilationResult(False, "timeout", diagnostics=("timeout",))
        except Exception as exc:
            return CompilationResult(False, str(exc), diagnostics=(str(exc),))

    def capture_frame(self, project: Path, output: Path) -> CompilationResult:
        if not self.godot_path:
            return CompilationResult(False, "Godot no encontrado")
        cmd = [
            str(self.godot_path), "--headless",
            "--path", str(project),
            "--script", "res://capture.gd",
            "--", str(output),
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30, check=False,
            )
            return CompilationResult(result.returncode == 0, "Frame capturada",
                                     result.stdout.strip(), result.stderr.strip())
        except Exception as exc:
            return CompilationResult(False, str(exc))

    @staticmethod
    def _find_godot() -> Path | None:
        candidates = [
            Path("C:/Program Files/Godot/Godot4.exe"),
            Path("C:/Program Files (x86)/Godot/Godot4.exe"),
            Path.home() / "AppData/Local/Godot/Godot4.exe",
        ]
        for path in candidates:
            if path.exists():
                return path
        return None
