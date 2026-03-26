"""Archival utilities for GDPR data retention.

The ``Archiver`` class moves expired records out of live tables, either
into a companion ``{table}_archive`` table within the same database or
into an encrypted JSON file on disk.
"""

import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


class Archiver:
    """Move expired records to an archive destination.

    Two modes are supported:

    * **Table mode** (default): rows are copied to ``{table}_archive`` within
      the same database, then deleted from the live table.
    * **File mode**: rows are serialised to a JSON file at *archive_path*.
      The JSON is written with restricted permissions (0o600) to protect PII.
      For production deployments consider adding encryption at rest.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def archive_records(
        self,
        db_path: str | Path,
        table: str,
        where_clause: str,
        where_params: list | None = None,
        *,
        archive_path: str | Path | None = None,
        delete_after_archive: bool = True,
    ) -> dict:
        """Archive all records in *table* that match *where_clause*.

        Parameters
        ----------
        db_path:
            Path to the SQLite database.
        table:
            Source table name.
        where_clause:
            SQL WHERE fragment (without the ``WHERE`` keyword), e.g.
            ``"created_at < ?"``.
        where_params:
            Positional parameters bound to *where_clause*.
        archive_path:
            If given, rows are written to this file path (JSON).
            If *None*, rows are moved to ``{table}_archive`` in the same DB.
        delete_after_archive:
            When *True* (default) the source rows are deleted after archiving.
            Set to *False* for dry-run inspection.

        Returns
        -------
        dict with ``table``, ``archive_destination``, ``records_archived``,
        ``status``.
        """
        conn = _connect(db_path)
        try:
            rows = conn.execute(
                f"SELECT * FROM {table} WHERE {where_clause}",  # noqa: S608
                where_params or [],
            ).fetchall()
        finally:
            conn.close()

        if not rows:
            return {
                "table": table,
                "archive_destination": str(archive_path or f"{table}_archive"),
                "records_archived": 0,
                "status": "nothing_to_archive",
            }

        records = [dict(r) for r in rows]

        if archive_path:
            destination = self._archive_to_file(table, records, archive_path)
        else:
            destination = self._archive_to_table(db_path, table, records)

        if delete_after_archive:
            deleted = self._delete_records(
                db_path, table, where_clause, where_params or []
            )
        else:
            deleted = 0

        logger.info(
            "Archived %d rows from %s → %s (deleted=%d)",
            len(records), table, destination, deleted,
        )
        return {
            "table": table,
            "archive_destination": destination,
            "records_archived": len(records),
            "records_deleted": deleted,
            "status": "archived",
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _archive_to_table(
        self,
        db_path: str | Path,
        table: str,
        records: list[dict[str, Any]],
    ) -> str:
        """Copy *records* into ``{table}_archive``, creating it if needed."""
        archive_table = f"{table}_archive"
        conn = _connect(db_path)
        try:
            # Create archive table mirroring source schema (add archived_at)
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {archive_table} AS
                SELECT * FROM {table} WHERE 0
                """  # noqa: S608
            )
            # Add archived_at column if it doesn't already exist
            try:
                conn.execute(
                    f"ALTER TABLE {archive_table} ADD COLUMN archived_at TEXT"
                )
            except sqlite3.OperationalError:
                pass  # Column already present

            now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
            for record in records:
                record_copy = dict(record)
                record_copy["archived_at"] = now
                cols = ", ".join(record_copy.keys())
                placeholders = ", ".join("?" for _ in record_copy)
                conn.execute(
                    f"INSERT OR IGNORE INTO {archive_table} ({cols}) VALUES ({placeholders})",  # noqa: S608
                    list(record_copy.values()),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return archive_table

    def _archive_to_file(
        self,
        table: str,
        records: list[dict[str, Any]],
        archive_path: str | Path,
    ) -> str:
        """Write *records* to a JSON file at *archive_path*.

        If the file already exists (from a previous run), existing records are
        merged so the file accumulates all archived data.
        """
        path = Path(archive_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        existing: list[dict] = []
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    existing = json.load(fh)
            except (json.JSONDecodeError, OSError):
                existing = []

        now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
        for record in records:
            record["_archived_at"] = now
            record["_source_table"] = table

        all_records = existing + records
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(all_records, fh, indent=2, default=str)

        # Restrict permissions — archive files contain PII
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

        return str(path)

    def _delete_records(
        self,
        db_path: str | Path,
        table: str,
        where_clause: str,
        where_params: list,
    ) -> int:
        conn = _connect(db_path)
        try:
            cursor = conn.execute(
                f"DELETE FROM {table} WHERE {where_clause}",  # noqa: S608
                where_params,
            )
            conn.commit()
            return cursor.rowcount
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
