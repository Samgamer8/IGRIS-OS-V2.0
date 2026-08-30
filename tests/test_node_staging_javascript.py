import json

import pytest

from igris_os.ai import ModelReply
from igris_os.application.node_staging import StrictNodeStagingDeveloper
from igris_os.application.project_mission import ProjectMissionFactory
from igris_os.application.project_planning import ProjectMissionPlanner


class PackageClient:
    def __init__(self, package):
        self.package = package

    def generate_json(self, prompt, model, schema):
        return ModelReply(True, json.dumps(self.package), model)


def _planned(tmp_path):
    destination = tmp_path / "delivery"
    destination.mkdir()
    mission = ProjectMissionFactory().create("Crea una suma", {
        "technology": "javascript", "delivery": "source",
        "destination": str(destination), "acceptance": "suma dos numeros",
    })
    return ProjectMissionPlanner().plan(mission)


def test_javascript_staging_runs_node_test(tmp_path):
    package = {"name": "sum-js", "readme": "uso", "files": {
        "main.js": "export const add = (a, b) => a + b;\n",
        "test_main.js": (
            "import test from 'node:test';\nimport assert from 'node:assert/strict';\n"
            "import { add } from './main.js';\ntest('add', () => assert.equal(add(2, 3), 5));\n"),
    }}
    result = StrictNodeStagingDeveloper(
        PackageClient(package), tmp_path / "workspace", "fake").stage(
            _planned(tmp_path))

    assert (result.root / "VERIFICATION.json").is_file()
    assert result.changed_files == ("main.js", "test_main.js")


def test_node_staging_rejects_dangerous_process_execution(tmp_path):
    package = {"name": "bad", "readme": "", "files": {
        "main.js": "import { execSync } from 'node:child_process';\nexecSync('whoami');\n",
        "test_main.js": "import test from 'node:test';\ntest('x', () => {});\n",
    }}
    with pytest.raises(ValueError, match="peligroso"):
        StrictNodeStagingDeveloper(
            PackageClient(package), tmp_path / "workspace", "fake").stage(
                _planned(tmp_path))
