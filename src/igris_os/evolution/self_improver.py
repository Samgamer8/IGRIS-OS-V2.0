from __future__ import annotations
import ast
import re
import shutil
from pathlib import Path
from typing import Any
from igris_os.ai.ollama import OllamaClient, ModelReply
class SelfImprover:
    def __init__(self, src_root: Path, model: str = "qwen2.5-coder:7b") -> None:
        self.src_root = src_root
        self.model = model
        self.ollama = OllamaClient()
    def _fallback_proposal(self, weakness: dict[str, Any]) -> str:
        issue = weakness["issue"]
        if "Long function" in issue:
            return "# Refactor: split function into smaller helpers"
        if "Duplicate" in issue:
            return "# Refactor: extract repeated block into shared function"
        if "Missing error handling" in issue:
            return "try:\n    pass\nexcept Exception:\n    pass"
        if "Hardcoded" in issue:
            return "# Config: move value to config module"
        if "Unused import" in issue:
            return "# Remove unused import"
        return ""
    def scan_weaknesses(self) -> list[dict[str, Any]]:
        weaknesses: list[dict[str, Any]] = []
        for path in self.src_root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            lines = text.splitlines()
            for m in re.finditer(r"^def\s+(\w+)\s*\([^)]*\):", text, re.M):
                start = text[:m.start()].count("\n")
                block = text[m.start():]
                end_m = re.search(r"^def\s+\w+\s*\([^)]*\):|^class\s+\w+", block[1:], re.M)
                end = end_m.start() + 1 if end_m else len(block)
                if (block[:end].count("\n")) > 50:
                    weaknesses.append({"file": str(path), "line": start + 1, "issue": "Long function", "severity": "medium"})
            for m in re.finditer(r"^(?:from\s+\S+\s+import\s+|import\s+)(\w+)", text, re.M):
                mod = m.group(1)
                if not re.search(r"\b" + re.escape(mod) + r"\b", text[m.end():]):
                    weaknesses.append({"file": str(path), "line": text[:m.start()].count("\n") + 1, "issue": "Unused import", "severity": "low"})
            for m in re.finditer(r"=\s*([\"'][^\"']{4,}[\"']|\d{3,})", text):
                weaknesses.append({"file": str(path), "line": text[:m.start()].count("\n") + 1, "issue": "Hardcoded value", "severity": "low"})
            if ("open(" in text or "Path(" in text) and "try:" not in text:
                weaknesses.append({"file": str(path), "line": 1, "issue": "Missing error handling around I/O", "severity": "medium"})
            seen_dup: set[str] = set()
            for i in range(len(lines) - 2):
                block = "\n".join(lines[i:i + 3]).strip()
                if not block or len(block) <= 30 or block in seen_dup:
                    continue
                for j in range(i + 3, len(lines) - 2):
                    other = "\n".join(lines[j:j + 3]).strip()
                    if block == other:
                        seen_dup.add(block)
                        weaknesses.append({"file": str(path), "line": i + 1, "issue": "Duplicate code block", "severity": "medium"})
                        break
        return weaknesses
    def propose_improvement(self, weakness: dict[str, Any]) -> str:
        reply: ModelReply = self.ollama.generate(prompt=f"Fix this Python weakness: {weakness['issue']} in {weakness['file']} at line {weakness['line']}. Return only the replacement code.", model=self.model)
        if reply.ok and reply.text.strip():
            return reply.text.strip()
        return self._fallback_proposal(weakness)
    def apply_improvement(self, file_path: Path, improvement: str) -> bool:
        if not improvement or not file_path.is_file():
            return False
        backup = file_path.with_suffix(file_path.suffix + ".bak")
        shutil.copy2(file_path, backup)
        text = file_path.read_text(encoding="utf-8")
        if "```" in improvement:
            code = re.search(r"```(?:python)?\s*(.*?)```", improvement, re.S)
            replacement = code.group(1).strip() if code else improvement
        else:
            replacement = improvement
        pattern = r"(def\s+\w+\s*\([^)]*\):[\s\S]*?)(?=\ndef\s|\nclass\s|\Z)"
        match = re.search(pattern, text, re.M)
        if match:
            new_text = text[:match.start()] + replacement + text[match.end():]
        else:
            new_text = text + "\n" + replacement
        try:
            ast.parse(new_text)
        except SyntaxError:
            shutil.copy2(backup, file_path)
            return False
        file_path.write_text(new_text, encoding="utf-8")
        return True
    def auto_refactor(self) -> list[dict[str, Any]]:
        weaknesses = self.scan_weaknesses()
        results: list[dict[str, Any]] = []
        for w in weaknesses[:3]:
            fix = self.propose_improvement(w)
            if fix:
                ok = self.apply_improvement(Path(w["file"]), fix)
                results.append({**w, "applied": ok})
        return results
