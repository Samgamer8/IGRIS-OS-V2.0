import shutil

from igris_os.production_bootstrap import EXPERIMENTAL_CAPABILITIES
from igris_os.production_bootstrap_final import CAPABILITY, build_final_igris


def test_final_kernel_exposes_3d_only_with_real_godot(tmp_path):
    kernel = build_final_igris(tmp_path / "runtime")
    names = {spec.name for spec in kernel.registry.specs()}

    assert (CAPABILITY in names) is (shutil.which("godot") is not None)
    assert names.isdisjoint(EXPERIMENTAL_CAPABILITIES)
