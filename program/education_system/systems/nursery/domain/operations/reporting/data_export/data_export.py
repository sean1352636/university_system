"""Domain layer for Data Export (Nursery System).

Exports the setting's nursery tables to CSV files for backup, migration or
sharing with the local authority / Ofsted. Read-only over the data: it never
mutates a table, it only ``SELECT * FROM`` a curated, whitelisted set of tables
and writes one ``<table>.csv`` per table.

Follows the 4-layer pattern: computation + SQLite access here, CLI in
``data_export_cli.py``, Tk GUI in ``data_export_views.py``.
"""

from __future__ import annotations

import csv
import datetime as _dt
import logging
import sqlite3
from pathlib import Path

from education_system.systems.nursery.infrastructure import paths
from education_system.systems.nursery.infrastructure.database import connect, init_db

logger = logging.getLogger(__name__)

FEATURE_NAME = "Data Export"
CATEGORY = "Compliance & Reports"


class ValidationError(ValueError):
    """Raised when an export request names a table outside the whitelist."""


# SECURITY: this module composes SQL that names a table. To prevent SQL
# injection we ONLY ever interpolate a table name that is a verbatim member of
# this hardcoded whitelist of (table_name, friendly_label) pairs. ``export_table``
# checks membership against ``{t for t, _ in EXPORTABLE_TABLES}`` BEFORE building
# any query (the accepted CodeQL py/sql-injection mitigation on this repo).
EXPORTABLE_TABLES: tuple[tuple[str, str], ...] = (
    ("pupils", "Children"),
    ("staff", "Staff"),
    ("rooms", "Rooms"),
    ("admissions", "Admissions"),
    ("enrolments", "Enrolments"),
    ("funded_hours_records", "Funded Hours"),
    ("attendance_records", "Attendance"),
    ("accident_records", "Accident / Incident"),
    ("invoices", "Invoices"),
    ("payments", "Payments"),
    ("funding_claims", "Funding Claims"),
    ("childcare_vouchers", "Vouchers"),
    ("fee_discounts", "Discounts"),
    ("settling_in", "Settling-In"),
    ("transitions", "Transitions"),
    ("leavers", "Leavers"),
    ("rota_shifts", "Staff Rota"),
    ("staff_training", "Training"),
    ("paediatric_first_aid", "Paediatric First Aid"),
    ("consents", "Consents"),
    ("parent_contacts", "Parent Contacts"),
    ("emergency_contacts", "Emergency Contacts"),
)

_ALLOWED_TABLES: frozenset[str] = frozenset(t for t, _ in EXPORTABLE_TABLES)
_LABELS: dict[str, str] = {t: label for t, label in EXPORTABLE_TABLES}


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for data export")
        raise


def _existing_tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {r["name"] for r in rows}


# ── Reads ──────────────────────────────────────────────────────────────────

def list_tables() -> list[dict]:
    """Whitelisted tables that actually exist, with their live row counts."""
    _ensure_schema()
    out: list[dict] = []
    try:
        with connect() as conn:
            present = _existing_tables(conn)
            for table, label in EXPORTABLE_TABLES:
                if table not in present:
                    continue
                # ``table`` is a verbatim whitelist member — safe to inline.
                rows = conn.execute(
                    f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                out.append({"table": table, "label": label, "rows": int(rows)})
    except sqlite3.Error:
        logger.exception("list_tables failed")
        raise
    return out


# ── Export ─────────────────────────────────────────────────────────────────

def export_table(table: str, dir_path: str | Path) -> dict:
    """Export one whitelisted table to ``<table>.csv`` in ``dir_path``."""
    # SECURITY: reject anything not a verbatim whitelist member BEFORE we
    # compose any SQL that names the table.
    if table not in {t for t, _ in EXPORTABLE_TABLES}:
        raise ValidationError(f"Table '{table}' is not exportable.")
    out_dir = Path(dir_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{table}.csv"
    try:
        with connect() as conn:
            # ``table`` is now guaranteed to be a whitelist literal.
            cursor = conn.execute(f"SELECT * FROM {table}")
            headers = [d[0] for d in cursor.description]
            rows = cursor.fetchall()
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for row in rows:
                writer.writerow(list(row))
    except sqlite3.Error:
        logger.exception("export_table failed for %s", table)
        raise
    except OSError as e:
        logger.exception("Could not write CSV for %s to %s", table, path)
        raise OSError(f"Could not write {table}.csv — {e}") from e
    return {"table": table, "path": str(path), "row_count": len(rows)}


def export_all(dir_path: str | Path,
               tables: list[str] | None = None) -> dict:
    """Export the given tables (default: all existing whitelisted ones).

    Errors on a single table are logged and collected without aborting the
    whole run.
    """
    _ensure_schema()
    if tables is None:
        tables = [t["table"] for t in list_tables()]
    out_dir = Path(dir_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    files: list[dict] = []
    total_rows = 0
    for table in tables:
        try:
            res = export_table(table, out_dir)
            files.append(res)
            total_rows += int(res["row_count"])
        except (ValidationError, sqlite3.Error, OSError) as e:
            logger.warning("Skipping table %s during export: %s", table, e)
            files.append({"table": table, "error": str(e)})
    return {
        "dir": str(out_dir),
        "files": files,
        "total_rows": total_rows,
        "table_count": sum(1 for f in files if "path" in f),
    }


def default_export_dir() -> Path:
    """A dated default destination under the nursery data directory."""
    paths.ensure_directories()
    return paths.DATA_DIR / f"export_{_dt.date.today().isoformat()}"


def label_for(table: str) -> str:
    """Friendly label for a whitelisted table (falls back to the name)."""
    return _LABELS.get(table, table)
