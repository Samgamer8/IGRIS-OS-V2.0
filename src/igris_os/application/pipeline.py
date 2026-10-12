"""CapabilityPipeline: une capacidades REALES de IGRIS en un grafo ejecutable.

Es el nucleo de "IA que crea IAs": en lugar de escribir codigo, el usuario
encadena capabilities existentes de IGRIS (``repository.analyze`` ->
``repository.develop`` -> ``repository.apply_verified``) formando un pipeline.
El grafo se puede guardar/cargar en JSON y ejecutarse mediante un ejecutor de
capabilities (en produccion envuelve a ``IgrisKernel.execute``, respetando la
politica de riesgo, la aprobacion y la auditoria).

Diseno local-first y sin dependencias externas (solo stdlib). La ejecucion es
determinista y secuencial por niveles topologicos para poder pasar la salida de
un nodo como entrada del siguiente. No copia ningun motor de terceros.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from pathlib import Path
from typing import Any, Callable, Iterable

# Ejecutor de capabilities: recibe (nombre_capability, payload) y devuelve un
# resultado con al menos ``.ok`` y ``.data`` (compatible con ExecutionResult).
CapabilityExecutor = Callable[[str, dict], Any]

# Referencia a la salida de otro nodo dentro de un payload:
#   {{otro_nodo.data.campo}}  o  {{otro_nodo.output}}
_REF = re.compile(r"\{\{\s*([A-Za-z0-9_.]+)\s*\}\}")


class PipelineError(ValueError):
    """Error de definicion del pipeline (ciclo, dependencia o capacidad)."""


@dataclass(frozen=True, slots=True)
class PipelineNode:
    """Un paso del pipeline ligado a una capability real de IGRIS."""

    id: str
    capability: str
    depends_on: tuple[str, ...] = ()
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id or not re.fullmatch(r"[A-Za-z0-9_\-]+", self.id):
            raise PipelineError(f"id de nodo invalido: {self.id!r}")
        if not self.capability or "." not in self.capability:
            raise PipelineError(f"capability invalida: {self.capability!r}")


@dataclass
class CapabilityPipeline:
    """Grafo de capabilities con validacion, persistencia y ejecucion."""

    name: str
    description: str = ""
    nodes: dict[str, PipelineNode] = field(default_factory=dict)

    def add_node(self, node: PipelineNode) -> PipelineNode:
        if node.id in self.nodes:
            raise PipelineError(f"nodo duplicado: {node.id}")
        self.nodes[node.id] = node
        return node

    # -- validacion ------------------------------------------------------
    def validate(self, available: Iterable[str] | None = None) -> list[str]:
        """Devuelve una lista de problemas (vacia = valido).

        Comprueba capacidades inexistentes, dependencias desconocidas y ciclos.
        """
        problems: list[str] = []
        available_set = set(available) if available is not None else None
        for node in self.nodes.values():
            if available_set is not None and node.capability not in available_set:
                problems.append(f"{node.id}: capability desconocida '{node.capability}'")
            for dep in node.depends_on:
                if dep not in self.nodes:
                    problems.append(f"{node.id}: dependencia desconocida '{dep}'")
                if dep == node.id:
                    problems.append(f"{node.id}: depende de si mismo")
        try:
            self.topological_levels()
        except PipelineError as exc:
            problems.append(str(exc))
        return problems

    def topological_levels(self) -> list[list[str]]:
        """Niveles topologicos (Kahn). Lanza PipelineError si hay ciclo."""
        in_degree = {nid: 0 for nid in self.nodes}
        for node in self.nodes.values():
            for dep in node.depends_on:
                in_degree[node.id] += 1
        levels: list[list[str]] = []
        remaining = dict(in_degree)
        while remaining:
            level = sorted(nid for nid, deg in remaining.items() if deg == 0)
            if not level:
                raise PipelineError("el grafo tiene un ciclo")
            levels.append(level)
            for nid in level:
                del remaining[nid]
                for node in self.nodes.values():
                    if nid in node.depends_on:
                        remaining[node.id] -= 1
        return levels

    def topological_levels_or_none(self) -> list[list[str]]:
        """Como ``topological_levels`` pero tolerante: si hay ciclo devuelve los
        nodos ya ordenados y el resto suelto al final (para la UI, que no debe
        romperse mientras el usuario edita)."""
        try:
            return self.topological_levels()
        except PipelineError:
            placed: set[str] = set()
            levels = self._topological_best_effort(placed)
            leftover = sorted(nid for nid in self.nodes if nid not in placed)
            if leftover:
                levels.append(leftover)
            return levels

    def _topological_best_effort(self, placed: set[str]) -> list[list[str]]:
        levels: list[list[str]] = []
        remaining = set(self.nodes)
        while remaining:
            ready = sorted(
                nid for nid in remaining
                if all(d not in remaining for d in self.nodes[nid].depends_on
                       if d in self.nodes))
            if not ready:
                break
            levels.append(ready)
            placed.update(ready)
            remaining.difference_update(ready)
        return levels

    # -- ejecucion -------------------------------------------------------
    def run(self, executor: CapabilityExecutor,
            initial: dict[str, Any] | None = None) -> dict[str, Any]:
        """Ejecuta el grafo por niveles topologicos.

        ``executor(capability, payload)`` corre cada capability (en produccion
        envuelve a ``IgrisKernel.execute``). La salida ``.data`` de cada nodo
        queda disponible para los siguientes como ``{{nodo.data.campo}}``. Si un
        nodo falla (``.ok`` falso), se detiene el pipeline de forma segura.
        """
        outputs: dict[str, Any] = dict(initial or {})
        for level in self.topological_levels():
            for nid in level:
                node = self.nodes[nid]
                payload = self._resolve_payload(node.payload, outputs)
                result = executor(node.capability, payload)
                ok = bool(getattr(result, "ok", False))
                data = getattr(result, "data", {}) or {}
                record = {
                    "node": nid, "capability": node.capability,
                    "ok": ok,
                    "message": str(getattr(result, "message", "") or ""),
                }
                outputs[nid] = {"data": data, "ok": ok,
                                "message": record["message"]}
                outputs[f"{nid}.ok"] = ok
                outputs.setdefault("__trace__", [])
                outputs["__trace__"].append(record)
                if not ok:
                    outputs["__failed_node__"] = nid
                    return outputs
        outputs["__completed__"] = True
        return outputs

    @staticmethod
    def _resolve_payload(template: dict[str, Any],
                         outputs: dict[str, Any]) -> dict[str, Any]:
        """Sustituye referencias ``{{ruta}}`` del payload con las salidas."""
        def resolve(value: Any) -> Any:
            if isinstance(value, str):
                return _REF.sub(
                    lambda m: str(_lookup(outputs, m.group(1))), value)
            if isinstance(value, dict):
                return {k: resolve(v) for k, v in value.items()}
            if isinstance(value, list):
                return [resolve(v) for v in value]
            return value
        return {key: resolve(val) for key, val in template.items()}

    # -- persistencia ----------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "nodes": [
                {
                    "id": n.id, "capability": n.capability,
                    "depends_on": list(n.depends_on), "payload": dict(n.payload),
                }
                for n in self.nodes.values()
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CapabilityPipeline":
        pipe = cls(name=str(data.get("name", "pipeline")),
                   description=str(data.get("description", "")))
        for raw in data.get("nodes", []):
            pipe.add_node(PipelineNode(
                id=str(raw["id"]), capability=str(raw["capability"]),
                depends_on=tuple(raw.get("depends_on", ())),
                payload=dict(raw.get("payload", {}))))
        return pipe

    def save(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
                          encoding="utf-8")
        return target

    @classmethod
    def load(cls, path: str | Path) -> "CapabilityPipeline":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def _lookup(data: dict[str, Any], path: str) -> Any:
    """Resuelve ``a.b.c`` sobre el dict de salidas; '' si no existe."""
    current: Any = data
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return ""
    return current