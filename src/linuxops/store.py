"""SQLite-backed timeline: bounded, local, and intentionally free of raw identifiers."""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock


class TelemetryStore:
    def __init__(self, database: str | Path, *, retention_days: int = 7):
        if retention_days < 1 or retention_days > 365:
            raise ValueError("Retention must be between 1 and 365 days")
        self.database = Path(database).expanduser()
        self.retention_days = retention_days
        self.lock = Lock()
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                observed_at TEXT NOT NULL,
                payload TEXT NOT NULL
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_samples_time ON samples(observed_at)")
            db.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    def save(self, payload: dict) -> None:
        timestamp = datetime.fromisoformat(payload["timestamp"])
        if timestamp.tzinfo is None:
            raise ValueError("Timezone-aware timestamps are required")
        cutoff = (datetime.now(timezone.utc) - timedelta(days=self.retention_days)).isoformat()
        with self.lock:
            with closing(self._connect()) as db, db:
                db.execute("INSERT INTO samples(observed_at, payload) VALUES(?,?)",
                           (timestamp.astimezone(timezone.utc).isoformat(), json.dumps(payload)))
                db.execute("DELETE FROM samples WHERE observed_at < ?", (cutoff,))

    def recent(self, *, limit: int = 120, since: datetime | None = None) -> list[dict]:
        if not 1 <= limit <= 5000:
            raise ValueError("Limit must be between 1 and 5000")
        with closing(self._connect()) as db:
            if since:
                if since.tzinfo is None:
                    raise ValueError("Since must be timezone aware")
                rows = db.execute(
                    "SELECT payload FROM samples WHERE observed_at >= ? ORDER BY id DESC LIMIT ?",
                    (since.astimezone(timezone.utc).isoformat(), limit),
                ).fetchall()
            else:
                rows = db.execute("SELECT payload FROM samples ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [json.loads(row[0]) for row in reversed(rows)]

    def latest(self) -> dict | None:
        recent = self.recent(limit=1)
        return recent[0] if recent else None

    def count(self) -> int:
        with closing(self._connect()) as db:
            return db.execute("SELECT COUNT(*) FROM samples").fetchone()[0]
