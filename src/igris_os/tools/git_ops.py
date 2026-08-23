from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


@dataclasses.dataclass(frozen=True, slots=True)
class GitCommit:
    hash: str
    short_hash: str
    message: str
    author: str
    timestamp: str
    branch: str


@dataclasses.dataclass(frozen=True, slots=True)
class GitDiff:
    file: str
    additions: int
    deletions: int
    patch: str


@dataclasses.dataclass(frozen=True, slots=True)
class GitBranchInfo:
    name: str
    current: bool
    last_commit: str


class GitOperationError(Exception):
    pass


class GitRepository:
    def __init__(self, root: str | Path, *, auto_init: bool = False) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        if auto_init and not (self.root / ".git").exists():
            self._run("init", "-b", "main")
            self._run("config", "user.name", "IGRIS")
            self._run("config", "user.email", "igris@local")
            self._run("config", "commit.gpgsign", "false")

    def create_branch(self, name: str, *, checkout: bool = True) -> str:
        safe = _safe_ref(name)
        self._run("checkout", "-b", safe)
        return safe

    def current_branch(self) -> str:
        try:
            out = self._run("symbolic-ref", "HEAD").strip()
            if out.startswith("refs/heads/"):
                return out[len("refs/heads/"):]
            return out
        except GitOperationError:
            try:
                out = self._run("rev-parse", "--abbrev-ref", "HEAD").strip()
                return out if out != "HEAD" else "(no commits)"
            except GitOperationError:
                return "(no commits)"

    def stage_all(self) -> None:
        self._run("add", ".")

    def commit(self, message: str, *, allow_empty: bool = False) -> GitCommit:
        args = ["commit", "-m", message]
        if allow_empty:
            args.append("--allow-empty")
        self._run(*args)
        sha = self._run("rev-parse", "HEAD").strip()
        short = sha[:12]
        out = self._run("log", "-1", "--format=%H|%h|%s|%an|%aI")
        parts = out.strip().split("|", 4)
        if len(parts) != 5:
            raise GitOperationError("Formato de log inesperado")
        return GitCommit(parts[0], parts[1], parts[2], parts[3], parts[4],
                         self.current_branch())

    def diff_since(self, ref: str) -> tuple[GitDiff, ...]:
        out = self._run("diff", "--stat", ref, "--")
        lines = [line.strip() for line in out.splitlines() if line.strip()]
        diffs = []
        for line in lines:
            if " | " not in line:
                continue
            file_part, stats = line.rsplit(" | ", 1)
            additions, deletions = 0, 0
            if "," in stats:
                ins, outs = stats.split(",", 1)
                additions = int(ins.replace("+", "").strip() or 0)
                deletions = int(outs.replace("-", "").strip() or 0)
            elif "+" in stats:
                additions = int(stats.replace("+", "").strip() or 0)
            elif "-" in stats:
                deletions = int(stats.replace("-", "").strip() or 0)
            patch = self._run("diff", ref, "--", file_part)
            diffs.append(GitDiff(file_part, additions, deletions, patch.strip()))
        return tuple(diffs)

    def rollback_to(self, ref: str) -> None:
        self._run("reset", "--hard", ref)

    def list_branches(self) -> tuple[GitBranchInfo, ...]:
        current = self.current_branch()
        out = self._run("branch", "--format=%(refname:short)|%(objectname:short)")
        branches = []
        for line in out.splitlines():
            if not line.strip():
                continue
            name, commit = line.strip().split("|", 1)
            branches.append(GitBranchInfo(name, name == current, commit))
        return tuple(branches)

    def blame(self, path: Path) -> str:
        return self._run("blame", "--line-porcelain", str(path))

    def status(self) -> str:
        return self._run("status", "--short")

    def _run(self, *args: str) -> str:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=self.root,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout
        except subprocess.CalledProcessError as exc:
            raise GitOperationError(
                f"git {' '.join(args)} fallo: {exc.stderr}"
            ) from exc


def _safe_ref(name: str) -> str:
    ref = "".join(ch if ch.isalnum() or ch in "-_/" else "_" for ch in name)
    ref = ref.strip("-_/") or "mission"
    if not ref.startswith("mission/"):
        ref = "mission/" + ref
    return ref[:80]


@dataclass(frozen=True, slots=True)
class MissionGitResult:
    branch: str
    commits: tuple[GitCommit, ...]
    diffs: tuple[GitDiff, ...]
    message: str


class MissionGitManager:
    def __init__(self, workspace: str | Path, mission_id: str) -> None:
        self.repo = GitRepository(Path(workspace) / "repos" / mission_id, auto_init=True)
        self.mission_id = mission_id

    def start_mission(self, description: str) -> MissionGitResult:
        branch = _safe_ref(f"{self.mission_id}-{description}")
        try:
            self.repo.create_branch(branch)
        except GitOperationError:
            branch = _safe_ref(f"{self.mission_id}-fallback")
            self.repo.create_branch(branch)
        return self._snapshot(f"Mission {self.mission_id}: start")

    def checkpoint(self, message: str) -> GitCommit:
        self.repo.stage_all()
        return self.repo.commit(f"[{self.mission_id}] {message}")

    def rollback(self, ref: str) -> MissionGitResult:
        self.repo.rollback_to(ref)
        return self._snapshot(f"Rollback a {ref}")

    def diff_since_start(self) -> tuple[GitDiff, ...]:
        refs = self.repo.list_branches()
        current = self.repo.current_branch()
        base_candidates = [b.name for b in refs if b.name != current and b.commit]
        if base_candidates:
            base = base_candidates[0]
        else:
            try:
                out = self.repo._run("rev-list", "--max-parents=0", "--all").strip()
                if out:
                    base = out.splitlines()[0]
                else:
                    return ()
            except GitOperationError:
                return ()
        return self.repo.diff_since(base)

    def _snapshot(self, message: str) -> MissionGitResult:
        commits: list[GitCommit] = []
        try:
            out = self.repo._run("log", "--format=%H|%h|%s|%an|%aI")
            for line in out.splitlines():
                parts = line.strip().split("|", 4)
                if len(parts) == 5:
                    commits.append(GitCommit(*parts, self.repo.current_branch()))
        except GitOperationError:
            pass
        diffs = self.diff_since_start()
        return MissionGitResult(self.repo.current_branch(), tuple(commits), diffs, message)
