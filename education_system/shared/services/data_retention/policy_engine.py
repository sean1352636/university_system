"""Retention policy execution engine.

``RetentionPolicyEngine`` loads active policies from the shared retention
database and applies them against each system's live database.

Each policy specifies:
  - entity_type   — a logical name that maps to a (db_path, table, date_column)
  - retention_days — how old records must be before action is taken
  - action         — 'archive', 'anonymize', or 'delete'
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .anonymizer import Anonymizer
from .archiver import Archiver
from .models import _connect as _retention_connect, init_retention_db, get_retention_db_path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Entity-type registry
# ---------------------------------------------------------------------------
# Maps entity_type → list of dicts describing affected tables.
# Each entry: {db_path_key, table, date_column, extra_where (optional)}
# db_path_key resolves to an actual path via _resolve_db().

_ENTITY_MAP: dict[str, list[dict[str, Any]]] = {
    "graduated_students": [
        {
            "system": "sixth_form",
            "table": "students",
            "date_column": "graduation_date",
        },
        {
            "system": "university",
            "table": "students",
            "date_column": "graduation_date",
        },
        {
            "system": "secondary",
            "table": "students",
            "date_column": "leaving_date",
        },
        {
            "system": "primary",
            "table": "pupils",
            "date_column": "leaving_date",
        },
    ],
    "attendance_records": [
        {"system": "sixth_form",    "table": "attendance",       "date_column": "date"},
        {"system": "university", "table": "attendance",       "date_column": "date"},
        {"system": "secondary",  "table": "attendance",       "date_column": "date"},
        {"system": "primary",    "table": "attendance",       "date_column": "date"},
    ],
    "chat_messages": [
        {"system": "university", "table": "chat_messages",    "date_column": "sent_at"},
        {"system": "sixth_form",    "table": "messages",         "date_column": "sent_at"},
    ],
    "session_data": [
        {"system": "auth",  "table": "sessions",         "date_column": "expires_at"},
    ],
    "audit_logs": [
        {"system": "sixth_form",    "table": "audit_log",        "date_column": "timestamp"},
        {"system": "university", "table": "audit_log",        "date_column": "timestamp"},
        {"system": "secondary",  "table": "audit_log",        "date_column": "created_at"},
        {"system": "primary",    "table": "audit_log",        "date_column": "created_at"},
    ],
    "temporary_files": [
        {"system": "sixth_form",    "table": "temp_files",       "date_column": "created_at"},
        {"system": "university", "table": "temp_files",       "date_column": "created_at"},
    ],
}

# ---------------------------------------------------------------------------
# DB path resolver
# ---------------------------------------------------------------------------

_shared_root = Path(__file__).resolve().parent.parent.parent.parent  # education_system/shared
_education_root = _shared_root.parent                                  # education_system/


def _resolve_db(system: str) -> Path | None:
    """Return the filesystem path for a known system's database."""
    mapping = {
        "university": _education_root / "post_18" / "university_system" / "data" / "db_files" / "student_records.db",
        "auth":       _shared_root                          / "data" / "db_files" / "auth.db",
    }
    return mapping.get(system)


def _table_exists(db_path: Path, table: str) -> bool:
    if not db_path.exists():
        return False
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            return row is not None
        finally:
            conn.close()
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class RetentionPolicyEngine:
    """Load and execute GDPR data retention policies.

    Parameters
    ----------
    retention_db_path:
        Path to the shared retention SQLite database.  Created (with default
        policies) on first instantiation if it does not exist.
    """

    def __init__(self, retention_db_path: str | Path | None = None):
        self._db_path = Path(retention_db_path) if retention_db_path else get_retention_db_path()
        init_retention_db(self._db_path)
        self._anonymizer = Anonymizer()
        self._archiver = Archiver()

    # ------------------------------------------------------------------
    # Policy CRUD
    # ------------------------------------------------------------------

    def get_active_policies(self) -> list[dict]:
        conn = _retention_connect(self._db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM retention_policies WHERE is_active = 1 ORDER BY id"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_all_policies(self) -> list[dict]:
        conn = _retention_connect(self._db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM retention_policies ORDER BY id"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def add_policy(
        self,
        entity_type: str,
        retention_days: int,
        action: str,
        *,
        system_key: str = "all",
        description: str = "",
    ) -> dict:
        now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
        conn = _retention_connect(self._db_path)
        try:
            conn.execute(
                """
                INSERT INTO retention_policies
                    (entity_type, system_key, retention_days, action, description,
                     is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (entity_type, system_key, retention_days, action, description, now, now),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM retention_policies WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def update_policy(self, policy_id: int, **kwargs) -> dict | None:
        set_parts: list[str] = []
        values: list = []
        for col in (
            "action", "description", "entity_type", "is_active",
            "retention_days", "system_key",
        ):
            if col in kwargs:
                set_parts.append(f"{col} = ?")
                values.append(kwargs[col])
        if not set_parts:
            raise ValueError("No valid fields provided to update.")
        now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
        set_parts.append("updated_at = ?")
        values.append(now)
        set_clause = ", ".join(set_parts)
        values.append(policy_id)
        conn = _retention_connect(self._db_path)
        try:
            conn.execute(
                f"UPDATE retention_policies SET {set_clause} WHERE id = ?",  # noqa: S608
                values,
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM retention_policies WHERE id = ?", (policy_id,)
            ).fetchone()
            return dict(row) if row else None
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def deactivate_policy(self, policy_id: int) -> bool:
        updated = self.update_policy(policy_id, is_active=0)
        return updated is not None

    # ------------------------------------------------------------------
    # Job history
    # ------------------------------------------------------------------

    def get_job_history(self, limit: int = 50) -> list[dict]:
        conn = _retention_connect(self._db_path)
        try:
            rows = conn.execute(
                """
                SELECT j.*, p.entity_type, p.action
                FROM retention_jobs j
                JOIN retention_policies p ON p.id = j.policy_id
                ORDER BY j.id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def run_policy(self, policy_id: int) -> dict:
        """Execute a single policy by ID. Returns the job record."""
        conn = _retention_connect(self._db_path)
        try:
            row = conn.execute(
                "SELECT * FROM retention_policies WHERE id = ?", (policy_id,)
            ).fetchone()
            if not row:
                raise ValueError(f"Policy {policy_id} not found.")
            policy = dict(row)
        finally:
            conn.close()

        job_id = self._create_job(policy_id)
        started_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
        self._update_job(job_id, status="running", started_at=started_at)

        try:
            total_affected = self._execute_policy(policy)
            completed_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
            self._update_job(
                job_id,
                status="completed",
                completed_at=completed_at,
                records_affected=total_affected,
            )
            logger.info(
                "Policy %d (%s/%s) completed: %d records affected",
                policy_id, policy["entity_type"], policy["action"], total_affected,
            )
        except Exception as exc:
            completed_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
            self._update_job(
                job_id,
                status="failed",
                completed_at=completed_at,
                error_message=str(exc),
            )
            logger.error("Policy %d failed: %s", policy_id, exc)

        return self._get_job(job_id)

    def run_all_policies(self) -> list[dict]:
        """Run all active policies sequentially. Returns list of job records."""
        policies = self.get_active_policies()
        results = []
        for policy in policies:
            result = self.run_policy(policy["id"])
            results.append(result)
        return results

    # ------------------------------------------------------------------
    # Internal execution helpers
    # ------------------------------------------------------------------

    def _execute_policy(self, policy: dict) -> int:
        """Apply the policy to all relevant tables.  Returns total rows affected."""
        entity_type = policy["entity_type"]
        system_key = policy.get("system_key", "all")
        retention_days = policy["retention_days"]
        action = policy["action"]

        cutoff = (
            datetime.utcnow() - timedelta(days=retention_days)
        ).strftime("%Y-%m-%d")

        targets = _ENTITY_MAP.get(entity_type, [])
        if not targets:
            logger.warning("No entity map entry for '%s', skipping.", entity_type)
            return 0

        total = 0
        for target in targets:
            # Filter by system_key if not 'all'
            if system_key != "all" and target.get("system") != system_key:
                continue

            db_path = _resolve_db(target["system"])
            if db_path is None:
                continue
            if not _table_exists(db_path, target["table"]):
                continue

            table = target["table"]
            date_col = target["date_column"]
            where_clause = f"{date_col} < ?"
            where_params = [cutoff]

            try:
                affected = self._apply_action(
                    action, db_path, table, where_clause, where_params
                )
                total += affected
                logger.info(
                    "Policy entity=%s system=%s table=%s action=%s: %d rows",
                    entity_type, target["system"], table, action, affected,
                )
            except Exception as exc:
                logger.error(
                    "Error processing %s.%s: %s", target["system"], table, exc
                )

        return total

    def _apply_action(
        self,
        action: str,
        db_path: Path,
        table: str,
        where_clause: str,
        where_params: list,
    ) -> int:
        if action == "delete":
            conn = sqlite3.connect(str(db_path))
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

        elif action == "anonymize":
            result = self._anonymizer.anonymize_where(
                table,
                where_clause,
                where_params,
                db_path=db_path,
            )
            return result.get("count", 0)

        elif action == "archive":
            result = self._archiver.archive_records(
                db_path, table, where_clause, where_params
            )
            return result.get("records_archived", 0)

        else:
            raise ValueError(f"Unknown action: {action}")

    # ------------------------------------------------------------------
    # Job management
    # ------------------------------------------------------------------

    def _create_job(self, policy_id: int) -> int:
        conn = _retention_connect(self._db_path)
        try:
            conn.execute(
                "INSERT INTO retention_jobs (policy_id, status) VALUES (?, 'pending')",
                (policy_id,),
            )
            conn.commit()
            job_id = conn.execute(
                "SELECT last_insert_rowid()"
            ).fetchone()[0]
            return job_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _update_job(self, job_id: int, **kwargs) -> None:
        allowed = {"status", "started_at", "completed_at",
                   "records_affected", "error_message"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        conn = _retention_connect(self._db_path)
        try:
            conn.execute(
                f"UPDATE retention_jobs SET {set_clause} WHERE id = ?",  # noqa: S608
                [*fields.values(), job_id],
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _get_job(self, job_id: int) -> dict:
        conn = _retention_connect(self._db_path)
        try:
            row = conn.execute(
                "SELECT * FROM retention_jobs WHERE id = ?", (job_id,)
            ).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()
