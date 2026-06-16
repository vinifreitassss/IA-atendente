import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import get_settings


class Storage:
    def __init__(self) -> None:
        settings = get_settings()
        self.db_path = Path(settings.database_path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(conversation_id) REFERENCES conversations(id)
                );

                CREATE TABLE IF NOT EXISTS draft_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'rascunho',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(conversation_id) REFERENCES conversations(id)
                );
                """
            )

    def ensure_conversation(self, conversation_id: str | None = None) -> str:
        now = datetime.now(timezone.utc).isoformat()
        cid = conversation_id or str(uuid.uuid4())
        with self._connect() as conn:
            exists = conn.execute(
                "SELECT id FROM conversations WHERE id = ?",
                (cid,),
            ).fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO conversations (id, state_json, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (cid, "{}", now, now),
                )
        return cid

    def add_message(self, conversation_id: str, role: str, content: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (conversation_id, role, content, now),
            )
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id),
            )

    def get_recent_messages(self, conversation_id: str, limit: int = 12) -> list[dict[str, str]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT role, content, created_at
                FROM messages
                WHERE conversation_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (conversation_id, limit),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def get_state(self, conversation_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT state_json FROM conversations WHERE id = ?",
                (conversation_id,),
            ).fetchone()
        if not row:
            return {}
        try:
            return json.loads(row["state_json"] or "{}")
        except json.JSONDecodeError:
            return {}

    def save_state(self, conversation_id: str, state: dict[str, Any]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "UPDATE conversations SET state_json = ?, updated_at = ? WHERE id = ?",
                (json.dumps(state, ensure_ascii=False), now, conversation_id),
            )

    def create_draft_order(self, conversation_id: str, payload: dict[str, Any]) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO draft_orders (conversation_id, payload_json, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (conversation_id, json.dumps(payload, ensure_ascii=False), now, now),
            )
            return int(cur.lastrowid)
