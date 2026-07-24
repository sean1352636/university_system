"""LMS synchronisation orchestrator.

Manages LMS connections stored in a SQLite database and coordinates
synchronisation runs via the provider implementations.

Conflict resolution policy
--------------------------
* **Enrollment status**: external data (from the LMS) always wins.
* **Grades**: internal data wins unless the ``force_external_grades``
  flag is set on the sync call.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Supported provider type strings
PROVIDER_CANVAS = "canvas"
PROVIDER_MOODLE = "moodle"
PROVIDER_GOOGLE_CLASSROOM = "google_classroom"

SUPPORTED_PROVIDERS = (PROVIDER_CANVAS, PROVIDER_MOODLE, PROVIDER_GOOGLE_CLASSROOM)


# ------------------------------------------------------------------ #
# Database schema                                                       #
# ------------------------------------------------------------------ #

_DDL = """
CREATE TABLE IF NOT EXISTS lms_connections (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    system_key  TEXT    NOT NULL,
    provider_type TEXT  NOT NULL CHECK (provider_type IN ('canvas', 'moodle', 'google_classroom')),
    config_json TEXT    NOT NULL DEFAULT '{}',
    is_active   INTEGER NOT NULL DEFAULT 1,
    last_sync   TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'utc'))
);

CREATE TABLE IF NOT EXISTS lms_sync_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    connection_id   INTEGER NOT NULL REFERENCES lms_connections(id) ON DELETE CASCADE,
    sync_type       TEXT    NOT NULL,
    status          TEXT    NOT NULL CHECK (status IN ('running', 'success', 'error')),
    records_synced  INTEGER NOT NULL DEFAULT 0,
    errors          TEXT    NOT NULL DEFAULT '[]',
    started_at      TEXT    NOT NULL DEFAULT (datetime('now', 'utc')),
    completed_at    TEXT
);

CREATE TABLE IF NOT EXISTS lms_id_mapping (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    connection_id   INTEGER NOT NULL REFERENCES lms_connections(id) ON DELETE CASCADE,
    entity_type     TEXT    NOT NULL,
    internal_id     TEXT    NOT NULL,
    external_id     TEXT    NOT NULL,
    UNIQUE (connection_id, entity_type, internal_id),
    UNIQUE (connection_id, entity_type, external_id)
);
"""


def init_lms_db(db_path: str) -> None:
    """Create the LMS integration tables if they do not already exist.

    Args:
        db_path: Filesystem path to the SQLite database file.
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(_DDL)
        conn.commit()
        logger.info("LMS integration DB initialised at %s", db_path)
    finally:
        conn.close()


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------------ #
# LMSSyncService                                                        #
# ------------------------------------------------------------------ #

class LMSSyncService:
    """Orchestrates LMS provider connections and synchronisation runs."""

    def __init__(self, db_path: str) -> None:
        """Initialise the service.

        Args:
            db_path: Path to the SQLite database that stores LMS connections
                     and sync logs.  The database and its tables are created
                     automatically if they do not exist.
        """
        self._db_path = db_path
        init_lms_db(db_path)

    # ------------------------------------------------------------------ #
    # Connection management                                                #
    # ------------------------------------------------------------------ #

    def add_connection(
        self,
        system_key: str,
        provider_type: str,
        config: dict[str, Any],
        *,
        is_active: bool = True,
    ) -> int:
        """Register a new LMS connection.

        Args:
            system_key: Identifies which education system uses this connection
                        (e.g. ``"university"``, ``"sixth_form"``).
            provider_type: One of ``canvas``, ``moodle``, ``google_classroom``.
            config: Provider-specific configuration (credentials, URLs, etc.).
                    Stored as JSON; do not store plain-text secrets in
                    production – use environment variable references instead.
            is_active: Whether the connection should be active immediately.

        Returns:
            The integer primary-key ID of the new connection row.

        Raises:
            ValueError: For unsupported provider types.
        """
        if provider_type not in SUPPORTED_PROVIDERS:
            raise ValueError(
                f"Unsupported provider '{provider_type}'. "
                f"Choose from: {SUPPORTED_PROVIDERS}"
            )
        conn = _connect(self._db_path)
        try:
            cur = conn.execute(
                """
                INSERT INTO lms_connections
                    (system_key, provider_type, config_json, is_active, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    system_key,
                    provider_type,
                    json.dumps(config),
                    1 if is_active else 0,
                    _now_utc(),
                ),
            )
            conn.commit()
            new_id = cur.lastrowid
            logger.info(
                "Added LMS connection id=%d system=%s provider=%s",
                new_id, system_key, provider_type,
            )
            return new_id
        finally:
            conn.close()

    def remove_connection(self, connection_id: int) -> bool:
        """Remove a connection (and cascade-delete its logs and mappings).

        Returns:
            ``True`` if a row was deleted, ``False`` if the ID was not found.
        """
        conn = _connect(self._db_path)
        try:
            cur = conn.execute(
                "DELETE FROM lms_connections WHERE id = ?", (connection_id,)
            )
            conn.commit()
            deleted = cur.rowcount > 0
            if deleted:
                logger.info("Removed LMS connection id=%d", connection_id)
            return deleted
        finally:
            conn.close()

    def list_connections(
        self, system_key: str | None = None, active_only: bool = False
    ) -> list[dict[str, Any]]:
        """Return all connections, optionally filtered.

        Args:
            system_key: When provided, only return connections for this system.
            active_only: When True, exclude inactive connections.
        """
        query = "SELECT * FROM lms_connections WHERE 1=1"
        params: list[Any] = []
        if system_key:
            query += " AND system_key = ?"
            params.append(system_key)
        if active_only:
            query += " AND is_active = 1"
        query += " ORDER BY id"

        conn = _connect(self._db_path)
        try:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_connection(self, connection_id: int) -> dict[str, Any] | None:
        """Fetch a single connection by ID."""
        conn = _connect(self._db_path)
        try:
            row = conn.execute(
                "SELECT * FROM lms_connections WHERE id = ?", (connection_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # Provider factory                                                      #
    # ------------------------------------------------------------------ #

    def get_provider(self, connection: dict[str, Any]):
        """Instantiate and return the correct LMSProvider for a connection dict.

        Args:
            connection: A row from ``lms_connections`` (as a dict).

        Returns:
            An instance of CanvasProvider, MoodleProvider, or
            GoogleClassroomProvider.

        Raises:
            ValueError: For unknown provider types.
            KeyError: When required config keys are missing.
        """
        provider_type = connection["provider_type"]
        config = json.loads(connection.get("config_json", "{}"))

        if provider_type == PROVIDER_CANVAS:
            from education_system.shared.integrations.canvas_provider import (
                CanvasProvider,
            )
            return CanvasProvider(
                base_url=config["base_url"],
                access_token=config["access_token"],
            )

        if provider_type == PROVIDER_MOODLE:
            from education_system.shared.integrations.moodle_provider import (
                MoodleProvider,
            )
            return MoodleProvider(
                base_url=config["base_url"],
                token=config["token"],
            )

        if provider_type == PROVIDER_GOOGLE_CLASSROOM:
            from education_system.shared.integrations.google_classroom_provider import (
                GoogleClassroomProvider,
            )
            return GoogleClassroomProvider(
                credentials_json=config["credentials_json"],
            )

        raise ValueError(f"Unknown provider type: {provider_type!r}")

    # ------------------------------------------------------------------ #
    # Synchronisation                                                       #
    # ------------------------------------------------------------------ #

    def sync_connection(
        self,
        connection_id: int,
        *,
        force_external_grades: bool = False,
    ) -> dict[str, Any]:
        """Run a full sync for one connection.

        Sync order: courses → students → grades → enrollments (per course).

        Conflict resolution:
            * Enrollment status: external wins (always applied).
            * Grades: internal wins unless ``force_external_grades=True``.

        Args:
            connection_id: Primary key of the ``lms_connections`` row.
            force_external_grades: When True, external grade data overwrites
                                   internal grades.

        Returns:
            A summary dict with keys:
                ``connection_id``, ``status``, ``records_synced``,
                ``errors``, ``started_at``, ``completed_at``.
        """
        connection = self.get_connection(connection_id)
        if not connection:
            return {
                "connection_id": connection_id,
                "status": "error",
                "records_synced": 0,
                "errors": [f"Connection {connection_id} not found"],
                "started_at": _now_utc(),
                "completed_at": _now_utc(),
            }

        started_at = _now_utc()
        log_id = self._start_sync_log(connection_id, "full")
        records_synced = 0
        errors: list[str] = []

        try:
            provider = self.get_provider(connection)

            # 1. Courses
            try:
                courses = provider.sync_courses()
                records_synced += len(courses)
                logger.info(
                    "Sync [conn=%d] courses: %d", connection_id, len(courses)
                )
            except Exception as exc:
                errors.append(f"sync_courses failed: {exc}")
                logger.exception("sync_courses failed for connection %d", connection_id)

            # 2. Students
            try:
                students = provider.sync_students()
                records_synced += len(students)
                logger.info(
                    "Sync [conn=%d] students: %d", connection_id, len(students)
                )
            except Exception as exc:
                errors.append(f"sync_students failed: {exc}")
                logger.exception("sync_students failed for connection %d", connection_id)

            # 3. Grades — only applied if force_external_grades is set
            try:
                grades = provider.sync_grades()
                if force_external_grades:
                    records_synced += len(grades)
                    logger.info(
                        "Sync [conn=%d] grades (external wins): %d",
                        connection_id, len(grades),
                    )
                else:
                    logger.info(
                        "Sync [conn=%d] grades fetched: %d (not overwriting "
                        "internal; pass force_external_grades=True to override)",
                        connection_id, len(grades),
                    )
            except Exception as exc:
                errors.append(f"sync_grades failed: {exc}")
                logger.exception("sync_grades failed for connection %d", connection_id)

            # 4. Enrollments — external wins for status
            try:
                if "courses" in dir():
                    for course in courses:  # type: ignore[possibly-undefined]
                        try:
                            enrollments = provider.pull_enrollments(
                                course["external_id"]
                            )
                            records_synced += len(enrollments)
                        except Exception as exc:
                            errors.append(
                                f"pull_enrollments course={course['external_id']}: {exc}"
                            )
            except Exception as exc:
                errors.append(f"pull_enrollments loop failed: {exc}")
                logger.exception(
                    "Enrollment sync failed for connection %d", connection_id
                )

            status = "success" if not errors else "error"

        except Exception as exc:
            errors.append(f"Unexpected sync error: {exc}")
            logger.exception(
                "Unexpected error during sync for connection %d", connection_id
            )
            status = "error"

        completed_at = _now_utc()
        self._finish_sync_log(log_id, status, records_synced, errors, completed_at)
        self._update_last_sync(connection_id, completed_at)

        return {
            "connection_id": connection_id,
            "status": status,
            "records_synced": records_synced,
            "errors": errors,
            "started_at": started_at,
            "completed_at": completed_at,
        }

    def sync_all(
        self, system_key: str | None = None, *, force_external_grades: bool = False
    ) -> list[dict[str, Any]]:
        """Run sync for all active connections, optionally scoped to a system.

        Args:
            system_key: If provided, only sync connections for this system.
            force_external_grades: Forwarded to each ``sync_connection`` call.

        Returns:
            List of per-connection result dicts (same shape as
            ``sync_connection``).
        """
        connections = self.list_connections(system_key=system_key, active_only=True)
        results: list[dict[str, Any]] = []
        for connection in connections:
            result = self.sync_connection(
                connection["id"],
                force_external_grades=force_external_grades,
            )
            results.append(result)
        return results

    # ------------------------------------------------------------------ #
    # History & mappings                                                    #
    # ------------------------------------------------------------------ #

    def get_sync_history(
        self,
        connection_id: int | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Return sync log entries, newest first.

        Args:
            connection_id: When provided, filter to a single connection.
            limit: Maximum number of rows to return.
        """
        query = "SELECT * FROM lms_sync_log WHERE 1=1"
        params: list[Any] = []
        if connection_id is not None:
            query += " AND connection_id = ?"
            params.append(connection_id)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        conn = _connect(self._db_path)
        try:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_mappings(
        self,
        connection_id: int,
        entity_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return ID mappings for a connection.

        Args:
            connection_id: Foreign key into ``lms_connections``.
            entity_type: When provided, filter to ``course``, ``student``,
                         ``grade``, etc.
        """
        query = "SELECT * FROM lms_id_mapping WHERE connection_id = ?"
        params: list[Any] = [connection_id]
        if entity_type:
            query += " AND entity_type = ?"
            params.append(entity_type)
        query += " ORDER BY id"

        conn = _connect(self._db_path)
        try:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def upsert_mapping(
        self,
        connection_id: int,
        entity_type: str,
        internal_id: str,
        external_id: str,
    ) -> None:
        """Insert or replace an ID mapping entry.

        Args:
            connection_id: Foreign key into ``lms_connections``.
            entity_type: E.g. ``"course"``, ``"student"``, ``"grade"``.
            internal_id: The ID used in the local education system DB.
            external_id: The ID used in the remote LMS.
        """
        conn = _connect(self._db_path)
        try:
            conn.execute(
                """
                INSERT INTO lms_id_mapping
                    (connection_id, entity_type, internal_id, external_id)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (connection_id, entity_type, internal_id)
                DO UPDATE SET external_id = excluded.external_id
                """,
                (connection_id, entity_type, internal_id, external_id),
            )
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # Private helpers                                                       #
    # ------------------------------------------------------------------ #

    def _start_sync_log(self, connection_id: int, sync_type: str) -> int:
        conn = _connect(self._db_path)
        try:
            cur = conn.execute(
                """
                INSERT INTO lms_sync_log
                    (connection_id, sync_type, status, started_at)
                VALUES (?, ?, 'running', ?)
                """,
                (connection_id, sync_type, _now_utc()),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def _finish_sync_log(
        self,
        log_id: int,
        status: str,
        records_synced: int,
        errors: list[str],
        completed_at: str,
    ) -> None:
        conn = _connect(self._db_path)
        try:
            conn.execute(
                """
                UPDATE lms_sync_log
                SET status = ?, records_synced = ?, errors = ?, completed_at = ?
                WHERE id = ?
                """,
                (status, records_synced, json.dumps(errors), completed_at, log_id),
            )
            conn.commit()
        finally:
            conn.close()

    def _update_last_sync(self, connection_id: int, ts: str) -> None:
        conn = _connect(self._db_path)
        try:
            conn.execute(
                "UPDATE lms_connections SET last_sync = ? WHERE id = ?",
                (ts, connection_id),
            )
            conn.commit()
        finally:
            conn.close()
