import shutil

from igris_os.production_bootstrap import EXPERIMENTAL_CAPABILITIES
from igris_os.production_bootstrap_release import (
    NODE_CAPABILITY,
    build_release_igris,
)


def test_release_kernel_exposes_only_strict_node_path(tmp_path):
    kernel = build_release_igris(tmp_path / "runtime")
    names = {spec.name for spec in kernel.registry.specs()}

    assert (NODE_CAPABILITY in names) is (shutil.which("node") is not None)
    assert "programming.multilang.develop" not in names
    assert names.isdisjoint(EXPERIMENTAL_CAPABILITIES)
