from igris_os.bootstrap import build_igris
from igris_os.domain import Mission


def test_plan_capability(tmp_path):
    result = build_igris(tmp_path).execute(
        Mission("plan"), "mission.plan",
        {"objective": "construye un programa Python"})
    assert result.ok
    assert result.data["branch"] == "programming"
    assert "deliverables" in result.data
    assert "acceptance_criteria" in result.data


def test_tool_discovery_capability(tmp_path):
    result = build_igris(tmp_path).execute(Mission("tools"), "system.tools")
    assert result.ok
    assert any(tool["name"] == "ffmpeg" for tool in result.data["tools"])


def test_k3_gate_capability(tmp_path):
    result = build_igris(tmp_path).execute(Mission("motor k3"), "k3.gate")
    if result.code == "K3_NOT_BUILT":
        import pytest
        pytest.skip("motor K3 no compilado (.tools/k3/build.ps1)")
    assert result.ok, result.message
    assert result.data["gates"] == 3
    assert "MATCHES THE REFERENCE" in result.data["verdict"]


def test_k3_run_requires_local_checkpoint(tmp_path):
    result = build_igris(tmp_path).execute(
        Mission("motor k3"), "k3.run", {"model_dir": str(tmp_path), "prompt": "hola"})
    if result.code == "K3_NOT_BUILT":
        import pytest
        pytest.skip("motor K3 no compilado (.tools/k3/build.ps1)")
    assert result.code == "K3_NO_MODEL"
    assert not result.ok

