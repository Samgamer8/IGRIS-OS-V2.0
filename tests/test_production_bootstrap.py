from igris_os.domain import Mission
from igris_os.production_bootstrap import (
    EXPERIMENTAL_CAPABILITIES,
    build_production_igris,
)


def test_production_kernel_excludes_uncertified_capabilities(tmp_path):
    kernel = build_production_igris(tmp_path / "runtime")
    names = {spec.name for spec in kernel.registry.specs()}

    assert names.isdisjoint(EXPERIMENTAL_CAPABILITIES)
    assert "programming.python.develop" in names
    assert "project.stage" in names


def test_production_languages_report_real_availability(tmp_path):
    kernel = build_production_igris(tmp_path / "runtime")

    result = kernel.execute(Mission("Detectar toolchains"),
                            "programming.languages")

    assert result.ok
    languages = {item["name"]: item for item in result.data["languages"]}
    assert languages["python"]["available"]
    assert all(isinstance(item["available"], bool)
               for item in languages.values())
    assert all("executable" in item for item in languages.values())
