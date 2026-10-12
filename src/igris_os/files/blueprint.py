"""Puente entre el analisis (reverse.inspect / reverse.project) y la
implementacion: convierte HECHOS observados en un blueprint de capacidades
propias de IGRIS OS.

Veracidad: cada caracteristica propuesta enlaza a la evidencia real que la
motiva (una URL, un import, un simbolo, un framework). NO copia ni clona
codigo del objetivo: propone capacidades ORIGINALES inspiradas en lo observado
y genera un esqueleto (scaffold) con stubs que hay que completar. Pensado para
software propio o autorizado (investigacion, interoperabilidad).
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import PurePosixPath

from .artifact import ArtifactReport
from .repository import RepositoryReport


def _fn_name(capability: str) -> str:
    """Convierte 'integrate.admin-cache' en un identificador Python valido."""
    return re.sub(r"[^0-9a-zA-Z_]", "_", capability)


def _py_str(text: str) -> str:
    """Escapa un texto para embeberlo de forma segura en codigo Python.

    Evita que una ruta de Windows (``C:\\Users\\...``) rompa el scaffold con
    secuencias de escape invalidas (\\U, \\x...)."""
    return str(text).replace("\\", "\\\\").replace('"""', "'''")

# Modulos de la stdlib, para distinguir dependencias externas de un proyecto.
try:
    from sys import stdlib_module_names as _STDLIB
except ImportError:  # Python < 3.10
    _STDLIB = frozenset({
        "os", "sys", "re", "json", "ast", "struct", "zipfile", "hashlib",
        "pathlib", "datetime", "typing", "dataclasses", "collections",
        "functools", "itertools", "subprocess", "threading", "enum", "math",
        "time", "random", "io", "abc", "copy", "logging", "argparse", "uuid",
    })


@dataclass(frozen=True, slots=True)
class BlueprintFeature:
    """Una caracteristica observada, con la evidencia que la respalda."""

    name: str
    kind: str          # endpoint | runtime | packer | dependency | symbol | test
    evidence: str      # el hecho real (URL, import, path:linea, framework)
    proposal: str      # que capacidad propia de IGRIS construiria


@dataclass(frozen=True, slots=True)
class BlueprintReport:
    """Blueprint de reimplementacion: caracteristicas, capabilities y scaffold."""

    target: str
    target_kind: str
    features: tuple[BlueprintFeature, ...]
    proposed_capabilities: tuple[dict, ...]
    scaffold: str
    limitations: tuple[str, ...]


def _slug(text: str, *, fallback: str = "item") -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    return cleaned[:40] or fallback


class BlueprintBuilder:
    """Convierte un informe de analisis en un blueprint de reimplementacion."""

    MAX_FEATURES = 12
    MAX_CAPABILITIES = 8

    # -- artefactos (binarios / paquetes) --------------------------------
    def from_artifact(self, report: ArtifactReport) -> BlueprintReport:
        features: list[BlueprintFeature] = []
        for url in report.urls:
            features.append(BlueprintFeature(
                name="Integracion HTTP", kind="endpoint", evidence=url,
                proposal=f"Cliente propio para consultar {url}"))
            if len(features) >= self.MAX_FEATURES:
                break
        if report.framework:
            features.append(BlueprintFeature(
                name="Runtime objetivo", kind="runtime",
                evidence=report.framework,
                proposal=f"Soportar el formato {report.framework}"))
        if report.packer:
            features.append(BlueprintFeature(
                name="Empaquetado", kind="packer", evidence=report.packer,
                proposal=f"Leer/extraer artefactos {report.packer}"))
        if report.is_dotnet:
            features.append(BlueprintFeature(
                name="Componente gestionado", kind="runtime",
                evidence="Cabecera CLI (.NET)",
                proposal="Interoperar con ensamblados .NET"))
        return self._assemble(report.path, "artifact", features,
                              list(report.limitations))

    # -- proyectos (codigo fuente) ---------------------------------------
    def from_project(self, report: RepositoryReport) -> BlueprintReport:
        features: list[BlueprintFeature] = []
        local = self._local_modules(report)
        external = sorted(
            imp for imp in report.imports
            if imp.split(".")[0] not in _STDLIB
            and imp.split(".")[0] not in local)
        for imp in external[: self.MAX_FEATURES]:
            features.append(BlueprintFeature(
                name=f"Dependencia: {imp}", kind="dependency",
                evidence=f"import {imp}",
                proposal=f"Integrar o sustituir la dependencia {imp}"))
            if len(features) >= self.MAX_FEATURES:
                break
        room = self.MAX_FEATURES - len(features)
        for sym in report.symbols[:room]:
            features.append(BlueprintFeature(
                name=f"Componente: {sym['name']}", kind="symbol",
                evidence=f"{sym['path']}:{sym['line']}",
                proposal=f"Reimplementar el componente {sym['name']}"))
        if report.tests:
            features.append(BlueprintFeature(
                name="Suite de pruebas", kind="test",
                evidence=f"{len(report.tests)} tests detectados",
                proposal="Replicar la cobertura de pruebas en IGRIS"))
        return self._assemble(
            report.manifest or "proyecto", "project", features,
            ["El scaffold es un esqueleto: completa cada TODO antes de usarlo."])

    @staticmethod
    def _local_modules(report: RepositoryReport) -> set[str]:
        """Nombres de paquete/modulo propios del repo (descartados de deps).

        Recoge cada componente de directorio y el stem de cada fichero, para
        no confundir un modulo interno (p. ej. ``admin_cache``) con una
        dependencia externa real.
        """
        names: set[str] = set()
        for record in report.records:
            raw = str(record.get("path", "")).replace("\\", "/")
            pure = PurePosixPath(raw)
            for part in pure.parts:
                if part and part not in (".", ".."):
                    names.add(part)
            if pure.stem:
                names.add(pure.stem)
        return names

    # -- comun -----------------------------------------------------------
    def _assemble(self, target: str, target_kind: str,
                  features: list[BlueprintFeature],
                  limitations: list[str]) -> BlueprintReport:
        features = tuple(features[: self.MAX_FEATURES])
        capabilities = self._capabilities(features)
        scaffold = self._scaffold(target, capabilities)
        return BlueprintReport(
            target=str(target), target_kind=target_kind, features=features,
            proposed_capabilities=capabilities, scaffold=scaffold,
            limitations=tuple(limitations) + (
                "No copia ni desensambla codigo: propone capacidades propias "
                "inspiradas en lo observado.",))

    def _capabilities(self, features: tuple[BlueprintFeature, ...]
                      ) -> tuple[dict, ...]:
        caps: list[dict] = []
        seen: set[str] = set()
        for feature in features:
            name = self._capability_name(feature)
            if not name or name in seen:
                continue
            seen.add(name)
            caps.append({
                "name": name,
                "description": feature.proposal,
                "risk": "read_only",
                "motivation": f"[{feature.kind}] {feature.evidence}",
            })
            if len(caps) >= self.MAX_CAPABILITIES:
                break
        return tuple(caps)

    @staticmethod
    def _capability_name(feature: BlueprintFeature) -> str:
        if feature.kind == "endpoint":
            match = re.search(r"https?://([^/]+)", feature.evidence)
            host = _slug(match.group(1) if match else "http")
            return f"integrate.{host}"
        if feature.kind == "dependency":
            return f"integrate.{_slug(feature.name.split(':', 1)[-1])}"
        if feature.kind == "symbol":
            return f"reimpl.{_slug(feature.name.split(':', 1)[-1])}"
        if feature.kind == "runtime":
            return f"support.{_slug(feature.name)}"
        if feature.kind == "packer":
            return f"unpack.{_slug(feature.name)}"
        return ""

    @staticmethod
    def _scaffold(target: str, capabilities: tuple[dict, ...]) -> str:
        target = _py_str(target)
        lines = [
            '"""Blueprint de reimplementacion generado por IGRIS OS.',
            "",
            f"Objetivo: {target}",
            "Esqueleto con stubs: completa cada TODO. No copia codigo del",
            "objetivo; propone capacidades propias inspiradas en lo observado.",
            '"""',
            "from __future__ import annotations",
            "",
            "from igris_os.domain import ActionRisk, CapabilitySpec, ExecutionResult",
            "",
            "",
            "def register_blueprint_capabilities(registry) -> None:",
        ]
        if not capabilities:
            lines.append("    # No se detectaron caracteristicas accionables.")
            lines.append("    return")
        for cap in capabilities:
            fn = _fn_name(cap["name"])
            desc = _py_str(cap["description"])
            lines += [
                "    registry.register(",
                f'        CapabilitySpec("{cap["name"]}", "{desc}",',
                "                       ActionRisk.READ_ONLY),",
                f"        _{fn})"
            ]
        lines += ["", ""]
        for cap in capabilities:
            fn = _fn_name(cap["name"])
            desc = _py_str(cap["description"])
            motivation = _py_str(cap["motivation"])
            lines += [
                f"def _{fn}(payload):",
                f'    """{desc}',
                "",
                f"    Motivacion (evidencia real): {motivation}",
                '    """',
                '    raise NotImplementedError("TODO: completar implementacion propia")',
                "", "",
            ]
        return "\n".join(lines)
