from pathlib import Path

from igris_os.tools import safe_output


PROJECT = """[application]
config/name="{name}"
run/main_scene="res://main.tscn"
[display]
window/size/viewport_width=960
window/size/viewport_height=540
[rendering]
renderer/rendering_method="gl_compatibility"
"""
SCENE = """[gd_scene load_steps=2 format=3]

[ext_resource path="res://main.gd" type="Script" id="1"]

[node name="Main" type="Node2D"]
script = ExtResource("1")
"""
SCRIPT = """extends Node2D

func _ready():
    print("IGRIS_GAME_READY")
"""


class GodotProjectFactory:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.resolve()

    def create(self, name: str, *, confirmed: bool = False) -> Path:
        if not confirmed:
            raise PermissionError("Se necesita confirmacion")
        safe_name = "".join(c for c in name if c.isalnum() or c in " _-").strip()
        if not safe_name:
            raise ValueError("Nombre invalido")
        root = safe_output(self.workspace, safe_name.replace(" ", "_"))
        root.mkdir(parents=True, exist_ok=False)
        (root / "project.godot").write_text(PROJECT.format(name=safe_name),
                                            encoding="utf-8")
        (root / "main.tscn").write_text(SCENE, encoding="utf-8")
        (root / "main.gd").write_text(SCRIPT, encoding="utf-8")
        return root

    @staticmethod
    def validate(root: Path) -> bool:
        return all((root / name).is_file()
                   for name in ("project.godot", "main.tscn", "main.gd"))
