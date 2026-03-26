"""PII anonymization utilities for GDPR data retention.

The ``Anonymizer`` class rewrites specific fields of a record in-place,
replacing personal identifiers with non-reversible placeholders while
keeping statistically useful data (grades, counts, dates-at-year-level).
"""

import hashlib
import logging
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Field-level strategies
# ---------------------------------------------------------------------------

# Maps a canonical field name (lower-cased) to the strategy key to apply.
_FIELD_STRATEGY: dict[str, str] = {
    # Email variants
    "email": "email",
    "email_address": "email",
    "contact_email": "email",
    # Name variants
    "name": "name",
    "first_name": "name",
    "last_name": "name",
    "forename": "name",
    "surname": "name",
    "middle_name": "name",
    "full_name": "name",
    "preferred_name": "name",
    # Phone variants
    "phone": "phone",
    "phone_number": "phone",
    "mobile": "phone",
    "telephone": "phone",
    "contact_number": "phone",
    # DOB variants — keep year only
    "date_of_birth": "dob",
    "dob": "dob",
    "birth_date": "dob",
    # Address variants
    "address": "address",
    "address_line1": "address",
    "address_line2": "address",
    "street": "address",
    "postcode": "address",
    "zip_code": "address",
    "city": "address",
}


def _apply_strategy(strategy: str, original_value: Any) -> Any:
    """Return the anonymized replacement for *original_value*."""
    if original_value is None:
        return None

    if strategy == "email":
        # SHA-256 first 12 chars → deterministic but non-reversible
        digest = hashlib.sha256(str(original_value).encode()).hexdigest()[:12]
        return f"{digest}@redacted.edu"

    if strategy == "name":
        return "REDACTED"

    if strategy == "phone":
        return "XXXXXXXXXX"

    if strategy == "dob":
        # Preserve year only for age-cohort statistics
        raw = str(original_value)
        if len(raw) >= 4 and raw[:4].isdigit():
            return raw[:4]
        return "XXXX"

    if strategy == "address":
        return "REDACTED"

    # Unknown strategy — redact entirely
    return "REDACTED"


def _detect_strategy(field_name: str) -> str | None:
    """Guess strategy from field name; returns None if not a PII field."""
    return _FIELD_STRATEGY.get(field_name.lower())


# ---------------------------------------------------------------------------
# Anonymizer class
# ---------------------------------------------------------------------------

class Anonymizer:
    """Anonymize individual records in a SQLite database.

    Parameters
    ----------
    db_path:
        Path to the SQLite database containing the record to anonymize.
        If *None* the call-site must pass it explicitly.
    """

    def __init__(self, db_path: str | Path | None = None):
        self._db_path = db_path

    def _connect(self, db_path: str | Path | None = None) -> sqlite3.Connection:
        path = str(db_path or self._db_path)
        if not path:
            raise ValueError("db_path is required")
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def anonymize_record(
        self,
        table: str,
        record_id: int | str,
        fields_to_anonymize: list[str] | None = None,
        *,
        id_column: str = "id",
        db_path: str | Path | None = None,
    ) -> dict:
        """Anonymize PII fields on a single record.

        Parameters
        ----------
        table:
            The table name to update.
        record_id:
            Primary key value of the row to anonymize.
        fields_to_anonymize:
            Explicit list of column names to anonymize.  When *None* the
            method reads the table's column list and applies strategies to
            all columns whose names match a known PII pattern.
        id_column:
            Name of the primary key column (default: ``"id"``).
        db_path:
            Override the instance-level db_path.

        Returns
        -------
        dict with keys ``table``, ``record_id``, ``fields_updated``, ``status``.
        """
        conn = self._connect(db_path)
        try:
            # Discover columns if not supplied
            if fields_to_anonymize is None:
                cursor = conn.execute(f"PRAGMA table_info({table})")  # noqa: S608
                all_columns = [row["name"] for row in cursor.fetchall()]
                fields_to_anonymize = [
                    col for col in all_columns if _detect_strategy(col) is not None
                ]

            if not fields_to_anonymize:
                return {
                    "table": table,
                    "record_id": record_id,
                    "fields_updated": [],
                    "status": "no_pii_fields",
                }

            # Read current values
            row = conn.execute(
                f"SELECT * FROM {table} WHERE {id_column} = ?",  # noqa: S608
                (record_id,),
            ).fetchone()
            if row is None:
                return {
                    "table": table,
                    "record_id": record_id,
                    "fields_updated": [],
                    "status": "not_found",
                }

            # Build UPDATE
            set_clauses = []
            params: list[Any] = []
            fields_updated = []
            for field in fields_to_anonymize:
                original = row[field] if field in row.keys() else None
                strategy = _detect_strategy(field) or "name"
                new_value = _apply_strategy(strategy, original)
                set_clauses.append(f"{field} = ?")
                params.append(new_value)
                fields_updated.append(field)

            params.append(record_id)
            sql = (
                f"UPDATE {table} SET {', '.join(set_clauses)} "  # noqa: S608
                f"WHERE {id_column} = ?"
            )
            conn.execute(sql, params)
            conn.commit()

            logger.info(
                "Anonymized %s id=%s: fields=%s", table, record_id, fields_updated
            )
            return {
                "table": table,
                "record_id": record_id,
                "fields_updated": fields_updated,
                "status": "anonymized",
            }
        except Exception as exc:
            conn.rollback()
            logger.error(
                "Failed to anonymize %s id=%s: %s", table, record_id, exc
            )
            raise
        finally:
            conn.close()

    def anonymize_where(
        self,
        table: str,
        where_clause: str,
        where_params: list | None = None,
        fields_to_anonymize: list[str] | None = None,
        *,
        id_column: str = "id",
        db_path: str | Path | None = None,
    ) -> dict:
        """Anonymize all records matching *where_clause*.

        Returns a summary dict with ``count`` of records processed.
        """
        conn = self._connect(db_path)
        try:
            rows = conn.execute(
                f"SELECT {id_column} FROM {table} WHERE {where_clause}",  # noqa: S608
                where_params or [],
            ).fetchall()
        finally:
            conn.close()

        results = []
        for row in rows:
            result = self.anonymize_record(
                table,
                row[0],
                fields_to_anonymize,
                id_column=id_column,
                db_path=db_path,
            )
            results.append(result)

        return {
            "table": table,
            "count": len(results),
            "details": results,
        }
