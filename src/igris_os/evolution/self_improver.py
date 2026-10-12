from __future__ import annotations

import ast
import re
import uuid
from pathlib import Path
from typing import Any, Callable

from igris_os.ai.ollama import ModelReply, OllamaClient
from igris_os.evolution.evolution_core import EvolutionCore, EvolutionPatch


class SelfImprover:
    """Suggest source improvements; apply only confirmed, externally verified patches."""

    PROTECTED_SUFFIXES = {
        ("igris_os", "ui", "cinematic.py"),
        ("igris_os", "ui", "panel_presentation.py"),
        ("ui", "cinematic.py"),
        ("ui", "panel_presentation.py"),
    }

    def __init__(self, src_root: Path, model: str = "qwen2.5-coder:7b",
                 client: Any | None = None) -> None:
        self.src_root = Path(src_root).resolve()
        self.model = model
        self.ollama = client or OllamaClient()

    @staticmethod
    def _function_at(source: str, line: int) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return None
        functions = [node for node in ast.walk(tree)
                     if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                     and node.lineno <= line <= (node.end_lineno or node.lineno)]
        return min(functions,
                   key=lambda node: (node.end_lineno or node.lineno) - node.lineno
                   ) if functions else None

    @staticmethod
    def _function_source(source: str, function: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        return "\n".join(source.splitlines()[function.lineno - 1:function.end_lineno])

    def _fallback_proposal(self, weakness: dict[str, Any]) -> str:
        """Never fabricate replacement code when the model is unavailable."""
        return ""

    def scan_weaknesses(self) -> list[dict[str, Any]]:
        weaknesses: list[dict[str, Any]] = []
        for path in self.src_root.rglob("*.py"):
            if any(part in {".git", ".venv", "venv", "__pycache__", ".evolution_backups"}
                   for part in path.parts):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            lines = text.splitlines()
            for match in re.finditer(r"^def\s+(\w+)\s*\([^)]*\):", text, re.M):
                start = text[:match.start()].count("\n")
                block = text[match.start():]
                end_match = re.search(r"^def\s+\w+\s*\([^)]*\):|^class\s+\w+", block[1:], re.M)
                end = end_match.start() + 1 if end_match else len(block)
                if block[:end].count("\n") > 50:
                    weaknesses.append({"file": str(path), "line": start + 1,
                                       "function": match.group(1),
                                       "issue": "Long function", "severity": "medium"})
            for match in re.finditer(r"^(?:from\s+\S+\s+import\s+|import\s+)(\w+)", text, re.M):
                name = match.group(1)
                if not re.search(r"\b" + re.escape(name) + r"\b", text[match.end():]):
                    weaknesses.append({"file": str(path),
                                       "line": text[:match.start()].count("\n") + 1,
                                       "issue": "Unused import", "severity": "low"})
            for match in re.finditer(r"=\s*([\"'][^\"']{4,}[\"']|\d{3,})", text):
                weaknesses.append({"file": str(path),
                                   "line": text[:match.start()].count("\n") + 1,
                                   "issue": "Hardcoded value", "severity": "low"})
            if ("open(" in text or "Path(" in text) and "try:" not in text:
                weaknesses.append({"file": str(path), "line": 1,
                                   "issue": "Missing error handling around I/O",
                                   "severity": "medium"})
            seen_dup: set[str] = set()
            for i in range(len(lines) - 2):
                block = "\n".join(lines[i:i + 3]).strip()
                if not block or len(block) <= 30 or block in seen_dup:
                    continue
                for j in range(i + 3, len(lines) - 2):
                    if block == "\n".join(lines[j:j + 3]).strip():
                        seen_dup.add(block)
                        weaknesses.append({"file": str(path), "line": i + 1,
                                           "issue": "Duplicate code block",
                                           "severity": "medium"})
                        break
        return weaknesses

    def propose_improvement(self, weakness: dict[str, Any]) -> str:
        try:
            target = Path(weakness["file"]).resolve()
            if not target.is_relative_to(self.src_root):
                return ""
            source = target.read_text(encoding="utf-8")
            function = self._function_at(source, int(weakness["line"]))
            if function is None:
                return ""
            original = self._function_source(source, function)
        except (KeyError, OSError, UnicodeError, TypeError, ValueError):
            return ""
        prompt = (
            "Propón una mejora de mantenimiento basada en el problema indicado. "
            "Devuelve únicamente la función Python completa de reemplazo, sin markdown. "
            "Conserva exactamente el nombre y la firma; no inventes requisitos ni cambies APIs. "
            "Si no puedes justificar una corrección, devuelve una cadena vacía.\n\n"
            f"Problema: {weakness['issue']}\nArchivo: {target.name}, línea {weakness['line']}\n"
            f"Función actual:\n{original}"
        )
        reply: ModelReply = self.ollama.generate(prompt=prompt, model=self.model)
        if not reply.ok or not reply.text.strip():
            return self._fallback_proposal(weakness)
        replacement = reply.text.strip()
        fenced = re.fullmatch(r"```(?:python)?\s*(.*?)\s*```", replacement,
                              flags=re.IGNORECASE | re.DOTALL)
        return (fenced.group(1).strip() if fenced else replacement)

    def apply_improvement(self, file_path: Path, improvement: str, *, line: int,
                          confirmed: bool = False,
                          validator: Callable[[Path], bool] | None = None) -> bool:
        """Replace one function only after explicit confirmation and full-project verification."""
        if confirmed is not True or not callable(validator) or not improvement.strip():
            return False
        try:
            requested = Path(file_path)
            if requested.is_symlink():
                return False
            target = requested.resolve()
            if not target.is_relative_to(self.src_root) or not target.is_file():
                return False
            relative_parts = tuple(part.casefold() for part in target.relative_to(self.src_root).parts)
            if any(relative_parts[-len(suffix):] == suffix for suffix in self.PROTECTED_SUFFIXES):
                return False
            original = target.read_text(encoding="utf-8")
            function = self._function_at(original, int(line))
            if function is None:
                return False
            old_function = self._function_source(original, function)
            replacement = improvement.strip()
            candidate_function = ast.parse(replacement).body
            if len(candidate_function) != 1 or not isinstance(
                    candidate_function[0], (ast.FunctionDef, ast.AsyncFunctionDef)):
                return False
            new_function = candidate_function[0]
            if (type(new_function) is not type(function)
                    or new_function.name != function.name
                    or ast.dump(new_function.args) != ast.dump(function.args)):
                return False
            source_lines = original.splitlines(keepends=True)
            start, end = function.lineno - 1, function.end_lineno
            candidate_lines = source_lines[:start] + [replacement.rstrip() + "\n"] + source_lines[end:]
            candidate = "".join(candidate_lines)
            ast.parse(candidate)
            patch = EvolutionPatch(target, original, candidate,
                                   str("verified proposal"), "self-improver-" + uuid.uuid4().hex)
            result = EvolutionCore(self.src_root).evolve([patch], verifier=validator)
            return result.ok
        except (OSError, SyntaxError, UnicodeError, ValueError, TypeError):
            return False

    def auto_refactor(self, *, confirmed: bool = False,
                      validator: Callable[[Path], bool] | None = None) -> list[dict[str, Any]]:
        """Collect proposals; writing is opt-in and gated by an external verifier."""
        results: list[dict[str, Any]] = []
        for weakness in self.scan_weaknesses()[:3]:
            proposal = self.propose_improvement(weakness)
            applied = False
            if proposal and confirmed is True and callable(validator):
                applied = self.apply_improvement(
                    Path(weakness["file"]), proposal, line=weakness["line"],
                    confirmed=True, validator=validator)
            status = ("verified and applied" if applied else
                      "proposal only; explicit confirmation and verifier required"
                      if proposal else "no evidence-based proposal available")
            results.append({**weakness, "proposal": proposal,
                            "applied": applied, "status": status})
        return results
