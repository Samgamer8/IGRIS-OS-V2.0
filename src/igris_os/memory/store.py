import json
import os
import sqlite3
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path


def _is_onedrive_path(path: Path) -> bool:
    """True si el path esta dentro de la carpeta OneDrive del usuario."""
    try:
        resolved = path.resolve()
    except OSError:
        return False
    onedrive = Path.home() / "OneDrive"
    try:
        resolved.relative_to(onedrive)
        return True
    except ValueError:
        return False


class MemoryStore:
    def __init__(self, path: Path) -> None:
        env_override = os.environ.get("IGRIS_MEMORY_PATH")
        if env_override:
            path = Path(env_override) / "memories.db"
        elif _is_onedrive_path(path):
            path = Path(tempfile.gettempdir()) / "igris_memory" / "memories.db"
        self.path = path
        self._write_lock = threading.Lock()
        self._connection = None
        self._delete_count_since_vacuum = 0
        self._vacuum_threshold = 100
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS memories(
                id INTEGER PRIMARY KEY, category TEXT NOT NULL, content TEXT NOT NULL,
                verified INTEGER NOT NULL, created_at TEXT NOT NULL)""")
            db.execute("""CREATE INDEX IF NOT EXISTS idx_mem_cat_ver ON memories(category, verified, id DESC)""")

    def _connect(self):
        conn = sqlite3.connect(
            self.path,
            check_same_thread=False,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        )
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-64000")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA wal_autocheckpoint=1000")
        return conn

    def _get_connection(self):
        if self._connection is None:
            self._connection = self._connect()
        return self._connection

    def close(self):
        if self._connection is not None:
            try:
                self._connection.close()
            except Exception:
                pass
            self._connection = None

    def __del__(self):
        self.close()

    def remember(self, category: str, content: dict, *, verified: bool = False) -> int:
        if not category.strip() or not content:
            raise ValueError("Memoria vacia")
        with self._write_lock:
            db = self._get_connection()
            cursor = db.execute(
                "INSERT INTO memories(category,content,verified,created_at) VALUES(?,?,?,?)",
                (category, json.dumps(content, ensure_ascii=False), int(verified),
                 datetime.now(timezone.utc).isoformat()))
            db.commit()
            return int(cursor.lastrowid)

    def remember_many(self, category: str, contents: list[dict], *, verified: bool = False) -> list[int]:
        if not category.strip() or not contents:
            raise ValueError("Memoria vacia")
        with self._write_lock:
            db = self._get_connection()
            now = datetime.now(timezone.utc).isoformat()
            rows = [
                (category, json.dumps(content, ensure_ascii=False), int(verified), now)
                for content in contents
            ]
            db.executemany(
                "INSERT INTO memories(category,content,verified,created_at) VALUES(?,?,?,?)",
                rows)
            db.commit()
            cursor = db.execute(
                "SELECT id FROM memories WHERE category=? AND created_at=? ORDER BY id DESC LIMIT ?",
                (category, now, len(rows)))
            return [int(row[0]) for row in cursor.fetchall()]

    def recall(self, category: str, *, verified_only: bool = True,
               limit: int = 100) -> list[dict]:
        query = "SELECT id,content,verified,created_at FROM memories WHERE category=?"
        args: list = [category]
        if verified_only:
            query += " AND verified=1"
        query += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        db = self._get_connection()
        rows = db.execute(query, args).fetchall()
        return [{"id": row[0], "content": json.loads(row[1]),
                 "verified": bool(row[2]), "created_at": row[3]} for row in rows]

    def verify(self, memory_id: int) -> None:
        with self._write_lock:
            db = self._get_connection()
            cursor = db.execute("UPDATE memories SET verified=1 WHERE id=?", (memory_id,))
            if not cursor.rowcount:
                raise KeyError(memory_id)
            db.commit()

    def recent(self, category: str, *, limit: int = 20,
               verified_only: bool = True) -> list[dict]:
        if limit < 1 or limit > 500:
            raise ValueError("Limite invalido")
        query = "SELECT id,content,verified,created_at FROM memories WHERE category=?"
        args: list = [category]
        if verified_only:
            query += " AND verified=1"
        query += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        db = self._get_connection()
        rows = db.execute(query, args).fetchall()
        return [{"id": row[0], "content": json.loads(row[1]),
                 "verified": bool(row[2]), "created_at": row[3]} for row in rows]

    def count(self, category: str, *, verified_only: bool = True) -> int:
        query = "SELECT COUNT(*) FROM memories WHERE category=?"
        args = [category]
        if verified_only:
            query += " AND verified=1"
        db = self._get_connection()
        return int(db.execute(query, args).fetchone()[0])

    def cleanup(self, force: bool = False) -> None:
        if force or self._delete_count_since_vacuum >= self._vacuum_threshold:
            with self._write_lock:
                db = self._get_connection()
                db.execute("VACUUM")
                db.commit()
                self._delete_count_since_vacuum = 0

    def _increment_delete_count(self):
        self._delete_count_since_vacuum += 1
        if self._delete_count_since_vacuum >= self._vacuum_threshold:
            self.cleanup()
