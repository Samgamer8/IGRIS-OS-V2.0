import threading
import time
from collections.abc import Callable
from pathlib import Path

_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "runtime", ".pytest_cache"}


class RepositoryWatcher:
    def __init__(self):
        self._thread = None
        self._stop = threading.Event()

    def watch(self, root: Path, callback: Callable[[list[Path]], None]):
        def scan():
            files = {}
            for p in root.rglob("*"):
                if any(part in _SKIP_DIRS for part in p.relative_to(root).parts):
                    continue
                if not p.is_file():
                    continue
                try:
                    s = p.stat()
                except OSError:
                    continue
                if s.st_size > 16 * 1024 * 1024:
                    continue
                files[p] = (s.st_mtime, s.st_size)
            return files

        known = scan()
        pending = set()
        changed_at = None

        def flush():
            nonlocal changed_at
            if self._stop.is_set():
                return
            if pending:
                callback(list(pending))
                pending.clear()
            changed_at = None

        callback(list(known.keys()))

        def run():
            nonlocal changed_at
            nonlocal pending
            while not self._stop.wait(2):
                current = {}
                new_pending = set()
                for p in root.rglob("*"):
                    if any(part in _SKIP_DIRS for part in p.relative_to(root).parts):
                        continue
                    if not p.is_file():
                        continue
                    try:
                        s = p.stat()
                    except OSError:
                        continue
                    if s.st_size > 16 * 1024 * 1024:
                        continue
                    current[p] = (s.st_mtime, s.st_size)
                    if p not in known or known[p] != current[p]:
                        new_pending.add(p)

                for p in set(known) - set(current):
                    new_pending.add(p)

                if new_pending:
                    pending |= new_pending
                    if changed_at is None:
                        changed_at = time.monotonic()

                known.clear()
                known.update(current)

                if pending and time.monotonic() - changed_at >= 1:
                    flush()

            flush()

        self._stop.clear()
        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None
