"""Tests del nucleo CapabilityPipeline: 'IA que crea IAs'.

Deterministas, sin red ni GPU. Usan un ejecutor falso que emula el contrato
``.ok`` / ``.data`` de ExecutionResult.
"""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from igris_os.application.pipeline import (
    CapabilityPipeline, PipelineError, PipelineNode,
)


class _FakeResult(SimpleNamespace):
    pass


def _ok(**data):
    return _FakeResult(ok=True, message="ok", data=data)


def _fail(msg="boom"):
    return _FakeResult(ok=False, message=msg, data={})


class PipelineTests(unittest.TestCase):
    def test_topological_levels_order(self):
        pipe = CapabilityPipeline(name="t")
        pipe.add_node(PipelineNode("b", "x.y", depends_on=("a",)))
        pipe.add_node(PipelineNode("a", "x.y"))
        pipe.add_node(PipelineNode("c", "x.y", depends_on=("b",)))
        self.assertEqual(pipe.topological_levels(), [["a"], ["b"], ["c"]])

    def test_cycle_detected(self):
        pipe = CapabilityPipeline(name="t")
        pipe.add_node(PipelineNode("a", "x.y", depends_on=("b",)))
        pipe.add_node(PipelineNode("b", "x.y", depends_on=("a",)))
        with self.assertRaises(PipelineError):
            pipe.topological_levels()

    def test_validate_unknown_capability(self):
        pipe = CapabilityPipeline(name="t")
        pipe.add_node(PipelineNode("a", "no.existe"))
        problems = pipe.validate(available={"si.existe"})
        self.assertTrue(any("desconocida" in p for p in problems))

    def test_validate_unknown_dependency(self):
        pipe = CapabilityPipeline(name="t")
        pipe.add_node(PipelineNode("a", "x.y", depends_on=("fantasma",)))
        problems = pipe.validate()
        self.assertTrue(any("dependencia desconocida" in p for p in problems))

    def test_run_passes_data_between_nodes(self):
        pipe = CapabilityPipeline(name="t")
        pipe.add_node(PipelineNode("scan", "repository.analyze",
                                   payload={"path": "C:/repo"}))
        pipe.add_node(PipelineNode("dev", "repository.develop",
                                   depends_on=("scan",),
                                   payload={"files": "{{scan.data.files}}"}))

        calls = {}

        def executor(capability, payload):
            calls[capability] = payload
            if capability == "repository.analyze":
                return _ok(files=7)
            return _ok(built=payload["files"])

        out = pipe.run(executor)
        self.assertTrue(out["__completed__"])
        self.assertEqual(calls["repository.analyze"]["path"], "C:/repo")
        self.assertEqual(calls["repository.develop"]["files"], "7")
        self.assertEqual(out["dev"]["data"]["built"], "7")

    def test_run_stops_on_failure(self):
        pipe = CapabilityPipeline(name="t")
        pipe.add_node(PipelineNode("a", "repository.analyze"))
        pipe.add_node(PipelineNode("b", "repository.develop", depends_on=("a",)))
        executed = []

        def executor(capability, payload):
            executed.append(capability)
            return _fail("sin permisos") if capability == "repository.analyze" else _ok()

        out = pipe.run(executor)
        self.assertEqual(out["__failed_node__"], "a")
        self.assertNotIn("repository.develop", executed)
        self.assertNotIn("__completed__", out)

    def test_trace_records_each_node(self):
        pipe = CapabilityPipeline(name="t")
        pipe.add_node(PipelineNode("a", "x.y"))
        pipe.add_node(PipelineNode("b", "x.y", depends_on=("a",)))
        out = pipe.run(lambda c, p: _ok())
        trace = out["__trace__"]
        self.assertEqual([r["node"] for r in trace], ["a", "b"])
        self.assertTrue(all(r["ok"] for r in trace))

    def test_persistence_roundtrip(self):
        pipe = CapabilityPipeline(name="fabrica", description="demo")
        pipe.add_node(PipelineNode("a", "repository.analyze", payload={"p": 1}))
        pipe.add_node(PipelineNode("b", "repository.develop",
                                   depends_on=("a",), payload={"f": "{{a.data.files}}"}))
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "pipeline.json"
            pipe.save(path)
            loaded = CapabilityPipeline.load(path)
            self.assertEqual(loaded.name, "fabrica")
            self.assertEqual(loaded.description, "demo")
            self.assertEqual(set(loaded.nodes), {"a", "b"})
            self.assertEqual(loaded.nodes["b"].depends_on, ("a",))
            # El JSON es legible/portable
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["name"],
                             "fabrica")

    def test_invalid_node_id_rejected(self):
        with self.assertRaises(PipelineError):
            PipelineNode("id con espacio", "x.y")

    def test_capability_requires_dot(self):
        with self.assertRaises(PipelineError):
            PipelineNode("ok_id", "sinpunto")


if __name__ == "__main__":
    unittest.main()
