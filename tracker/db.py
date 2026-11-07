"""SQLite database connection and schema definition for Activity Tracker."""

from __future__ import annotations

import sqlite3
from pathlib import Path

DEFAULT_DB_NAME = "activity_tracker.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    target_value REAL NOT NULL CHECK (target_value > 0),
    unit TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activity_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
    log_date TEXT NOT NULL,
    actual_value REAL NOT NULL CHECK (actual_value >= 0),
    is_completed INTEGER NOT NULL CHECK (is_completed IN (0, 1)),
    notes TEXT NOT NULL DEFAULT '',
    UNIQUE(activity_id, log_date)
);

CREATE TABLE IF NOT EXISTS backup_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    file_path TEXT NOT NULL,
    activities_count INTEGER NOT NULL CHECK (activities_count >= 0),
    logs_count INTEGER NOT NULL CHECK (logs_count >= 0),
    action TEXT NOT NULL CHECK (action IN ('EXPORT', 'RESTORE'))
);
"""


def connect(path: str | Path = ":memory:") -> sqlite3.Connection:
    """Open SQLite connection, enable foreign keys, and initialize schema."""
    db = sqlite3.connect(str(path), check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(SCHEMA)
    return db
