import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class MemoryStore:
    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                ts TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT 'fact',
                source TEXT NOT NULL DEFAULT 'conversation',
                ts TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                ts TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                origin TEXT NOT NULL DEFAULT 'global',
                ts TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                reason TEXT,
                result TEXT,
                verification TEXT,
                ts TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    def _now(self):
        return datetime.now(timezone.utc).isoformat()

    def add_conversation(self, role, content):
        self.conn.execute(
            "INSERT INTO conversations (role, content, ts) VALUES (?, ?, ?)",
            (role, content, self._now()),
        )
        self.conn.commit()

    def recent_conversation(self, limit=20):
        rows = self.conn.execute(
            "SELECT role, content FROM conversations ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return list(reversed([(r["role"], r["content"]) for r in rows]))

    def remember(self, content, kind="fact", source="conversation"):
        self.conn.execute(
            "INSERT INTO memory (content, kind, source, ts) VALUES (?, ?, ?, ?)",
            (content, kind, source, self._now()),
        )
        self.conn.commit()

    def recall(self, query=None, limit=10):
        if query:
            like = f"%{query}%"
            rows = self.conn.execute(
                "SELECT content, kind, source, ts FROM memory "
                "WHERE content LIKE ? ORDER BY id DESC LIMIT ?",
                (like, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT content, kind, source, ts FROM memory "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def add_task(self, title):
        self.conn.execute(
            "INSERT INTO tasks (title, status, ts) VALUES (?, 'pending', ?)",
            (title, self._now()),
        )
        self.conn.commit()

    def list_tasks(self, status=None):
        if status:
            rows = self.conn.execute(
                "SELECT id, title, status FROM tasks WHERE status = ? ORDER BY id DESC",
                (status,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT id, title, status FROM tasks ORDER BY id DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def complete_task(self, task_id):
        self.conn.execute(
            "UPDATE tasks SET status = 'done' WHERE id = ?", (task_id,)
        )
        self.conn.commit()

    def cache_knowledge(self, question, answer, origin="global"):
        self.conn.execute(
            "INSERT INTO knowledge (question, answer, origin, ts) VALUES (?, ?, ?, ?)",
            (question, answer, origin, self._now()),
        )
        self.conn.commit()

    def find_cached_knowledge(self, question):
        like = f"%{question}%"
        rows = self.conn.execute(
            "SELECT question, answer, origin FROM knowledge "
            "WHERE question LIKE ? OR answer LIKE ? "
            "ORDER BY id DESC LIMIT 1",
            (like, like),
        ).fetchall()
        return dict(rows[0]) if rows else None

    def log_action(self, action, reason=None, result=None, verification=None):
        self.conn.execute(
            "INSERT INTO actions (action, reason, result, verification, ts) "
            "VALUES (?, ?, ?, ?, ?)",
            (action, reason, result, verification, self._now()),
        )
        self.conn.commit()

    def close(self):
        self.conn.close()

    def recent_actions(self, limit=10):
        rows = self.conn.execute(
            "SELECT action, reason, result, verification, ts "
            "FROM actions ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]