import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class MemoryStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS memories(
                id INTEGER PRIMARY KEY, category TEXT NOT NULL, content TEXT NOT NULL,
                verified INTEGER NOT NULL, created_at TEXT NOT NULL)""")

    def _connect(self):
        return sqlite3.connect(self.path)

    def remember(self, category: str, content: dict, *, verified: bool = False) -> int:
        if not category.strip() or not content:
            raise ValueError("Memoria vacia")
        with self._connect() as db:
            cursor = db.execute(
                "INSERT INTO memories(category,content,verified,created_at) VALUES(?,?,?,?)",
                (category, json.dumps(content, ensure_ascii=False), int(verified),
                 datetime.now(timezone.utc).isoformat()))
            return int(cursor.lastrowid)

    def recall(self, category: str, *, verified_only: bool = True) -> list[dict]:
        query = "SELECT id,content,verified,created_at FROM memories WHERE category=?"
        args = [category]
        if verified_only:
            query += " AND verified=1"
        query += " ORDER BY id DESC"
        with self._connect() as db:
            rows = db.execute(query, args).fetchall()
        return [{"id": row[0], "content": json.loads(row[1]),
                 "verified": bool(row[2]), "created_at": row[3]} for row in rows]

    def verify(self, memory_id: int) -> None:
        with self._connect() as db:
            cursor = db.execute("UPDATE memories SET verified=1 WHERE id=?", (memory_id,))
            if not cursor.rowcount:
                raise KeyError(memory_id)
