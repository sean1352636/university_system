from __future__ import annotations

import shutil
import logging
from datetime import datetime
from pathlib import Path

from education_system.systems.university.domains.health.infrastructure.health.storage import sqlite3, get_connection

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
    """The ``templates`` table and the columns older layouts lacked
    (``is_shared`` / ``version`` / ``created_by`` / ``updated_at`` / ``body``,
    filled from ``content`` when added) — declared in
    ``infrastructure/health/health_schema``. Safe to call repeatedly."""
    from education_system.systems.university.domains.health.infrastructure.health import (
        health_schema,
    )
    health_schema.ensure()
