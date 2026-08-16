from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Optional


class PythonPreprocessor:
    def __init__(self, *, fix_indentation: bool = True,
                 remove_internal_imports: bool = True,
                 strip_section_markers: bool = True) -> None:
        self.fix_indentation = fix_indentation
        self.remove_internal_imports = remove_internal_imports
        self.strip_section_markers = strip_section_markers

    def process(self, source: str, filename: str = "solution.py") -> str:
        processed = source
        if self.strip_section_markers:
            processed = self._strip_section_markers(processed)
        if self.remove_internal_imports:
            processed = self._remove_internal_imports(processed, filename)
        if self.fix_indentation:
            processed = self._fix_decorator_indentation(processed)
            processed = self._fix_unexpected_unindent(processed)
        return processed

    def _strip_section_markers(self, source: str) -> str:
        lines = source.splitlines()
        cleaned = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("# solution.py"):
                continue
            if stripped.startswith("# main.py"):
                continue
            if stripped.startswith("# test_solution.py"):
                continue
            if stripped.startswith("# tests_calculadora_imc.py"):
                continue
            cleaned.append(line)
        return "\n".join(cleaned)

    def _remove_internal_imports(self, source: str, filename: str) -> str:
        module_name = Path(filename).stem
        lines = source.splitlines()
        cleaned = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("from ") and module_name in stripped:
                continue
            if stripped.startswith("import ") and module_name in stripped:
                continue
            cleaned.append(line)
        return "\n".join(cleaned)

    def _fix_decorator_indentation(self, source: str) -> str:
        lines = source.splitlines()
        fixed = []
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            if stripped.startswith("@") and not line.startswith(" "):
                decorator = stripped
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    next_stripped = next_line.strip()
                    if next_stripped.startswith("def ") and not next_line.startswith(" "):
                        indent = "    "
                        fixed.append(indent + decorator)
                        fixed.append(indent + next_stripped)
                        i += 2
                        continue
                    if next_stripped.startswith("class ") and not next_line.startswith(" "):
                        indent = "    "
                        fixed.append(indent + decorator)
                        fixed.append(indent + next_stripped)
                        i += 2
                        continue
            fixed.append(line)
            i += 1
        return "\n".join(fixed)

    def _fix_unexpected_unindent(self, source: str) -> str:
        for _ in range(3):
            try:
                ast.parse(source)
                return source
            except SyntaxError as exc:
                if "unexpected unindent" not in str(exc):
                    return source
                lines = source.splitlines()
                if exc.lineno is not None and 0 < exc.lineno <= len(lines):
                    bad_line = lines[exc.lineno - 1]
                    if bad_line.strip() == "":
                        lines.pop(exc.lineno - 1)
                    else:
                        lines[exc.lineno - 1] = "    " + bad_line
                    source = "\n".join(lines)
                else:
                    return source
        return source

    def is_valid_python(self, source: str) -> bool:
        try:
            ast.parse(source)
            return True
        except SyntaxError:
            return False
