"""One-time (idempotent) backfill of the cross-system identity registry.

Walks each of the 5 system databases, reads existing student/pupil records,
and registers them into ``student_journey`` via
:func:`identity_service.get_or_create_journey`. Because matching is on
(first_name, last_name, date_of_birth), the same real person enrolled in
several systems collapses to a single ``journey_id`` with each system's slot
linked — turning name-based guessing into authoritative identity.

As well as registering each row into the registry, the backfill stamps the
resulting ``journey_id`` back onto the system's own pupil/student row (adding
the column if absent), so existing records gain the same FK to the shared
identity that newly created ones get on insert. Pass ``stamp=False`` to skip.

Re-running is safe: ``get_or_create_journey`` is idempotent, so a second pass
relinks the same rows without creating duplicates.

Records without a date of birth are skipped (the registry requires DOB to
match identity) and reported in the summary so the gap is visible rather than
silently dropped.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from education_system.shared.cross_system import identity_service
from education_system.shared.database.paths import SYSTEM_DB_PATHS, SYSTEM_ORDER

logger = logging.getLogger(__name__)

# system -> (table, id_col, first_name_col, last_name_col, dob_col)
_SOURCES: dict[str, tuple[str, str, str, str, str]] = {
    "nursery":    ("pupils",   "pupil_id",   "first_name", "last_name", "date_of_birth"),
    "primary":    ("pupils",   "pupil_id",   "first_name", "last_name", "date_of_birth"),
    "school":     ("pupils",   "pupil_id",   "first_name", "last_name", "date_of_birth"),
    "college":    ("students",  "student_id", "first_name", "last_name", "date_of_birth"),
    "university": ("students",  "student_id", "first_name", "last_name", "dob"),
}


def _blank() -> dict[str, int]:
    return {"total": 0, "linked": 0, "stamped": 0, "skipped_no_dob": 0,
            "skipped_no_name": 0, "errors": 0, "db_missing": 0}


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _stamp_local_journey_ids(src: Path, table: str, id_col: str,
                             pairs: list[tuple[str, str]]) -> int:
    """Write ``journey_id`` onto local rows in one pass (adding the column
    if absent). ``pairs`` is a list of (student_id, journey_id). Returns the
    number of rows updated. Best-effort: logs and returns 0 on failure."""
    if not pairs:
        return 0
    try:
        conn = sqlite3.connect(str(src))
        try:
            cols = {r[1] for r in conn.execute(
                f"PRAGMA table_info({table})").fetchall()}
            if "journey_id" not in cols:
                conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN journey_id TEXT")  # nosec B608
            cur = conn.executemany(
                f"UPDATE {table} SET journey_id = ? WHERE {id_col} = ?",  # nosec B608
                [(jid, sid) for (sid, jid) in pairs])
            conn.commit()
            return cur.rowcount if cur.rowcount and cur.rowcount > 0 else len(pairs)
        finally:
            conn.close()
    except Exception as e:  # noqa: BLE001
        logger.warning("Backfill stamp failed for %s: %s", table, e)
        return 0


def backfill_system(system: str, *, db_path=None, auth_db=None,
                    dry_run: bool = False, stamp: bool = True) -> dict[str, int]:
    """Backfill a single system. Returns a counts dict.

    When ``stamp`` is true (the default), the resulting ``journey_id`` is
    also written onto each local pupil/student row.
    """
    stats = _blank()
    table, id_col, first_col, last_col, dob_col = _SOURCES[system]
    src = Path(db_path) if db_path else Path(SYSTEM_DB_PATHS[system])
    if not src.exists():
        stats["db_missing"] = 1
        return stats

    conn = sqlite3.connect(str(src))
    conn.row_factory = sqlite3.Row
    try:
        if not _table_exists(conn, table):
            return stats
        rows = conn.execute(
            f"SELECT {id_col} AS sid, {first_col} AS first, "  # nosec B608 - identifiers from fixed map
            f"{last_col} AS last, {dob_col} AS dob FROM {table}"
        ).fetchall()
    except Exception as e:  # noqa: BLE001
        logger.warning("Backfill read failed for %s: %s", system, e)
        stats["errors"] += 1
        return stats
    finally:
        conn.close()

    to_stamp: list[tuple[str, str]] = []
    for r in rows:
        stats["total"] += 1
        first = (r["first"] or "").strip()
        last = (r["last"] or "").strip()
        dob = (r["dob"] or "").strip()
        if not (first and last):
            stats["skipped_no_name"] += 1
            continue
        if not dob:
            stats["skipped_no_dob"] += 1
            continue
        if dry_run:
            stats["linked"] += 1
            continue
        try:
            jid = identity_service.get_or_create_journey(
                first_name=first, last_name=last, date_of_birth=dob,
                system=system, student_id=str(r["sid"]), db_path=auth_db,
            )
            stats["linked"] += 1
            if stamp and jid:
                to_stamp.append((str(r["sid"]), jid))
        except Exception as e:  # noqa: BLE001
            logger.warning("Backfill link failed for %s/%s: %s", system, r["sid"], e)
            stats["errors"] += 1

    if stamp and not dry_run:
        stats["stamped"] = _stamp_local_journey_ids(src, table, id_col, to_stamp)
    return stats


def backfill_identity_registry(*, db_paths=None, auth_db=None,
                               dry_run: bool = False,
                               stamp: bool = True) -> dict[str, dict[str, int]]:
    """Backfill every system into the registry (nursery -> university order).

    Args:
        db_paths: optional {system: path} override (defaults to the canonical
            registry); useful for tests.
        auth_db: optional auth DB path override (where student_journey lives).
        dry_run: count what would be linked without writing.
        stamp: also write journey_id back onto each local row (default True).

    Returns {system: counts} plus a "_total" aggregate row.
    """
    result: dict[str, dict[str, int]] = {}
    total = _blank()
    for system in SYSTEM_ORDER:
        path = (db_paths or {}).get(system)
        stats = backfill_system(system, db_path=path, auth_db=auth_db,
                                dry_run=dry_run, stamp=stamp)
        result[system] = stats
        for k, v in stats.items():
            total[k] += v
    result["_total"] = total
    logger.info(
        "Identity backfill %s: %d linked, %d stamped, %d skipped (no DOB), "
        "%d errors", "(dry run)" if dry_run else "complete",
        total["linked"], total["stamped"], total["skipped_no_dob"],
        total["errors"],
    )
    return result
