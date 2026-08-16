from __future__ import annotations

import ast
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True, slots=True)
class SecurityAudit:
    vulnerabilities: tuple[str, ...] = ()
    secrets: tuple[str, ...] = ()
    unsafe_functions: tuple[str, ...] = ()
    risk_score: float = 0.0
    passed: bool = True


@dataclass(frozen=True, slots=True)
class QualityReport:
    security: SecurityAudit
    performance: dict
    tests: dict
    coverage: float = 0.0
    overall_score: float = 0.0


class AdvancedVerifier:
    SECRET_PATTERNS = [
        r"(?i)api[_-]?key\s*[:=]\s*['\"][^'\"]+['\"]",
        r"(?i)secret\s*[:=]\s*['\"][^'\"]+['\"]",
        r"(?i)password\s*[:=]\s*['\"][^'\"]+['\"]",
        r"(?i)token\s*[:=]\s*['\"][^'\"]+['\"]",
        r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----",
        r"sk-[a-zA-Z0-9]{20,}",
    ]

    UNSAFE_PYTHON = {"eval", "exec", "compile", "__import__",
                     "os.system", "subprocess.call", "pickle.loads"}

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def verify_project(self, language: str) -> QualityReport:
        security = self._audit_security(language)
        performance = self._profile_performance(language)
        tests = self._run_tests(language)
        coverage = self._estimate_coverage(language)
        overall = self._score(security, performance, tests, coverage)
        return QualityReport(security, performance, tests, coverage, overall)

    def self_heal(self, language: str, report: QualityReport) -> list[str]:
        actions = []
        if not report.security.passed:
            actions.append("security_fix_required")
        if report.tests.get("failed", 0) > 0:
            actions.append("test_repair_required")
        if report.performance.get("hot_paths"):
            actions.append("optimization_required")
        return actions

    def _audit_security(self, language: str) -> SecurityAudit:
        vulnerabilities = []
        secrets = []
        unsafe = []
        if language == "python":
            for path in self.root.rglob("*.py"):
                if not path.is_file():
                    continue
                try:
                    source = path.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                for pattern in self.SECRET_PATTERNS:
                    matches = re.findall(pattern, source)
                    if matches:
                        secrets.extend([f"{path.name}:{m[:20]}..." for m in matches[:3]])
                try:
                    tree = ast.parse(source)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Call):
                            func = node.func
                            if isinstance(func, ast.Name) and func.id in self.UNSAFE_PYTHON:
                                unsafe.append(f"{path.name}:{node.lineno}:{func.id}")
                            if isinstance(func, ast.Attribute):
                                full = f"{getattr(func.value, 'id', '')}.{func.attr}"
                                if full in self.UNSAFE_PYTHON:
                                    unsafe.append(f"{path.name}:{node.lineno}:{full}")
                except SyntaxError:
                    pass
        risk = (len(secrets) * 0.5 + len(unsafe) * 0.3 + len(vulnerabilities) * 0.2)
        return SecurityAudit(
            tuple(vulnerabilities), tuple(secrets), tuple(unsafe),
            min(risk, 1.0), risk < 0.3,
        )

    def _profile_performance(self, language: str) -> dict:
        return {"hot_paths": [], "memory_issues": [], "status": "ok"}

    def _run_tests(self, language: str) -> dict:
        return {"total": 0, "passed": 0, "failed": 0, "status": "skipped"}

    def _estimate_coverage(self, language: str) -> float:
        return 0.0

    @staticmethod
    def _score(security: SecurityAudit, performance: dict,
               tests: dict, coverage: float) -> float:
        score = 1.0
        score -= security.risk_score * 0.4
        score -= (1.0 - security.passed) * 0.2
        score -= max(0.0, 0.1 - coverage) * 0.2
        return max(0.0, min(1.0, score))
