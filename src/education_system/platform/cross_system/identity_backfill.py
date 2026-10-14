"""Idempotent backfill of the cross-system identity registry.

Walks each system database, reads existing student/pupil records, and
registers them into ``student_journey`` via
:func:`identity_service.get_or_create_journey`. The same real person
enrolled in several systems collapses to a single ``journey_id`` with each
system's slot linked — turning name-based guessing into authoritative
identity. Resolution is the registry's own (a record already linked is
reused; different people who share a name and birthday are *not* folded
together), so the backfill cannot create a false merge the live create
paths would not.

As well as registering each row into the registry, the backfill stamps the
resulting ``journey_id`` back onto the system's own pupil/student row (adding
the column if absent), so existing records gain the same FK to the shared
identity that newly created ones get on insert. Pass ``stamp=False`` to skip.

Re-running is safe: a second pass finds every record already linked and
creates nothing. Registration events are suppressed — historic records
joining the registry are not news to the other systems.

Records without a date of birth are skipped (the registry requires DOB to
match identity) and reported in the summary so the gap is visible rather than
silently dropped.

:func:`run_all` is the single entry point an operator screen calls: identity,
then the enrolment history derived from the slots, then the qualification
projection.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from education_system.platform.cross_system import identity_service
from education_system.paths import SYSTEM_DB_PATHS, SYSTEM_ORDER

logger = logging.getLogger(__name__)

# system -> (table, id_col, first_name_col, last_name_col, dob_col)
#
# The name columns are per-system, which is why this cannot simply reuse
# paths.SYSTEM_LEARNER_TABLE: university stores ``dob`` where everyone else
# stores ``date_of_birth``, and apprenticeships uses the employment-record
# vocabulary ``given_name``/``family_name`` rather than first/last.
_SOURCES: dict[str, tuple[str, str, str, str, str]] = {
    "nursery":    ("pupils",   "pupil_id",   "first_name", "last_name", "date_of_birth"),
    "primary":    ("pupils",   "pupil_id",   "first_name", "last_name", "date_of_birth"),
    "secondary":     ("pupils",   "pupil_id",   "first_name", "last_name", "date_of_birth"),
    "sixth_form":    ("students",  "student_id", "first_name", "last_name", "date_of_birth"),
    "fe_college": ("students",  "student_id", "first_name", "last_name", "date_of_birth"),
    "apprenticeships": ("apprentices", "apprentice_id",
                        "given_name", "family_name", "date_of_birth"),
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
                system=system, student_id=str(r["sid"]), announce=False,
                db_path=auth_db,
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
        db_paths: optional {system: path} override. When given, it is the
            *complete* set: a system absent from it is reported as
            ``db_missing`` rather than silently read — and stamped — from
            the live registry path. (That fallback used to let a test that
            listed five systems write into the running FE and
            apprenticeships databases.)
        auth_db: optional auth DB path override (where student_journey lives).
        dry_run: count what would be linked without writing.
        stamp: also write journey_id back onto each local row (default True).

    Returns {system: counts} plus a "_total" aggregate row.
    """
    result: dict[str, dict[str, int]] = {}
    total = _blank()
    for system in SYSTEM_ORDER:
        if db_paths is not None and not db_paths.get(system):
            stats = _blank()
            stats["db_missing"] = 1
        else:
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


def run_all(*, db_paths=None, auth_db=None, dry_run: bool = False,
            include_qualifications: bool = True) -> dict[str, int]:
    """Run every backfill, in dependency order. Idempotent.

    1. identity — register and stamp every local learner record;
    2. enrolments — derive ``learner_enrolment`` history from the slots;
    3. qualifications — project each system's awards and approved
       handovers into ``learner_qualification`` (no bus events).

    Returns one flat ``{counter: n}`` dict (``identity_linked``,
    ``enrolments_created``, ``qualifications_created`` ...), which is what a
    superadmin screen shows after pressing the button. ``dry_run`` stops
    after counting the identity pass, since the later steps read its output.
    """
    from education_system.platform.cross_system import (
        enrolment_schema,
        qualifications,
    )

    out: dict[str, int] = {}
    identity = backfill_identity_registry(db_paths=db_paths, auth_db=auth_db,
                                          dry_run=dry_run, stamp=True)
    for key, value in identity["_total"].items():
        out[f"identity_{key}"] = value
    if dry_run:
        return out

    for key, value in enrolment_schema.backfill_enrolments(
            db_path=auth_db).items():
        out[f"enrolments_{key}"] = value

    if include_qualifications:
        try:
            q = qualifications.sync_all(db_paths=db_paths, db_path=auth_db)
            out["qualifications_created"] = q.get("created", 0)
            out["qualifications_unmatched"] = q.get("unmatched", 0)
        except Exception:
            logger.exception("Qualification projection failed during run_all")
            out["qualifications_errors"] = 1
    logger.info("Backfill run_all: %s", out)
    return out


__all__ = [
    "backfill_system",
    "backfill_identity_registry",
    "run_all",
]
