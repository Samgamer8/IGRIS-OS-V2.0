import json

from igris_os.ai import ModelReply
from igris_os.application.node_staging_final import FinalNodeStagingDeveloper
from igris_os.application.project_mission import ProjectMissionFactory
from igris_os.application.project_planning import ProjectMissionPlanner


class Client:
    def generate_json(self, prompt, model, schema):
        return ModelReply(True, json.dumps({
            "name": "final-ts", "readme": "uso", "files": {
                "main.ts": "export const add = (a: number, b: number): number => a + b;\n",
                "test_main.ts": (
                    "import test from 'node:test';\n"
                    "import assert from 'node:assert/strict';\n"
                    "import { add } from './main.js';\n"
                    "test('add', () => assert.equal(add(2, 3), 5));\n"),
            }}), model)


def test_final_typescript_compiles_and_executes(tmp_path):
    destination = tmp_path / "delivery"
    destination.mkdir()
    mission = ProjectMissionFactory().create("Crea una suma TypeScript", {
        "technology": "typescript", "delivery": "source",
        "destination": str(destination), "acceptance": "suma dos números",
    })
    planned = ProjectMissionPlanner().plan(mission)

    result = FinalNodeStagingDeveloper(
        Client(), tmp_path / "workspace", "fake").stage(planned)

    assert (result.root / "dist" / "main.js").is_file()
    assert (result.root / "dist" / "test_main.js").is_file()
    assert json.loads(
        (result.root / "VERIFICATION.json").read_text())["tests_passed"]
