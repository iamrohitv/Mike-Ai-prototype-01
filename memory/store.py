import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

STOPWORDS = {
    "a", "about", "am", "an", "and", "are", "as", "at", "be", "by",
    "can", "could", "did", "do", "does", "for", "from", "get", "have",
    "how", "i", "in", "is", "it", "its", "me", "my", "of", "on", "or",
    "our", "out", "please", "so", "tell", "that", "the", "this", "to",
    "us", "was", "we", "what", "when", "where", "which", "who", "why",
    "will", "with", "you", "your", "want", "like", "help", "know",
    "need", "see", "look", "check", "show", "remind", "remember",
    "make", "made", "any", "some", "just", "then", "there",
}


def _words(text):
    return set(re.findall(r"[a-z0-9]+", (text or "").lower())) - STOPWORDS


def _bigrams(text):
    words = [w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if w not in STOPWORDS]
    return {" ".join(words[i:i + 2]) for i in range(len(words) - 1)}


def _extract_tags(content, limit=4):
    words = [w for w in re.findall(r"[a-z0-9]+", (content or "").lower()) if w not in STOPWORDS]
    counter = {}
    for w in words:
        counter[w] = counter.get(w, 0) + 1
    top = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
    return ",".join(w for w, _ in top if len(w) > 2)


class MemoryStore:
    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
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
                status TEXT NOT NULL DEFAULT 'active',
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

            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT 'pc',
                synced_ts TEXT
            );

            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                due_ts TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                ts TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                value REAL,
                ts TEXT NOT NULL
            );
            """
        )
        self.conn.commit()
        self._migrate()

    def _migrate(self):
        columns = [
            row["name"]
            for row in self.conn.execute("PRAGMA table_info(memory)").fetchall()
        ]
        if "status" not in columns:
            self.conn.execute(
                "ALTER TABLE memory ADD COLUMN status TEXT NOT NULL DEFAULT 'active'"
            )
        if "tags" not in columns:
            self.conn.execute(
                "ALTER TABLE memory ADD COLUMN tags TEXT NOT NULL DEFAULT ''"
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

    def remember(self, content, kind="fact", source="conversation", tags=None):
        tags = tags or _extract_tags(content)
        self.conn.execute(
            "INSERT INTO memory (content, kind, source, tags, ts) VALUES (?, ?, ?, ?, ?)",
            (content, kind, source, tags, self._now()),
        )
        self.conn.commit()

    def recall_by_tag(self, tag, limit=10):
        rows = self.conn.execute(
            "SELECT content, kind, source, tags, ts FROM memory "
            "WHERE status = 'active' AND tags LIKE ? ORDER BY id DESC LIMIT ?",
            (f"%{tag}%", limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def recall(self, query=None, limit=10):
        rows = self.conn.execute(
            "SELECT content, kind, source, tags, ts FROM memory "
            "WHERE status = 'active' ORDER BY id DESC"
        ).fetchall()
        records = [dict(r) for r in rows]

        if not query or not _words(query):
            return records[:limit]

        qwords = _words(query)
        qbigrams = _bigrams(query)
        doc_count = len(records) or 1
        word_docs = {}
        for record in records:
            for w in _words(record["content"]):
                word_docs[w] = word_docs.get(w, 0) + 1
        scored = []
        for record in records:
            mwords = _words(record["content"])
            if not mwords:
                continue
            overlap = qwords & mwords
            if not overlap:
                continue
            idf = sum(
                doc_count / (word_docs.get(w, 0) or 1) for w in overlap
            )
            ratio = idf / (1 + len(mwords))
            bigram_hits = len(qbigrams & _bigrams(record["content"]))
            tag_hits = len(qwords & set((record.get("tags") or "").split(",")))
            score = idf + ratio + (bigram_hits * 1.5) + (tag_hits * 2.0)
            scored.append((score, record))
        scored.sort(key=lambda x: x[0], reverse=True)
        matches = [record for _, record in scored][:limit]
        if matches:
            return matches
        return records[:limit]

    def recent_memories(self, limit=5):
        rows = self.conn.execute(
            "SELECT content, kind, source, ts FROM memory "
            "WHERE status = 'active' ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def active_memories(self, limit=50):
        rows = self.conn.execute(
            "SELECT id, content, kind, source, ts FROM memory "
            "WHERE status = 'active' ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def archive_memories(self, ids):
        if not ids:
            return 0
        placeholders = ",".join("?" for _ in ids)
        cursor = self.conn.execute(
            f"UPDATE memory SET status = 'archived' WHERE id IN ({placeholders})",
            list(ids),
        )
        self.conn.commit()
        return cursor.rowcount

    def restore_memories(self, ids):
        if not ids:
            return 0
        placeholders = ",".join("?" for _ in ids)
        cursor = self.conn.execute(
            f"UPDATE memory SET status = 'active' WHERE id IN ({placeholders})",
            list(ids),
        )
        self.conn.commit()
        return cursor.rowcount

    def archived_memories(self, limit=50):
        rows = self.conn.execute(
            "SELECT id, content, kind, source, ts FROM memory "
            "WHERE status = 'archived' ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def recent_pending_tasks(self, limit=5):
        rows = self.conn.execute(
            "SELECT id, title, status, ts FROM tasks "
            "WHERE status = 'pending' ORDER BY id DESC LIMIT ?",
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

    def register_device(self, name, kind="pc"):
        self.conn.execute(
            "INSERT INTO devices (name, kind, synced_ts) VALUES (?, ?, ?)",
            (name, kind, self._now()),
        )
        self.conn.commit()
        return True

    def list_devices(self):
        rows = self.conn.execute(
            "SELECT id, name, kind, synced_ts FROM devices ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]

    def touch_device(self, name):
        self.conn.execute(
            "UPDATE devices SET synced_ts = ? WHERE name = ?",
            (self._now(), name),
        )
        self.conn.commit()

    def sync_changes(self, since_ts=None):
        if since_ts:
            memories = self.conn.execute(
                "SELECT content, kind, source, status, ts FROM memory "
                "WHERE ts > ? ORDER BY ts",
                (since_ts,),
            ).fetchall()
            conversations = self.conn.execute(
                "SELECT role, content, ts FROM conversations WHERE ts > ? ORDER BY ts",
                (since_ts,),
            ).fetchall()
        else:
            memories = self.conn.execute(
                "SELECT content, kind, source, status, ts FROM memory ORDER BY ts"
            ).fetchall()
            conversations = self.conn.execute(
                "SELECT role, content, ts FROM conversations ORDER BY ts"
            ).fetchall()
        return {
            "memories": [dict(r) for r in memories],
            "conversations": [dict(r) for r in conversations],
        }

    def apply_sync(self, payload, device_name):
        count = 0
        for mem in payload.get("memories", []):
            existing = self.conn.execute(
                "SELECT id FROM memory WHERE content = ? AND ts = ?",
                (mem["content"], mem["ts"]),
            ).fetchone()
            if existing:
                continue
            self.conn.execute(
                "INSERT INTO memory (content, kind, source, status, ts) "
                "VALUES (?, ?, ?, ?, ?)",
                (mem["content"], mem["kind"], mem["source"],
                 mem.get("status", "active"), mem["ts"]),
            )
            count += 1
        for conv in payload.get("conversations", []):
            existing = self.conn.execute(
                "SELECT id FROM conversations WHERE content = ? AND ts = ?",
                (conv["content"], conv["ts"]),
            ).fetchone()
            if existing:
                continue
            self.conn.execute(
                "INSERT INTO conversations (role, content, ts) VALUES (?, ?, ?)",
                (conv["role"], conv["content"], conv["ts"]),
            )
            count += 1
        self.conn.commit()
        self.touch_device(device_name)
        return count

    def add_reminder(self, title, due_ts):
        self.conn.execute(
            "INSERT INTO reminders (title, due_ts, status, ts) VALUES (?, ?, 'pending', ?)",
            (title, due_ts, self._now()),
        )
        self.conn.commit()
        return True

    def due_reminders(self, now_ts=None):
        now_ts = now_ts or self._now()
        rows = self.conn.execute(
            "SELECT id, title, due_ts FROM reminders "
            "WHERE status = 'pending' AND due_ts <= ? ORDER BY due_ts",
            (now_ts,),
        ).fetchall()
        return [dict(r) for r in rows]

    def pending_reminders(self, limit=20):
        rows = self.conn.execute(
            "SELECT id, title, due_ts FROM reminders "
            "WHERE status = 'pending' ORDER BY due_ts LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_reminder_done(self, reminder_id):
        self.conn.execute(
            "UPDATE reminders SET status = 'done' WHERE id = ?",
            (reminder_id,),
        )
        self.conn.commit()
        return True

    def record_metric(self, name, value):
        self.conn.execute(
            "INSERT INTO metrics (name, value, ts) VALUES (?, ?, ?)",
            (name, value, self._now()),
        )
        self.conn.commit()
        return True

    def recent_metrics(self, name, limit=30):
        rows = self.conn.execute(
            "SELECT value, ts FROM metrics "
            "WHERE name = ? ORDER BY id DESC LIMIT ?",
            (name, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def conversation_count(self):
        row = self.conn.execute(
            "SELECT COUNT(*) AS c FROM conversations"
        ).fetchone()
        return row["c"]

    def prune_conversations(self, keep=200):
        rows = self.conn.execute(
            "SELECT id FROM conversations ORDER BY id DESC LIMIT -1 OFFSET ?",
            (keep,),
        ).fetchall()
        if not rows:
            return 0
        ids = [r["id"] for r in rows]
        placeholders = ",".join("?" for _ in ids)
        cursor = self.conn.execute(
            f"DELETE FROM conversations WHERE id IN ({placeholders})", ids
        )
        self.conn.commit()
        return cursor.rowcount

    def summarize_old_conversation(self, limit=100):
        rows = self.conn.execute(
            "SELECT role, content FROM conversations ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        pairs = list(reversed([(r["role"], r["content"]) for r in rows]))
        if len(pairs) <= 40:
            return None
        recent = pairs[-10:]
        older = pairs[:-10]
        summary = (
            "Conversation history (auto-summarized): "
            + "; ".join(content for _, content in older[:30])
        )
        self.remember(summary, kind="summary", source="compaction")
        return len(older)