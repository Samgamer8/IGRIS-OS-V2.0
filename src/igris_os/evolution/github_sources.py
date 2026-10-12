"""Read a small, auditable Markdown snapshot from a public GitHub repository."""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen


MAX_FILES = 36
MAX_FILE_CHARS = 100_000
MAX_TOTAL_CHARS = 60_000
CHUNK_LINES = 70


@dataclass(frozen=True, slots=True)
class RepositoryFile:
    path: str
    text: str


@dataclass(frozen=True, slots=True)
class EvidenceChunk:
    evidence_id: str
    source: str
    path: str
    line_start: int
    line_end: int
    text: str


@dataclass(frozen=True, slots=True)
class RepositorySnapshot:
    url: str
    owner: str
    name: str
    branch: str
    commit: str
    files: tuple[RepositoryFile, ...]
    evidence: tuple[EvidenceChunk, ...]
    available_file_count: int
    omitted_file_count: int
    truncated_files: tuple[str, ...]


def _github_repo_parts(url: str) -> tuple[str, str, str | None]:
    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or parsed.hostname not in {"github.com", "www.github.com"}:
        raise ValueError("Usa una URL HTTPS de un repositorio público github.com/propietario/repositorio.")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        raise ValueError("La URL debe señalar a un repositorio, no solo a github.com.")
    owner, name = parts[0], parts[1].removesuffix(".git")
    branch = None
    if len(parts) >= 4 and parts[2] in {"tree", "blob"}:
        branch = parts[3]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", owner) or not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
        raise ValueError("La URL contiene un propietario o nombre de repositorio no válido.")
    return owner, name, branch


def _get_json(url: str) -> dict:
    request = Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "IGRIS-Repository-Study/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read(4_000_000).decode("utf-8"))


def _get_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": "IGRIS-Repository-Study/1.0"})
    with urlopen(request, timeout=20) as response:
        raw = response.read(MAX_FILE_CHARS * 4 + 1)
    if len(raw) > MAX_FILE_CHARS * 4:
        raw = raw[:MAX_FILE_CHARS * 4]
    return raw.decode("utf-8", errors="replace")[:MAX_FILE_CHARS]


def _is_study_file(path: str) -> bool:
    lower = path.lower()
    if not lower.endswith((".md", ".mdx", ".prompt.md", ".instructions.md", ".agent.md")):
        return False
    return (path.count("/") <= 1 or lower.startswith(("docs/", "_examples/", ".github/", "skills/")))


def _rank_path(path: str) -> tuple[int, str]:
    lower = path.lower()
    if lower == "readme.md":
        return 0, lower
    if lower in {"index.md", "about.md", "contributing.md"}:
        return 1, lower
    if lower.startswith("docs/"):
        return 2, lower
    if lower.startswith(("_examples/", ".github/", "skills/")):
        return 3, lower
    return 4, lower


def _make_evidence(files: tuple[RepositoryFile, ...], source_id: str) -> tuple[EvidenceChunk, ...]:
    chunks: list[EvidenceChunk] = []
    for file in files:
        lines = file.text.splitlines()
        for start in range(0, len(lines), CHUNK_LINES):
            body = "\n".join(lines[start:start + CHUNK_LINES]).strip()
            if body:
                chunks.append(EvidenceChunk(
                    f"{source_id}-R{len(chunks) + 1:03d}", source_id, file.path, start + 1,
                    min(start + CHUNK_LINES, len(lines)), body))
    return tuple(chunks)


def read_github_repository(url: str, *, source_id: str = "S1") -> RepositorySnapshot:
    """Fetch a bounded set of repository documents without cloning or executing code."""
    owner, name, branch_from_url = _github_repo_parts(url)
    base = f"https://api.github.com/repos/{quote(owner)}/{quote(name)}"
    repository = _get_json(base)
    branch = branch_from_url or str(repository.get("default_branch") or "main")
    encoded_branch = quote(branch, safe="")
    tree = _get_json(f"{base}/git/trees/{encoded_branch}?recursive=1")
    if tree.get("truncated"):
        raise RuntimeError("GitHub truncó el índice del repositorio; no puedo asegurar una lectura completa.")
    available_paths = sorted(
        (str(item.get("path", "")) for item in tree.get("tree", ())
         if item.get("type") == "blob" and _is_study_file(str(item.get("path", "")))),
        key=_rank_path,
    )
    paths = available_paths[:MAX_FILES]
    files: list[RepositoryFile] = []
    truncated_files: list[str] = []
    omitted_count = max(0, len(available_paths) - len(paths))
    total = 0
    for path_index, path in enumerate(paths):
        raw_url = f"https://raw.githubusercontent.com/{quote(owner)}/{quote(name)}/{encoded_branch}/{quote(path, safe='/')}"
        try:
            text = _get_text(raw_url)
        except Exception:
            omitted_count += 1
            continue
        remaining = MAX_TOTAL_CHARS - total
        if remaining <= 0:
            omitted_count += len(paths) - path_index
            break
        file_was_truncated = len(text) >= MAX_FILE_CHARS
        if file_was_truncated:
            truncated_files.append(path)
        total_limit_hit = len(text) > remaining
        if total_limit_hit:
            text = text[:remaining]
            if path not in truncated_files:
                truncated_files.append(path)
            omitted_count += len(paths) - path_index - 1
        if text.strip():
            files.append(RepositoryFile(path, text))
            total += len(text)
        if total_limit_hit:
            break
    if not files:
        raise RuntimeError("No se pudieron leer documentos Markdown de ese repositorio público.")
    commit = str(tree.get("sha") or "desconocido")
    file_tuple = tuple(files)
    return RepositorySnapshot(
        url=url, owner=owner, name=name, branch=branch, commit=commit,
        files=file_tuple, evidence=_make_evidence(file_tuple, source_id),
        available_file_count=len(available_paths),
        omitted_file_count=omitted_count,
        truncated_files=tuple(truncated_files))


def read_github_repositories(urls: list[str]) -> tuple[RepositorySnapshot, ...]:
    """Read multiple repositories independently and assign unambiguous citations."""
    cleaned = [url.strip() for url in urls if url and url.strip()]
    if not cleaned:
        raise ValueError("Añade al menos una URL de GitHub.")
    if len(cleaned) > 4:
        raise ValueError("La revisión inicial admite hasta cuatro repositorios.")
    return tuple(read_github_repository(url, source_id=f"S{index}")
                 for index, url in enumerate(cleaned, start=1))
