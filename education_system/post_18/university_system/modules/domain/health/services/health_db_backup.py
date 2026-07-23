from __future__ import annotations

import shutil
import logging
from datetime import datetime
from pathlib import Path

from education_system.post_18.university_system.infrastructure.database.db import sqlite3, get_connection

# Configure logging
logger = logging.getLogger(__name__)

def _sqlite_main_db_path(conn: sqlite3.Connection) -> Path | None:
    """
    Resolve the on-disk path of the main SQLite database for this connection.
    Works with file: URIs and regular paths. Returns None for in-memory DBs.
    """
    try:
        rows = conn.execute("PRAGMA database_list").fetchall()
        for _, name, file_ in rows:
            if name == "main":
                if not file_:
                    return None
                # Handle SQLite URI format: file:/path/to/db.sqlite3?mode=rwc
                if file_.startswith("file:"):
                    file_ = file_.split("?", 1)[0].replace("file:", "", 1)
                return Path(file_).resolve()
    except Exception as e:
        logger.debug(f"Could not resolve database path: {e}")
    return None

def create_sqlite_backup(conn: sqlite3.Connection, label: str = "pre_purge", backup_dir: Path | None = None) -> Path:
    """
    Make a consistent backup using the SQLite backup API.
    Copies WAL safely; returns the backup path. Raises on failure.
    """
    db_path = _sqlite_main_db_path(conn)
    if db_path is None or not db_path.exists():
        raise FileNotFoundError("SQLite DB file not found via PRAGMA database_list")

    if backup_dir is None:
        backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = backup_dir / f"{db_path.stem}.{label}.{ts}.sqlite3"

    # Use SQLite backup API for a coherent snapshot
    with sqlite3.connect(backup_path) as dst:
        conn.backup(dst)

    # Best-effort copy of WAL/SHM (not strictly needed after backup API)
    for suffix in ("-wal", "-shm"):
        sidecar = db_path.with_name(db_path.name + suffix)
        if sidecar.exists():
            try:
                shutil.copy2(sidecar, backup_dir / (backup_path.name + suffix))
            except Exception as e:
                logger.debug(f"Could not copy sidecar file {sidecar}: {e}")

    return backup_path

def ensure_templates_schema():
    """
    Ensure the 'templates' table exists and has expected columns.
    Safe to call repeatedly.
    """
    conn = get_connection()
    try:
        c = conn.cursor()

        # Create table if missing
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='templates'")
        if not c.fetchone():
            c.execute("""
                CREATE TABLE templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    category TEXT,
                    body TEXT NOT NULL,
                    created_by TEXT,
                    is_shared INTEGER DEFAULT 0,         -- 0/1
                    version INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_templates_category ON templates(category)")
            conn.commit()
            return  # freshly created; no column backfills needed

        # Table exists: make sure required columns exist
        c.execute("PRAGMA table_info(templates)")
        cols = {row[1] for row in c.fetchall()}

        def add_col(sql):
            try:
                c.execute(sql)
            except sqlite3.OperationalError as e:
                logger.debug(f"Column alteration skipped (may already exist): {e}")

        if 'is_shared' not in cols:
            add_col("ALTER TABLE templates ADD COLUMN is_shared INTEGER DEFAULT 0")
        if 'version' not in cols:
            add_col("ALTER TABLE templates ADD COLUMN version INTEGER DEFAULT 1")
        if 'created_by' not in cols:
            add_col("ALTER TABLE templates ADD COLUMN created_by TEXT")
        if 'updated_at' not in cols:
            add_col("ALTER TABLE templates ADD COLUMN updated_at TEXT")
        if 'body' not in cols:
            # Worst case: old schema with 'content' only. Try to add body and backfill.
            add_col("ALTER TABLE templates ADD COLUMN body TEXT")
            try:
                c.execute("UPDATE templates SET body = COALESCE(body, content)")
            except Exception as e:
                logger.debug(f"Could not update template body column: {e}")

        conn.commit()
    finally:
        try:
            conn.close()
        except Exception as e:
            logger.debug(f"Could not close database connection: {e}")
