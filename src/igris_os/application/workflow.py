from dataclasses import dataclass, field
from threading import Thread, Lock
from typing import Callable, Any
import json
import os


@dataclass
class WorkflowNode:
    id: str
    handler: Callable[[dict], Any]
    inputs: list[str] = field(default_factory=list)


class WorkflowGraph:
    def __init__(self):
        self.nodes: dict[str, WorkflowNode] = {}
        self.edges: dict[str, list[str]] = {}

    def add_node(self, node: WorkflowNode):
        self.nodes[node.id] = node
        self.edges.setdefault(node.id, [])

    def add_edge(self, from_id: str, to_id: str):
        self.edges.setdefault(from_id, []).append(to_id)
        self.edges.setdefault(to_id, [])

    def _topo_levels(self):
        in_degree = {n: 0 for n in self.nodes}
        for src, targets in self.edges.items():
            for t in targets:
                in_degree[t] += 1
        levels = []
        remaining = dict(in_degree)
        while remaining:
            level = [n for n, d in remaining.items() if d == 0]
            if not level:
                break
            levels.append(level)
            for n in level:
                del remaining[n]
                for t in self.edges.get(n, []):
                    remaining[t] -= 1
        return levels

    def run(self, context: dict) -> dict:
        results = dict(context)
        for level in self._topo_levels():
            errors = []
            lock = Lock()

            def wrap(node):
                try:
                    results[node.id] = node.handler(results)
                except Exception as e:
                    with lock:
                        errors.append(e)

            threads = [Thread(target=wrap, args=(self.nodes[n],)) for n in level]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            if errors:
                return results
        return results

    def checkpoint(self, state: dict, path: str):
        with open(path, "w") as f:
            json.dump(state, f)

    def resume(self, path: str) -> dict:
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
        return {}
