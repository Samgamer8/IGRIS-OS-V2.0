import ast
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from igris_os.tools import safe_output

EXCLUDED = {".git", ".venv", "venv", "node_modules", "build", "dist",
            "runtime", "__pycache__", ".pytest_cache", "target"}
LANGUAGES = {".py": "python", ".js": "javascript", ".ts": "typescript",
             ".tsx": "typescript", ".rs": "rust", ".cpp": "cpp",
             ".cc": "cpp", ".h": "cpp", ".java": "java", ".cs": "csharp",
             ".gd": "gdscript", ".json": "json", ".toml": "toml",
             ".yaml": "yaml", ".yml": "yaml", ".md": "markdown"}


@dataclass(frozen=True, slots=True)
class RepositoryReport:
    files: int
    bytes_read: int
    languages: dict[str, int]
    symbols: tuple[dict, ...]
    imports: tuple[str, ...]
    tests: tuple[str, ...]
    matches: tuple[dict, ...]
    manifest: str
    truncated: bool


class RepositoryAnalyzer:
    def __init__(self, workspace: Path, *, max_files: int = 2000,
                 max_file_bytes: int = 512_000,
                 max_total_bytes: int = 32 * 1024 * 1024) -> None:
        self.workspace = workspace.resolve()
        self.max_files = max_files
        self.max_file_bytes = max_file_bytes
        self.max_total_bytes = max_total_bytes

    def analyze(self, root: Path, query: str = "") -> RepositoryReport:
        root = root.resolve()
        if not root.is_dir() or root.is_symlink():
            raise ValueError("Repositorio no valido")
        records, symbols, imports, tests = [], [], set(), []
        languages, total, truncated = Counter(), 0, False
        for path in sorted(root.rglob("*")):
            if len(records) >= self.max_files:
                truncated = True
                break
            if not path.is_file() or path.is_symlink():
                continue
            relative = path.relative_to(root)
            if any(part in EXCLUDED for part in relative.parts):
                continue
            language, size = LANGUAGES.get(path.suffix.casefold()), path.stat().st_size
            if not language or size > self.max_file_bytes:
                continue
            if total + size > self.max_total_bytes:
                truncated = True
                break
            text, rel = path.read_text(encoding="utf-8", errors="replace"), relative.as_posix()
            total += size
            languages[language] += 1
            if self._is_test(rel):
                tests.append(rel)
            found, dependencies = self._structure(language, text, rel)
            symbols.extend(found)
            imports.update(dependencies)
            records.append({"path": rel, "language": language, "size": size,
                            "text": text[:20_000],
                            "symbols": [item["name"] for item in found]})
        matches = self._search(records, query)
        document = {"schema": 1, "root": str(root), "files": len(records),
                    "bytes_read": total, "languages": dict(languages),
                    "symbols": symbols[:5000], "imports": sorted(imports)[:2000],
                    "tests": tests[:2000], "truncated": truncated,
                    "records": [{k: v for k, v in item.items() if k != "text"}
                                for item in records]}
        manifest = safe_output(self.workspace, "output/repository_map.json")
        manifest.write_text(json.dumps(document, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        return RepositoryReport(len(records), total, dict(languages),
                                tuple(symbols[:5000]), tuple(sorted(imports)[:2000]),
                                tuple(tests[:2000]), tuple(matches), str(manifest), truncated)

    @staticmethod
    def _is_test(path: str) -> bool:
        low = path.casefold()
        return ("/test" in "/" + low or low.startswith("test") or
                low.endswith((".spec.js", ".test.js", ".spec.ts", ".test.ts")))

    @staticmethod
    def _structure(language: str, text: str, path: str):
        symbols, imports = [], set()
        if language == "python":
            try:
                tree = ast.parse(text)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                         ast.ClassDef)):
                        symbols.append({"name": node.name, "path": path,
                                        "line": node.lineno,
                                        "kind": type(node).__name__})
                    elif isinstance(node, ast.Import):
                        imports.update(alias.name for alias in node.names)
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        imports.add(node.module)
            except SyntaxError:
                pass
        else:
            pattern = re.compile(r"(?m)^\s*(?:class|function|fn|interface|struct|enum)\s+([A-Za-z_$][\w$]*)")
            for match in pattern.finditer(text):
                symbols.append({"name": match.group(1), "path": path,
                                "line": text.count("\n", 0, match.start()) + 1,
                                "kind": "symbol"})
        return symbols, imports

    @staticmethod
    def _search(records: list[dict], query: str) -> list[dict]:
        ignored = {"este", "esta", "analiza", "proyecto", "repositorio"}
        terms = {word for word in re.findall(r"\w{3,}", query.casefold())
                 if word not in ignored}
        scored = []
        for item in records:
            text = (item["path"] + " " + " ".join(item["symbols"]) +
                    " " + item["text"]).casefold()
            score = sum(text.count(term) for term in terms)
            if score:
                scored.append({"path": item["path"], "score": score,
                               "language": item["language"],
                               "excerpt": item["text"][:600]})
        return sorted(scored,
                      key=lambda item: (-item["score"], item["path"]))[:12]
