from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS profiles (
  id INTEGER PRIMARY KEY,
  slot TEXT NOT NULL UNIQUE,
  instagram_username TEXT UNIQUE,
  display_name TEXT,
  biography TEXT,
  avatar_complete INTEGER NOT NULL DEFAULT 0,
  biography_complete INTEGER NOT NULL DEFAULT 0,
  posts_existing INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'pending',
  last_error TEXT,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  profile_id INTEGER NOT NULL REFERENCES profiles(id),
  kind TEXT NOT NULL,
  payload_json TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'pending',
  attempts INTEGER NOT NULL DEFAULT 0,
  idempotency_key TEXT NOT NULL UNIQUE,
  result_json TEXT,
  last_error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS assets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  profile_id INTEGER NOT NULL REFERENCES profiles(id),
  kind TEXT NOT NULL,
  path TEXT NOT NULL UNIQUE,
  sha256 TEXT NOT NULL UNIQUE,
  prompt TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS publications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  profile_id INTEGER NOT NULL REFERENCES profiles(id),
  asset_id INTEGER NOT NULL REFERENCES assets(id),
  remote_id TEXT UNIQUE,
  status TEXT NOT NULL,
  idempotency_key TEXT NOT NULL UNIQUE,
  published_at TEXT
);
CREATE TABLE IF NOT EXISTS control (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
INSERT OR IGNORE INTO control(key, value) VALUES ('paused', '1');
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(root: Path) -> sqlite3.Connection:
    db = root / "state.sqlite3"
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def initialize(root: Path, count: int) -> None:
    (root / "logs").mkdir(parents=True, exist_ok=True)
    with connect(root) as con:
        for number in range(1, count + 1):
            slot = f"Perfil_{number:02d}"
            folder = root / slot
            (folder / "avatar").mkdir(parents=True, exist_ok=True)
            (folder / "publicacoes").mkdir(exist_ok=True)
            for filename in ("biografia.txt", "prompts.txt"):
                (folder / filename).touch(exist_ok=True)
            con.execute(
                "INSERT OR IGNORE INTO profiles(id, slot, updated_at) VALUES (?, ?, ?)",
                (number, slot, now()),
            )
    write_report(root)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def register_asset(root: Path, profile_id: int, kind: str, path: Path, prompt: str | None = None) -> int:
    resolved = path.resolve()
    digest = sha256(resolved)
    with connect(root) as con:
        duplicate = con.execute("SELECT id, path FROM assets WHERE sha256=?", (digest,)).fetchone()
        if duplicate:
            raise ValueError(f"Arquivo duplicado; já registrado como {duplicate['path']}")
        cursor = con.execute(
            "INSERT INTO assets(profile_id, kind, path, sha256, prompt, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (profile_id, kind, str(resolved), digest, prompt, now()),
        )
        asset_id = int(cursor.lastrowid)
    write_report(root)
    return asset_id


def update_profile(
    root: Path, profile_id: int, *, username: str, display_name: str | None,
    biography: str | None, avatar_complete: bool, biography_complete: bool,
    posts_existing: int, complete: bool,
) -> None:
    clean_username = username.strip().lstrip("@")
    if not clean_username:
        raise ValueError("username é obrigatório")
    with connect(root) as con:
        con.execute(
            """UPDATE profiles SET instagram_username=?, display_name=?, biography=?,
               avatar_complete=?, biography_complete=?, posts_existing=?, status=?,
               last_error=NULL, updated_at=? WHERE id=?""",
            (clean_username, display_name, biography, int(avatar_complete),
             int(biography_complete), posts_existing,
             "complete" if complete else "pending", now(), profile_id),
        )
    write_report(root)


def write_report(root: Path) -> Path:
    with connect(root) as con:
        profiles = [dict(row) for row in con.execute("SELECT * FROM profiles ORDER BY id")]
        tasks = [dict(row) for row in con.execute("SELECT * FROM tasks ORDER BY id")]
        assets = [dict(row) for row in con.execute("SELECT * FROM assets ORDER BY id")]
        pubs = [dict(row) for row in con.execute("SELECT * FROM publications ORDER BY id")]
        paused = con.execute("SELECT value FROM control WHERE key='paused'").fetchone()[0] == "1"
    report = {
        "generated_at": now(),
        "paused": paused,
        "profiles": profiles,
        "tasks": tasks,
        "assets": assets,
        "publications": pubs,
    }
    output = root / "relatorio.json"
    temporary = output.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(output)
    return output
