import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).parent / "tasks.db"


def init_db():
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            title     TEXT NOT NULL,
            detail    TEXT,
            urgency   INTEGER DEFAULT 3,
            urgency_reason TEXT,
            size      TEXT,
            deadline  TEXT,
            category  TEXT,
            subtasks  TEXT,   -- JSON array stored as string
            done      INTEGER DEFAULT 0,
            created   TEXT DEFAULT (datetime('now'))
        )
    """)
    con.commit()
    con.close()


def save_tasks(tasks: list) -> list:
    """Save a list of task dicts, return them with IDs."""
    con = sqlite3.connect(DB_PATH)
    saved = []
    for t in tasks:
        cur = con.execute(
            """INSERT INTO tasks (title, detail, urgency, urgency_reason, size, deadline, category, subtasks)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                t.get("title"), t.get("detail"), t.get("urgency"),
                t.get("urgency_reason"), t.get("size"), t.get("deadline"),
                t.get("category"), json.dumps(t.get("subtasks", []))
            )
        )
        saved.append({**t, "id": cur.lastrowid, "done": False})
    con.commit()
    con.close()
    return saved


def get_tasks(include_done: bool = False) -> list:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    where = "" if include_done else "WHERE done = 0"
    rows = con.execute(
        f"SELECT * FROM tasks {where} ORDER BY urgency DESC, created DESC"
    ).fetchall()
    con.close()
    result = []
    for r in rows:
        t = dict(r)
        t["subtasks"] = json.loads(t["subtasks"] or "[]")
        t["done"] = bool(t["done"])
        result.append(t)
    return result


def mark_done(task_id: int):
    con = sqlite3.connect(DB_PATH)
    con.execute("UPDATE tasks SET done = 1 WHERE id = ?", (task_id,))
    con.commit()
    con.close()


def delete_task(task_id: int):
    con = sqlite3.connect(DB_PATH)
    con.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    con.commit()
    con.close()

def init_db():
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            title     TEXT NOT NULL,
            detail    TEXT,
            urgency   INTEGER DEFAULT 3,
            urgency_reason TEXT,
            size      TEXT,
            deadline  TEXT,
            category  TEXT,
            subtasks  TEXT,
            done      INTEGER DEFAULT 0,
            created   TEXT DEFAULT (datetime('now'))
        )
    """)
    # new — cache table
    con.execute("""
        CREATE TABLE IF NOT EXISTS cache (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            saved TEXT DEFAULT (datetime('now'))
        )
    """)
    con.commit()
    con.close()


def cache_set(key: str, value: str):
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "INSERT OR REPLACE INTO cache (key, value, saved) VALUES (?, ?, datetime('now'))",
        (key, value)
    )
    con.commit()
    con.close()


def cache_get(key: str) -> str | None:
    con = sqlite3.connect(DB_PATH)
    row = con.execute(
        "SELECT value FROM cache WHERE key = ?", (key,)
    ).fetchone()
    con.close()
    return row[0] if row else None