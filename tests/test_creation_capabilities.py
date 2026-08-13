from igris_os.bootstrap import build_igris
from igris_os.domain import Mission


def test_godot_capability_requires_kernel_confirmation(tmp_path):
    kernel = build_igris(tmp_path)
    denied = kernel.execute(Mission("juego"), "games.godot.scaffold",
                            {"name": "Demo"})
    allowed = kernel.execute(Mission("juego"), "games.godot.scaffold",
                             {"name": "Demo"}, confirmed=True)
    assert denied.code == "CONFIRMATION_REQUIRED"
    assert allowed.ok


def test_creation_catalog_is_visible(tmp_path):
    names = {spec.name for spec in build_igris(tmp_path).registry.specs()}
    assert "programming.python.develop" in names
    assert "multimedia.status" in names
