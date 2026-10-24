from __future__ import annotations

import json
import random
import time
from pathlib import Path

from .storage import connect, now, write_report


def set_paused(root: Path, paused: bool) -> None:
    with connect(root) as con:
        con.execute("UPDATE control SET value=? WHERE key='paused'", ("1" if paused else "0",))
    write_report(root)


def is_paused(root: Path) -> bool:
    with connect(root) as con:
        return con.execute("SELECT value FROM control WHERE key='paused'").fetchone()[0] == "1"


def add_task(root: Path, profile_id: int, kind: str, payload: dict, key: str) -> None:
    with connect(root) as con:
        con.execute(
            "INSERT OR IGNORE INTO tasks(profile_id, kind, payload_json, idempotency_key, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (profile_id, kind, json.dumps(payload, ensure_ascii=False), key, now(), now()),
        )
    write_report(root)


def claim_next(root: Path):
    with connect(root) as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT * FROM tasks WHERE status IN ('pending','retry') ORDER BY id LIMIT 1").fetchone()
        if row is None:
            return None
        con.execute(
            "UPDATE tasks SET status='running', attempts=attempts+1, updated_at=? WHERE id=?",
            (now(), row["id"]),
        )
        return dict(row)


def finish(root: Path, task_id: int, result: dict) -> None:
    with connect(root) as con:
        con.execute(
            "UPDATE tasks SET status='done', result_json=?, last_error=NULL, updated_at=? WHERE id=?",
            (json.dumps(result, ensure_ascii=False), now(), task_id),
        )
    write_report(root)


def fail(root: Path, task_id: int, error: Exception, retry: bool = False) -> None:
    with connect(root) as con:
        con.execute(
            "UPDATE tasks SET status=?, last_error=?, updated_at=? WHERE id=?",
            ("retry" if retry else "blocked", str(error), now(), task_id),
        )
    write_report(root)


def stable_delay(minimum: int, maximum: int) -> None:
    time.sleep(random.randint(minimum, maximum))
