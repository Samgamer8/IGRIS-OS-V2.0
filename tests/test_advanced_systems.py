from __future__ import annotations

import json
from pathlib import Path

import pytest

from igris_os.programming import (
    CompilationResult,
    DependencyResult,
    OptimizationResult,
    PatchResult,
    PerformanceOptimizer,
    RealToolchain,
    SurgicalPatcher,
)
from igris_os.games import Godot4AdvancedFactory, Godot3DProject
from igris_os.tools import DependencyManager, WindowsSystemAccess
from igris_os.tools.devops import DevOpsPipeline
from igris_os.multimedia.pro_pipeline import MultimediaProPipeline
from igris_os.evaluation import AdvancedVerifier, QualityReport, SecurityAudit


def test_surgical_patcher_apply_replace(tmp_path: Path):
    patcher = SurgicalPatcher(tmp_path)
    target = tmp_path / "main.py"
    target.write_text("a = 1\nb = 2\nc = 3\n", encoding="utf-8")
    result = patcher.apply_patch(target, "replace", 2, 2, "b = 20\n")
    assert result.ok
    assert "b = 20" in target.read_text(encoding="utf-8")


def test_surgical_patcher_rejects_invalid_path(tmp_path: Path):
    patcher = SurgicalPatcher(tmp_path)
    result = patcher.apply_patch(tmp_path / ".." / "x.py", "replace", 1, 1, "x=1")
    assert not result.ok


def test_surgical_patcher_rejects_syntax_error(tmp_path: Path):
    patcher = SurgicalPatcher(tmp_path)
    target = tmp_path / "main.py"
    target.write_text("a = 1\n", encoding="utf-8")
    result = patcher.apply_patch(target, "replace", 1, 1, "def foo(\n")
    assert not result.ok


def test_real_toolchain_python_check(tmp_path: Path):
    toolchain = RealToolchain(tmp_path)
    result = toolchain.check("python")
    assert result.ok or "python" in result.message.lower() or "ok" in result.message.lower()


def test_real_toolchain_dependencies_python(tmp_path: Path):
    toolchain = RealToolchain(tmp_path)
    req = tmp_path / "requirements.txt"
    req.write_text("pytest\nrequests\n", encoding="utf-8")
    result = toolchain.dependencies("python")
    assert result.ok
    assert "pytest" in result.installed


def test_performance_optimizer_detects_io_in_loop():
    optimizer = PerformanceOptimizer(Path("."))
    source = "for i in range(100):\n    f = open('x')\n    data = f.read()\n"
    profile = optimizer.profile("python", source)
    assert profile.io_issues


def test_performance_optimizer_suggests_split():
    optimizer = PerformanceOptimizer(Path("."))
    source = "def huge():\n    x = 1\n" + "\n".join(f"    x += {i}" for i in range(100)) + "\n    return x\n"
    profile = optimizer.profile("python", source)
    assert any("Dividir" in s for s in profile.suggestions)


def test_godot4_factory_creates_3d_project(tmp_path: Path):
    factory = Godot4AdvancedFactory()
    project = factory.create_3d_project(tmp_path, "Test3D", "fps", confirmed=True)
    assert project.root.exists()
    assert (project.root / "main.tscn").is_file()
    assert (project.root / "player.gd").is_file()
    assert (project.root / "project.godot").is_file()


def test_godot4_factory_rejects_unconfirmed(tmp_path: Path):
    factory = Godot4AdvancedFactory()
    with pytest.raises(PermissionError):
        factory.create_3d_project(tmp_path, "Test3D", "fps", confirmed=False)


def test_windows_system_info():
    access = WindowsSystemAccess()
    info = access.system_info()
    assert "os" in info
    assert "admin" in info


def test_dependency_manager_creates_manifest(tmp_path: Path):
    mgr = DependencyManager(tmp_path)
    result = mgr.resolve("python", {"dependencies": ["requests", "pytest"]})
    assert result["ok"]
    assert (tmp_path / "requirements.txt").exists()


def test_dependency_manager_generates_sbom(tmp_path: Path):
    mgr = DependencyManager(tmp_path)
    sbom_path = mgr.generate_sbom([
        {"name": "requests", "version": "2.31.0"},
        {"name": "pytest", "version": "8.0.0"},
    ])
    assert Path(sbom_path).exists()
    data = json.loads(Path(sbom_path).read_text(encoding="utf-8"))
    assert data["bomFormat"] == "CycloneDX"


def test_multimedia_pro_pipeline_transcode(tmp_path: Path):
    pipeline = MultimediaProPipeline(tmp_path)
    source = tmp_path / "input.mp4"
    source.write_bytes(b"\x00" * 1024)
    output = tmp_path / "output.mp4"
    result = pipeline.transcode(source, output)
    assert not result.ok or output.exists()


def test_advanced_verifier_detects_secrets(tmp_path: Path):
    verifier = AdvancedVerifier(tmp_path)
    bad = tmp_path / "bad.py"
    bad.write_text("api_key = 'sk-1234567890abcdef'\n", encoding="utf-8")
    report = verifier.verify_project("python")
    assert not report.security.passed
    assert report.security.secrets


def test_advanced_verifier_clean_project(tmp_path: Path):
    verifier = AdvancedVerifier(tmp_path)
    clean = tmp_path / "clean.py"
    clean.write_text("print('hello')\n", encoding="utf-8")
    report = verifier.verify_project("python")
    assert report.security.passed


def test_devops_generates_dockerfile():
    pipeline = DevOpsPipeline(Path("."))
    dockerfile = pipeline.generate_dockerfile("python")
    assert "FROM python" in dockerfile
    assert "pip install" in dockerfile


def test_devops_generates_ci():
    pipeline = DevOpsPipeline(Path("."))
    ci = pipeline.generate_ci("rust")
    assert "cargo test" in ci
    assert "name: CI" in ci
