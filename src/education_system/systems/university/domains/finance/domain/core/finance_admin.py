"""Finance administration helpers shared by the Finance GUI and CLI.

Lifted from the Finance GUI Admin tab
(``interfaces/gui/finance/layout/_admin.py``) so the command-line Finance
Admin menu runs the same queries and writes.  Covers fee-type and aid-type
management, database statistics, backups, old-data cleanup and the system
status snapshot.

Backups land under ``var/backups/university/database`` — the single backup
location the platform uses (``paths.system_backup_dir``), never a hand-built
path.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from education_system.systems.university.infrastructure.database.db import get_connection

#: Tables the GUI "Database Statistics" button counts.
STATISTICS_TABLES: tuple[str, ...] = (
    "students",
    "student_fees",
    "payments",
    "scholarships",
    "student_scholarships",
    "collection_cases",
    "student_financial_aid",
    "late_fees",
    "exchange_rates",
)

#: Categories offered when creating a financial-aid type.
AID_CATEGORIES: tuple[str, ...] = ("grant", "loan", "scholarship", "work_study")

#: Records older than this are removed by :func:`cleanup_old_data`.
CLEANUP_RETENTION_YEARS = 7


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# --------------------------------------------------------------------------- #
# Fee types
# --------------------------------------------------------------------------- #
def create_fee_type(
    fee_name: str,
    description: str = "",
    academic_year: str = "",
    is_recurring: bool = False,
) -> int:
    """Insert a fee type and return its id. ``fee_name`` is required."""
    name = (fee_name or "").strip()
    if not name:
        raise ValueError("Fee name is required.")
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO fee_types
            (fee_name, description, academic_year, is_recurring, created_at, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
            """,
            (name, description.strip(), academic_year.strip(), 1 if is_recurring else 0),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def list_fee_types() -> list[dict[str, Any]]:
    """Every fee type, oldest first."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT fee_type_id, fee_name, description, academic_year, is_recurring
            FROM fee_types
            ORDER BY fee_type_id
            """
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "fee_type_id": r[0],
            "fee_name": r[1],
            "description": r[2],
            "academic_year": r[3],
            "is_recurring": bool(r[4]),
        }
        for r in rows
    ]


# --------------------------------------------------------------------------- #
# Financial aid types
# --------------------------------------------------------------------------- #
def create_aid_type(
    aid_name: str,
    description: str = "",
    max_amount: float = 0.0,
    category: str = "grant",
) -> int:
    """Insert an active financial-aid type and return its id."""
    name = (aid_name or "").strip()
    if not name:
        raise ValueError("Aid type name is required.")
    if category not in AID_CATEGORIES:
        raise ValueError(f"Category must be one of: {', '.join(AID_CATEGORIES)}.")
    if max_amount < 0:
        raise ValueError("Maximum amount cannot be negative.")
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO financial_aid_types
            (aid_name, description, max_amount, aid_category, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, datetime('now'), datetime('now'))
            """,
            (name, description.strip(), float(max_amount), category),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def list_aid_types() -> list[dict[str, Any]]:
    """Every financial-aid type, oldest first."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT aid_type_id, aid_name, description, max_amount, aid_category, is_active
            FROM financial_aid_types
            ORDER BY aid_type_id
            """
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "aid_type_id": r[0],
            "aid_name": r[1],
            "description": r[2],
            "max_amount": float(r[3] or 0),
            "aid_category": r[4],
            "is_active": bool(r[5]),
        }
        for r in rows
    ]


# --------------------------------------------------------------------------- #
# Database maintenance
# --------------------------------------------------------------------------- #
def database_statistics(tables: tuple[str, ...] = STATISTICS_TABLES) -> list[tuple[str, int | None]]:
    """Row counts for the finance tables; ``None`` when a table is absent."""
    conn = get_connection()
    try:
        present = {
            r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        stats: list[tuple[str, int | None]] = []
        for table in tables:
            if table not in present:
                stats.append((table, None))
                continue
            count = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            stats.append((table, int(count)))
        return stats
    finally:
        conn.close()


def backup_database() -> Path:
    """Copy the live university database into the platform backup tree."""
    import shutil

    from education_system import paths

    backup_dir = paths.system_backup_dir("university", "database")
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"student_records_backup_{datetime.now():%Y%m%d_%H%M%S}.db"
    shutil.copy2(paths.UNIVERSITY_DEFAULT_DB_PATH, target)
    return target


def cleanup_old_data(retention_years: int = CLEANUP_RETENTION_YEARS) -> dict[str, int]:
    """Delete payments and late fees older than *retention_years* years."""
    window = f"-{int(retention_years)} years"
    conn = get_connection()
    try:
        deleted_payments = conn.execute(
            "DELETE FROM payments WHERE created_at < date('now', ?)", (window,)
        ).rowcount
        deleted_late_fees = conn.execute(
            "DELETE FROM late_fees WHERE created_at < date('now', ?)", (window,)
        ).rowcount
        conn.commit()
    finally:
        conn.close()
    return {"payments": int(deleted_payments), "late_fees": int(deleted_late_fees)}


# --------------------------------------------------------------------------- #
# System status
# --------------------------------------------------------------------------- #
def system_status() -> dict[str, Any]:
    """Headline counts plus a seven-day activity snapshot."""
    conn = get_connection()
    try:
        scalar = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
        return {
            "generated_at": _now(),
            "total_students": int(scalar("SELECT COUNT(*) FROM students")),
            "unpaid_fees": int(scalar("SELECT COUNT(*) FROM student_fees WHERE status = 'unpaid'")),
            "total_payments": int(scalar("SELECT COUNT(*) FROM payments")),
            "total_revenue": float(
                scalar("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'completed'")
            ),
            "recent_payments": int(
                scalar("SELECT COUNT(*) FROM payments WHERE created_at >= date('now', '-7 days')")
            ),
            "recent_fees": int(
                scalar("SELECT COUNT(*) FROM student_fees WHERE created_at >= date('now', '-7 days')")
            ),
            "recent_collections": int(
                scalar(
                    "SELECT COUNT(*) FROM collection_cases WHERE created_at >= date('now', '-7 days')"
                )
            ),
        }
    finally:
        conn.close()


def system_status_text(status: dict[str, Any] | None = None) -> str:
    """Plain-text rendering of :func:`system_status` (the GUI status panel)."""
    s = status or system_status()
    return "\n".join(
        [
            f"System Status - {s['generated_at']}",
            "=" * 70,
            "",
            "DATABASE STATUS",
            "-" * 70,
            f"Total Students: {s['total_students']:,}",
            f"Unpaid Fees: {s['unpaid_fees']:,}",
            f"Total Payments: {s['total_payments']:,}",
            f"Total Revenue: £{s['total_revenue']:,.2f}",
            "",
            "RECENT ACTIVITY (Last 7 Days)",
            "-" * 70,
            f"New Payments: {s['recent_payments']}",
            f"New Fees Assigned: {s['recent_fees']}",
            f"New Collection Cases: {s['recent_collections']}",
            "",
            "System is operational and running normally.",
            f"Last updated: {s['generated_at']}",
        ]
    )


__all__ = [
    "AID_CATEGORIES",
    "CLEANUP_RETENTION_YEARS",
    "STATISTICS_TABLES",
    "backup_database",
    "cleanup_old_data",
    "create_aid_type",
    "create_fee_type",
    "database_statistics",
    "list_aid_types",
    "list_fee_types",
    "system_status",
    "system_status_text",
]
