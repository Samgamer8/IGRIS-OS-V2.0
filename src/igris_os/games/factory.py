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
"""

SCENE = """[gd_scene load_steps=2 format=3]

[ext_resource path="res://main.gd" type="Script" id="1"]

[node name="Main" type="Node2D"]
script = ExtResource("1")
"""

SCRIPT = """extends Node2D

var player := Vector2(480, 270)
var speed := 260.0
var _frames := 0
var _capture_path := ""

func _ready():
    _capture_path = _capture_arg()
    queue_redraw()
    print("IGRIS_GAME_READY")

func _capture_arg() -> String:
    for arg in OS.get_cmdline_user_args():
        var prefix := "--igris-capture="
        if arg.begins_with(prefix):
            return arg.substr(prefix.length())
    return ""

func _process(delta):
    _frames += 1
    var direction := Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
    player += direction * speed * delta
    player.x = clamp(player.x, 24.0, 936.0)
    player.y = clamp(player.y, 24.0, 516.0)
    queue_redraw()
    if _capture_path != "" and _frames == 5:
        var image := get_viewport().get_texture().get_image()
        image.save_png(_capture_path)
        print("IGRIS_CAPTURE_SAVED")
        get_tree().quit()

func _draw():
    draw_rect(Rect2(0, 0, 960, 540), Color("10131d"))
    for x in range(0, 961, 48):
        draw_line(Vector2(x, 0), Vector2(x, 540), Color("211b2c"), 1.0)
    for y in range(0, 541, 48):
        draw_line(Vector2(0, y), Vector2(960, y), Color("211b2c"), 1.0)
    draw_circle(player, 22.0, Color("d11124"))
    draw_circle(player, 10.0, Color("ffb23e"))
    draw_string(ThemeDB.fallback_font, Vector2(24, 36),
        "IGRIS 2D STARTER · Mover: flechas", HORIZONTAL_ALIGNMENT_LEFT, -1, 20,
        Color("f1d7a0"))
"""

GENRE_CODE = {
    "top_down": 'var genre := "top_down"\n',
    "arcade": 'var genre := "arcade"\nvar score := 0\n',
    "platformer": (
        'var genre := "platformer"\n'
        'var gravity := 980.0\n'
        'var jump_force := 420.0\n'),
}


class GodotProjectFactory:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.resolve()

    def create(self, name: str, *, genre: str = "top_down",
               confirmed: bool = False) -> Path:
        if not confirmed:
            raise PermissionError("Se necesita confirmacion")
        safe_name = "".join(c for c in name if c.isalnum() or c in " _-").strip()
        if not safe_name:
            raise ValueError("Nombre invalido")
        normalized_genre = genre.casefold().strip().replace("-", "_")
        if normalized_genre not in GENRE_CODE:
            raise ValueError("Genero no soportado")
        root = safe_output(self.workspace, safe_name.replace(" ", "_"))
        root.mkdir(parents=True, exist_ok=False)
        (root / "project.godot").write_text(
            PROJECT.format(name=safe_name), encoding="utf-8")
        (root / "main.tscn").write_text(SCENE, encoding="utf-8")
        body = SCRIPT.removeprefix("extends Node2D\n")
        (root / "main.gd").write_text(
            "extends Node2D\n" + GENRE_CODE[normalized_genre] + body,
            encoding="utf-8")
        report = {"files_present": all(
                      (root / item).is_file()
                      for item in ("project.godot", "main.tscn", "main.gd")),
                  "genre": normalized_genre,
                  "godot_checked": False, "godot_ok": None}
        runtime = GodotRuntime()
        if runtime.available:
            version = runtime.version()
            report.update(godot_checked=True, godot_version=version)
            imported = runtime.import_project(root)
            report.update(godot_ok=imported.ok,
                          diagnostic=imported.output[-1200:])
        (root / "VERIFICATION.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return root

    @staticmethod
    def validate(root: Path) -> bool:
        required = ("project.godot", "main.tscn", "main.gd",
                    "VERIFICATION.json")
        return all((root / name).is_file() for name in required)
