from __future__ import annotations

import json
from pathlib import Path

import pytest

from igris_os.programming import (
    Language,
    LanguageDevelopmentResult,
    MultiLanguageCoordinator,
    MultiLanguageVerifier,
    UniversalQualityGate,
)
from igris_os.tools.git_ops import GitRepository, MissionGitManager


class FakeLLMClient:
    def __init__(self, responses: dict[str, str]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def generate(self, prompt: str, model: str):
        self.calls.append(prompt)
        lower = prompt.lower()
        if "lenguaje: rust" in lower:
            return type("R", (), {"ok": True, "text": RUST_JSON, "error": ""})()
        if "lenguaje: cpp" in lower:
            return type("R", (), {"ok": True, "text": CPP_JSON, "error": ""})()
        if "lenguaje: java" in lower:
            return type("R", (), {"ok": True, "text": JAVA_JSON, "error": ""})()
        for key, text in self.responses.items():
            if key in prompt:
                return type("R", (), {"ok": True, "text": text, "error": ""})()
        return type("R", (), {"ok": False, "text": "", "error": "no"})()

    def models(self):
        return tuple(self.responses.keys())


RUST_JSON = json.dumps({
    "source": 'fn main() { println!("hello"); }',
    "tests": '#[test] fn test_main() { main(); }',
    "cargo": '[package]\nname = "demo"\nversion = "0.1"',
    "explanation": "Rust minimal",
})
CPP_JSON = json.dumps({
    "source": '#include <iostream>\nint main() { std::cout << "hi"; return 0; }',
    "tests": '#include <catch2/catch.hpp>\nTEST_CASE("ok") { REQUIRE(true); }',
    "cmake": 'cmake_minimum_required(VERSION 3.15)\nproject(demo)',
    "explanation": "C++ minimal",
})
JAVA_JSON = json.dumps({
    "source": 'public class Main { public static void main(String[] args) { System.out.println("hi"); } }',
    "tests": 'import org.junit.jupiter.api.Test;\nimport static org.junit.jupiter.api.Assertions.assertTrue;\nclass MainTest { @Test void ok() { assertTrue(true); } }',
    "pom": '<project><modelVersion>4.0.0</modelVersion><groupId>demo</groupId><artifactId>demo</artifactId><version>0.1</version></project>',
    "explanation": "Java minimal",
})


def test_multilanguage_coordinator_rust(tmp_path: Path):
    client = FakeLLMClient({
        "Genera plan arquitectonico JSON.": '{"plan":"ok","modules":[],"interfaces":[],"risks":[],"acceptance":[]}',
        "Implementa": RUST_JSON,
        "Revisa y puntua": '{"score":0.9,"approved":true,"issues":[]}',
    })
    coordinator = MultiLanguageCoordinator(client, tmp_path)
    result = coordinator.develop("crea funcion rust", language=Language.RUST, confirmed=True)
    assert result.ok
    assert result.language == "rust"


def test_multilanguage_coordinator_cpp(tmp_path: Path):
    client = FakeLLMClient({
        "Genera plan arquitectonico JSON.": '{"plan":"ok","modules":[],"interfaces":[],"risks":[],"acceptance":[]}',
        "Implementa": CPP_JSON,
        "Revisa y puntua": '{"score":0.9,"approved":true,"issues":[]}',
    })
    coordinator = MultiLanguageCoordinator(client, tmp_path)
    result = coordinator.develop("crea cpp", language=Language.CPP, confirmed=True)
    assert result.ok
    assert result.language == "cpp"


def test_multilanguage_coordinator_java(tmp_path: Path):
    client = FakeLLMClient({
        "Genera plan arquitectonico JSON.": '{"plan":"ok","modules":[],"interfaces":[],"risks":[],"acceptance":[]}',
        "Implementa": JAVA_JSON,
        "Revisa y puntua": '{"score":0.9,"approved":true,"issues":[]}',
    })
    coordinator = MultiLanguageCoordinator(client, tmp_path)
    result = coordinator.develop("crea java", language=Language.JAVA, confirmed=True)
    assert result.ok
    assert result.language == "java"


def test_universal_quality_gate_detects_language(tmp_path: Path):
    py = tmp_path / "main.py"
    py.write_text("print(1)\n", encoding="utf-8")
    gate = UniversalQualityGate(tmp_path)
    result = gate.check(py, run_tests=False, run_security=False)
    assert result.ok
    assert result.language == Language.PYTHON


def test_universal_quality_gate_reports_unsupported(tmp_path: Path):
    unknown = tmp_path / "main.xyz"
    unknown.write_text("x", encoding="utf-8")
    gate = UniversalQualityGate(tmp_path)
    result = gate.check(unknown, run_tests=False, run_security=False)
    assert not result.ok


def test_git_repository_initializes(tmp_path: Path):
    repo = GitRepository(tmp_path / "repo", auto_init=True)
    assert (tmp_path / "repo" / ".git").exists()


def test_git_branch_and_commit(tmp_path: Path):
    repo = GitRepository(tmp_path / "repo", auto_init=True)
    (tmp_path / "repo" / "README.md").write_text("hello", encoding="utf-8")
    repo.create_branch("mission/test")
    repo.stage_all()
    commit = repo.commit("first commit")
    assert commit.message == "first commit"
    assert len(commit.hash) == 40


def test_mission_git_manager_workflow(tmp_path: Path):
    mgr = MissionGitManager(tmp_path, "M1")
    start = mgr.start_mission("demo")
    assert start.branch.startswith("mission/")
    repo_path = tmp_path / "repos" / "M1"
    (repo_path / "README.md").write_text("hello", encoding="utf-8")
    cp = mgr.checkpoint("add feature")
    assert cp.message == "[M1] add feature"
    diffs = mgr.diff_since_start()
    assert isinstance(diffs, tuple)
