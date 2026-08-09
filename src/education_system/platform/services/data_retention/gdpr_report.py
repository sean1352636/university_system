"""GDPR Data Subject Access Request (DSAR) and erasure processing.

``generate_dsar_report(email)`` searches all four system databases for records
linked to a given email address and returns a structured JSON-serialisable
summary of every piece of data held.

``process_erasure_request(email)`` anonymizes / deletes all PII for that
subject across all systems and records the request in the retention DB.
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from education_system.platform.governance.security.fail_closed import alert_security_failure

from .anonymizer import Anonymizer
from .models import _connect as _retention_connect, get_retention_db_path, init_retention_db
from .verification import subject_reference

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System database registry
# ---------------------------------------------------------------------------

def _discover_system_dbs() -> dict[str, Path]:
    """Resolve every system database from its own paths module.

    These were previously hand-built relative paths
    (``.../post_18/university_system/data/db_files/student_records.db`` and
    ``.../education_system/data/db_files/auth.db``). Neither has existed since
    the tree moved under ``var/``, and a non-existent path does not
    error — ``_open_db`` simply returns None and the table is skipped. The
    visible effect was that every DSAR returned "0 records found" and every
    erasure reported "completed" having anonymised nothing.

    Deriving from ``education_system.paths`` means a future layout change moves
    these with it. All five systems are included because the other four hold
    children's records; covering only university and auth left four systems'
    worth of subject data outside both the access and the erasure workflow
    entirely.
    """
    discovered: dict[str, Path] = {}

    try:
        from education_system.paths import PLATFORM_AUTH_DB_FILE, SYSTEM_DB_PATHS
    except ImportError:  # pragma: no cover — education_system.paths always imports
        logger.error("education_system.paths unavailable; DSAR scope is empty")
        return discovered

    discovered["auth"] = Path(PLATFORM_AUTH_DB_FILE)
    for system, db_path in SYSTEM_DB_PATHS.items():
        discovered[system] = Path(db_path)

    return discovered


def assert_dsar_scope_resolves() -> list[str]:
    """Return the systems whose DSAR database path does not exist on disk.

    A missing path is not an error at import time — a deployment may not run
    every system — but it *is* something a subject-access request must not
    silently skip. The security suite calls this and fails if a system that is
    installed has an unresolvable database, which is what turned the previous
    stale paths into an invisible no-op.
    """
    return [system for system, path in _SYSTEM_DBS.items() if not Path(path).exists()]


_SYSTEM_DBS: dict[str, Path] = _discover_system_dbs()

# Email column names to search in each table
_EMAIL_COLUMNS = {"email", "email_address", "contact_email", "username"}

# Tables known to contain subject-linked data (searched by email column)
_SUBJECT_TABLES: dict[str, list[str]] = {
    "university": [
        "students", "user_accounts", "contact_details", "applications",
        "alumni", "parent_contacts",
    ],
    "auth": [
        "users",
    ],
    # The four school systems hold children's records and were previously
    # outside DSAR scope entirely. Tables absent from a given system are
    # skipped by _table_exists_conn, so listing the superset is safe.
    "nursery": [
        "children", "pupils", "parent_contacts", "staff", "user_accounts",
    ],
    "primary": [
        "pupils", "students", "parent_contacts", "staff", "user_accounts",
    ],
    "secondary": [
        "pupils", "students", "parent_contacts", "staff", "user_accounts",
    ],
    "sixth_form": [
        "students", "applications", "parent_contacts", "staff",
        "user_accounts", "alumni",
    ],
}

# Fields considered PII for erasure purposes
_PII_FIELDS_BY_TABLE: dict[str, list[str]] = {
    "students":        ["email", "email_address", "first_name", "last_name",
                        "date_of_birth", "address", "phone", "phone_number"],
    "pupils":          ["email", "email_address", "first_name", "last_name",
                        "date_of_birth", "address", "phone"],
    "user_accounts":   ["email", "email_address", "first_name", "last_name",
                        "phone"],
    "users":           ["email", "first_name", "last_name", "phone"],
    "staff":           ["email", "email_address", "first_name", "last_name",
                        "date_of_birth", "address", "phone"],
    "parent_contacts": ["email", "email_address", "name", "first_name",
                        "last_name", "phone", "address"],
    "applications":    ["email", "email_address", "first_name", "last_name",
                        "date_of_birth", "address", "phone"],
    "alumni":          ["email", "email_address", "first_name", "last_name",
                        "phone", "address"],
    "contact_details": ["email", "email_address", "phone", "address"],
    "admissions":      ["email", "email_address", "first_name", "last_name",
                        "date_of_birth"],
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _open_db(db_path: Path) -> sqlite3.Connection | None:
    if not db_path.exists():
        return None
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _get_table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()  # noqa: S608
        return [r["name"] for r in rows]
    except Exception:
        return []


def _table_exists_conn(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def _find_email_column(columns: list[str]) -> str | None:
    for col in columns:
        if col.lower() in _EMAIL_COLUMNS:
            return col
    return None


def _search_table(
    conn: sqlite3.Connection,
    table: str,
    email: str,
) -> list[dict]:
    if not _table_exists_conn(conn, table):
        return []
    columns = _get_table_columns(conn, table)
    email_col = _find_email_column(columns)
    if not email_col:
        return []
    try:
        rows = conn.execute(
            f"SELECT * FROM {table} WHERE LOWER({email_col}) = LOWER(?)",  # noqa: S608
            (email,),
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception as exc:
        logger.warning("Search failed on %s: %s", table, exc)
        return []


def _redact_sensitive(records: list[dict]) -> list[dict]:
    """Strip password hashes and secrets before returning in DSAR report."""
    sensitive_keys = {"password", "password_hash", "hashed_password", "salt",
                      "legacy_salt", "mfa_secret", "totp_secret", "token"}
    clean = []
    for record in records:
        clean.append({
            k: "***REDACTED***" if k.lower() in sensitive_keys else v
            for k, v in record.items()
        })
    return clean


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_dsar_report(email: str) -> dict[str, Any]:
    """Build a Data Subject Access Request report for *email*.

    Searches all 4 system databases plus the shared auth DB for any record
    linked to the given email address.

    Returns
    -------
    A JSON-serialisable dict containing::

        {
            "email": ...,
            "generated_at": ...,
            "systems": {
                "university": {"table_name": [row, ...]},
                ...
            },
            "total_records": N,
        }
    """
    report: dict[str, Any] = {
        "email": email,
        "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
        "systems": {},
        "total_records": 0,
    }

    for system_key, db_path in _SYSTEM_DBS.items():
        conn = _open_db(db_path)
        if conn is None:
            continue
        try:
            system_data: dict[str, list[dict]] = {}
            for table in _SUBJECT_TABLES.get(system_key, []):
                records = _search_table(conn, table, email)
                if records:
                    system_data[table] = _redact_sensitive(records)
                    report["total_records"] += len(records)
            if system_data:
                report["systems"][system_key] = system_data
        finally:
            conn.close()

    logger.info(
        "DSAR report for %s: found %d records across %d systems",
        email, report["total_records"], len(report["systems"]),
    )
    return report


def process_erasure_request(
    email: str,
    processed_by: str = "system",
    retention_db_path: str | Path | None = None,
) -> dict[str, Any]:
    """Anonymize / delete all PII held for *email* across all systems.

    Records a ``data_subject_requests`` entry in the retention database so
    there is an auditable trail without retaining PII.

    Returns
    -------
    A JSON-serialisable dict summarising actions taken::

        {
            "email": ...,
            "processed_at": ...,
            "request_id": N,
            "systems_affected": [...],
            "records_anonymized": N,
            "records_deleted": N,
            "details": [...],
        }
    """
    init_retention_db(retention_db_path)
    r_db = retention_db_path or get_retention_db_path()
    anonymizer = Anonymizer()

    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
    systems_affected: list[str] = []
    total_anonymized = 0
    total_deleted = 0
    details: list[dict] = []
    erasure_failures: list[dict] = []

    # ── Create pending request record ────────────────────────────────────
    conn = _retention_connect(r_db)
    try:
        conn.execute(
            """
            INSERT INTO data_subject_requests
                (subject_email, request_type, status, requested_at, processed_by)
            VALUES (?, 'erasure', 'in_progress', ?, ?)
            """,
            (email, now, processed_by),
        )
        conn.commit()
        request_id = conn.execute(
            "SELECT last_insert_rowid()"
        ).fetchone()[0]
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    # ── Process each system ──────────────────────────────────────────────
    for system_key, db_path in _SYSTEM_DBS.items():
        s_conn = _open_db(db_path)
        if s_conn is None:
            continue

        try:
            system_affected = False
            for table in _SUBJECT_TABLES.get(system_key, []):
                if not _table_exists_conn(s_conn, table):
                    continue
                columns = _get_table_columns(s_conn, table)
                email_col = _find_email_column(columns)
                if not email_col:
                    continue

                rows = s_conn.execute(
                    f"SELECT id FROM {table} WHERE LOWER({email_col}) = LOWER(?)",  # noqa: S608
                    (email,),
                ).fetchall()

                for row in rows:
                    record_id = row["id"]
                    pii_fields = _PII_FIELDS_BY_TABLE.get(table, [])
                    # Only anonymize fields that actually exist in this table
                    fields_present = [f for f in pii_fields if f in columns]
                    result = anonymizer.anonymize_record(
                        table,
                        record_id,
                        fields_present or None,
                        db_path=db_path,
                    )
                    total_anonymized += 1
                    details.append(
                        {"system": system_key, "table": table, **result}
                    )
                    system_affected = True
        finally:
            s_conn.close()

        if system_affected:
            systems_affected.append(system_key)

    # ── Handle auth sessions — delete rather than anonymize ──────────────
    auth_db = _SYSTEM_DBS["auth"]
    if auth_db.exists():
        try:
            a_conn = sqlite3.connect(str(auth_db))
            try:
                # Find user_id for this email in the users table
                user_row = a_conn.execute(
                    "SELECT id FROM users WHERE LOWER(email) = LOWER(?)", (email,)
                ).fetchone()
                if user_row:
                    user_id = user_row[0]
                    cursor = a_conn.execute(
                        "DELETE FROM sessions WHERE user_id = ?", (user_id,)
                    )
                    deleted_sessions = cursor.rowcount
                    a_conn.commit()
                    if deleted_sessions:
                        total_deleted += deleted_sessions
                        details.append({
                            "system": "auth",
                            "table": "sessions",
                            "action": "deleted",
                            "count": deleted_sessions,
                        })
            finally:
                a_conn.close()
        except Exception as exc:
            # Sessions are the subject's live access. Failing to revoke them
            # while reporting the erasure "completed" would leave the person
            # both erased and still logged in, so this is recorded as a
            # failure rather than logged and forgotten.
            alert_security_failure(
                "gdpr.erasure.sessions",
                f"Could not revoke auth sessions during erasure: {exc}",
                exc=exc,
            )
            erasure_failures.append({"system": "auth", "stage": "sessions", "error": str(exc)})

    # ── Finalise request record ───────────────────────────────────────────
    # The status reflects what actually happened. Marking a partially failed
    # erasure 'completed' is how an unerased record becomes invisible.
    completed_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
    final_status = "completed" if not erasure_failures else "in_progress"
    conn = _retention_connect(r_db)
    try:
        conn.execute(
            """
            UPDATE data_subject_requests
            SET status = ?,
                systems_affected = ?,
                completed_at = ?,
                subject_email = ?,
                subject_name = NULL
            WHERE id = ?
            """,
            # Overwrite the address with its keyed pseudonym now the erasure
            # has run: keeping it would make this table the last surviving
            # copy of every address the estate was asked to forget, while the
            # pseudonym still answers "did we already process this person?".
            (final_status, ", ".join(systems_affected), completed_at,
             subject_reference(email), request_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    result = {
        # The pseudonym, not the address: this dict is logged, returned over
        # the API and often written to a report file.
        "subject_ref": subject_reference(email),
        "processed_at": completed_at,
        "request_id": request_id,
        "status": final_status,
        "systems_affected": systems_affected,
        "records_anonymized": total_anonymized,
        "records_deleted": total_deleted,
        "failures": erasure_failures,
        "details": details,
    }
    logger.info(
        "Erasure request %d (%s) %s: %d anonymized, %d deleted, %d failure(s)",
        request_id, result["subject_ref"], final_status,
        total_anonymized, total_deleted, len(erasure_failures),
    )
    return result
