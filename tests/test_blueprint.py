"""Tests del puente analisis -> reimplementacion (BlueprintBuilder)."""
from __future__ import annotations

from igris_os.files.artifact import ArtifactReport
from igris_os.files.blueprint import BlueprintBuilder
from igris_os.files.repository import RepositoryReport
import ast


def _artifact(**overrides) -> ArtifactReport:
    base = dict(
        path="C:/demo/app.exe", size=1024, sha256="deadbeef", kind="pe",
        kind_description="ejecutable PE", architecture="x86-64", bitness="64",
        timestamp="2024-01-01T00:00:00Z", sections=4, is_dotnet=False,
        packer="", framework="", urls=(), notable_strings=(), zip_entries=(),
        notes=(), limitations=(),
    )
    base.update(overrides)
    return ArtifactReport(**base)


def _project(**overrides) -> RepositoryReport:
    base = dict(
        manifest="C:/demo/app/manifest.json", files=3, bytes_read=1000,
        languages={"python": 3}, symbols=(), imports=(), tests=(),
        matches=(), truncated=False, records=(),
    )
    base.update(overrides)
    return RepositoryReport(**base)


def test_artifact_urls_become_integration_capabilities():
    report = _artifact(urls=["https://api.acme.com/v1", "https://cdn.acme.com"])
    blueprint = BlueprintBuilder().from_artifact(report)
    names = [c["name"] for c in blueprint.proposed_capabilities]
    assert "integrate.api-acme-com" in names
    assert "integrate.cdn-acme-com" in names
    # toda propuesta enlaza a su evidencia real
    assert all(c["motivation"].startswith("[") for c in blueprint.proposed_capabilities)


def test_artifact_framework_and_packer_add_features():
    report = _artifact(framework="Electron", packer="UPX", is_dotnet=True)
    blueprint = BlueprintBuilder().from_artifact(report)
    kinds = {f.kind for f in blueprint.features}
    assert {"runtime", "packer"} <= kinds


def test_artifact_scaffold_compiles():
    report = _artifact(urls=["https://api.acme.com/v1", "https://x.io"])
    blueprint = BlueprintBuilder().from_artifact(report)
    ast.parse(blueprint.scaffold)  # no debe lanzar SyntaxError


def test_project_external_imports_excluded_local_modules():
    report = _project(
        imports=("requests", "PIL", "admin_cache", "admission"),
        symbols=({"name": "Engine", "path": "app/core.py", "line": 3},),
        tests=("tests/test_a.py",),
        records=({"path": "admin_cache/views.py"}, {"path": "app/core.py"},
                 {"path": "admission/api.py"}),
    )
    blueprint = BlueprintBuilder().from_project(report)
    names = [c["name"] for c in blueprint.proposed_capabilities]
    # dependencias externas reales
    assert "integrate.requests" in names
    assert "integrate.pil" in names
    # modulos internos del repo descartados
    assert "integrate.admin-cache" not in names
    assert "integrate.admission" not in names
    # componente del codigo + suite de tests
    assert "reimpl.engine" in names
    assert any(f.kind == "test" for f in blueprint.features)


def test_project_scaffold_compiles_with_windows_paths():
    report = _project(
        imports=("aiohttp",),
        symbols=({"name": "Client", "path": "C:\\demo\\app\\client.py", "line": 5},),
        records=({"path": "C:\\demo\\app\\client.py"},),
    )
    blueprint = BlueprintBuilder().from_project(report)
    # la ruta con barras invertidas no debe romper el scaffold
    ast.parse(blueprint.scaffold)


def test_blueprint_never_claims_to_copy():
    report = _artifact(urls=["https://api.acme.com"])
    blueprint = BlueprintBuilder().from_artifact(report)
    assert any("No copia" in lim for lim in blueprint.limitations)


def test_empty_artifact_scaffold_is_valid():
    blueprint = BlueprintBuilder().from_artifact(_artifact())
    ast.parse(blueprint.scaffold)
    assert blueprint.proposed_capabilities == ()
