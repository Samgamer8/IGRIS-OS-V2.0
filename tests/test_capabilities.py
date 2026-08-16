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
