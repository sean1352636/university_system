"""Back-fill ``journey_id`` on existing student rows across all four systems.

Step 2 of the cross-system integration plan. Pure-data migration: read
each system's local students/pupils table, match each unlinked row to a
``student_journey`` row in the shared auth DB (creating one if needed),
then write the resulting ``journey_id`` back onto the local row.

Idempotent — safe to re-run. Rows that are already linked are skipped.
Rows missing the matching keys (DOB or names) are skipped and counted
as ``skipped_no_match_keys``.

This module is **not** an event producer. Wiring
``journey.registered`` / ``journey.transitioned`` events into create /
transfer paths is step 3.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Iterable

from education_system.shared.cross_system import identity_service as ids

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-system row-shape config
# ---------------------------------------------------------------------------
#
# Each system's students/pupils table has slightly different column names.
# We declare the shape declaratively so the backfill loop can be written
# once. ``dob_col`` / ``first_col`` / ``last_col`` are the identity keys we
# match on; ``id_col`` is the integer pk to link as ``<system>_pk`` (None
# for the university subsystem, which uses a TEXT pk only); ``sid_col`` is
# the human-readable id we link as ``<system>_student_id``.

@dataclass(frozen=True)
class _SystemSpec:
    name: str             # 'primary' | 'school' | 'college' | 'university'
    table: str            # 'pupils' or 'students'
    id_col: str | None    # integer pk column (None for university)
    sid_col: str          # human student id column
    dob_col: str
    first_col: str
    last_col: str


_SPECS: dict[str, _SystemSpec] = {
    "primary": _SystemSpec(
        name="primary", table="pupils",
        id_col="id", sid_col="pupil_id",
        dob_col="date_of_birth", first_col="first_name", last_col="last_name",
    ),
    "school": _SystemSpec(
        name="school", table="students",
        id_col="id", sid_col="student_id",
        dob_col="date_of_birth", first_col="first_name", last_col="last_name",
    ),
    "college": _SystemSpec(
        name="college", table="students",
        id_col="id", sid_col="student_id",
        dob_col="date_of_birth", first_col="first_name", last_col="last_name",
    ),
    "university": _SystemSpec(
        name="university", table="students",
        id_col=None, sid_col="student_id",  # student_id IS the pk
        dob_col="dob", first_col="first_name", last_col="last_name",
    ),
}


# ---------------------------------------------------------------------------
# Report shape
# ---------------------------------------------------------------------------

@dataclass
class BackfillReport:
    system: str
    examined: int = 0
    already_linked: int = 0
    linked_existing_journey: int = 0
    linked_new_journey: int = 0
    skipped_no_match_keys: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def linked(self) -> int:
        return self.linked_existing_journey + self.linked_new_journey

    def as_dict(self) -> dict:
        return {
            "system": self.system,
            "examined": self.examined,
            "already_linked": self.already_linked,
            "linked_existing_journey": self.linked_existing_journey,
            "linked_new_journey": self.linked_new_journey,
            "skipped_no_match_keys": self.skipped_no_match_keys,
            "errors": list(self.errors),
        }


# ---------------------------------------------------------------------------
# Backfill loop
# ---------------------------------------------------------------------------

def backfill_system(
    system: str, db_path: str,
    *,
    auth_db_path: str | None = None,
    dry_run: bool = False,
    batch_size: int = 500,
) -> BackfillReport:
    """Back-fill ``journey_id`` on every unlinked row in ``<system>``.

    ``db_path`` is the system's own database file. ``auth_db_path`` is the
    shared auth DB; ``None`` means use the default resolved by
    ``shared.auth.db.connect``.

    With ``dry_run=True`` the function reports what it *would* do without
    writing anything (neither to the system DB nor to the shared journey
    tables). Useful as a pre-flight before running for real.
    """
    if system not in _SPECS:
        raise ValueError(f"Unknown system {system!r}; expected {tuple(_SPECS)}")
    spec = _SPECS[system]
    report = BackfillReport(system=system)

    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        # Verify the journey_id column has been added (step-2 migration).
        cols = {r[1] for r in conn.execute(
            f"PRAGMA table_info({spec.table})").fetchall()}
        if "journey_id" not in cols:
            raise RuntimeError(
                f"{spec.table}.journey_id column missing — run the system "
                f"schema migration before backfilling.")

        select_cols = [spec.sid_col, spec.dob_col, spec.first_col,
                       spec.last_col, "journey_id"]
        if spec.id_col:
            select_cols.insert(0, spec.id_col)
        sql = (f"SELECT {', '.join(select_cols)} FROM {spec.table} "
               f"WHERE journey_id IS NULL OR journey_id = ''")
        rows = conn.execute(sql).fetchall()  # nosec B608

        update_buffer: list[tuple] = []
        for row in rows:
            report.examined += 1
            try:
                outcome = _link_one(spec, row, auth_db_path, dry_run)
            except Exception as exc:
                logger.exception(
                    "Backfill failed for %s row %s",
                    system, row[spec.sid_col],
                )
                report.errors.append(
                    f"{row[spec.sid_col]}: {exc!r}")
                continue

            if outcome is None:
                report.skipped_no_match_keys += 1
                continue
            journey_id, status = outcome
            if status == "existing":
                report.linked_existing_journey += 1
            else:
                report.linked_new_journey += 1
            if not dry_run:
                pk_for_update = row[spec.id_col] if spec.id_col else row[spec.sid_col]
                update_buffer.append((journey_id, pk_for_update))
                if len(update_buffer) >= batch_size:
                    _flush(conn, spec, update_buffer)
                    update_buffer.clear()

        if not dry_run and update_buffer:
            _flush(conn, spec, update_buffer)

        if not dry_run:
            conn.commit()
    finally:
        conn.close()

    logger.info("Backfill report: %s", report.as_dict())
    return report


def backfill_all(
    *,
    primary_db: str | None = None,
    school_db: str | None = None,
    college_db: str | None = None,
    university_db: str | None = None,
    auth_db_path: str | None = None,
    dry_run: bool = False,
) -> dict[str, BackfillReport]:
    """Run ``backfill_system`` for each subsystem whose DB path is given.

    Missing paths are silently skipped — useful when running in dev where
    only one subsystem's DB exists.
    """
    paths = {
        "primary":    primary_db,
        "school":     school_db,
        "college":    college_db,
        "university": university_db,
    }
    out: dict[str, BackfillReport] = {}
    for system, path in paths.items():
        if not path:
            continue
        out[system] = backfill_system(
            system, path, auth_db_path=auth_db_path, dry_run=dry_run)
    return out


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _link_one(spec: _SystemSpec, row: sqlite3.Row,
              auth_db_path: str | None, dry_run: bool,
              ) -> tuple[str, str] | None:
    """Try to link a single row. Returns ``(journey_id, status)`` where
    ``status`` is ``'existing'`` if a journey already existed for this
    identity tuple or ``'new'`` if one was created. Returns ``None`` if
    the row is missing the keys we need to match on."""
    first = (row[spec.first_col] or "").strip()
    last = (row[spec.last_col] or "").strip()
    dob = (row[spec.dob_col] or "").strip()
    if not (first and last and dob):
        return None

    pk = row[spec.id_col] if spec.id_col else None
    sid = row[spec.sid_col]

    # Pre-check whether a journey already exists so we can report
    # "existing" vs "new" honestly. Without this we'd lose that signal.
    pre_existing = ids.get_journey  # only used for None-checking below
    matched = ids.find_journey_by_system_pk(spec.name, pk, db_path=auth_db_path) \
        if pk is not None else None
    if matched is None and sid:
        matched = ids.find_journey_by_student_id(spec.name, sid,
                                                  db_path=auth_db_path)

    if dry_run:
        # Don't mutate; figure out which bucket it would fall in.
        # ``get_or_create`` would return matched.journey_id if a row with
        # this DOB+name already exists, otherwise create a new one.
        existing_for_keys = _journey_exists_for_keys(
            first=first, last=last, dob=dob, db_path=auth_db_path)
        return (
            (matched["journey_id"] if matched else
             (existing_for_keys or "(would-create)")),
            "existing" if (matched or existing_for_keys) else "new",
        )

    existing_for_keys = _journey_exists_for_keys(
        first=first, last=last, dob=dob, db_path=auth_db_path)
    journey_id = ids.get_or_create_journey(
        first_name=first, last_name=last, date_of_birth=dob,
        current_system=spec.name, db_path=auth_db_path,
    )
    ids.attach_system_record(
        journey_id, spec.name,
        pk=pk, student_id=sid, db_path=auth_db_path,
    )
    status = "existing" if (matched or existing_for_keys) else "new"
    return journey_id, status


def _journey_exists_for_keys(*, first: str, last: str, dob: str,
                              db_path: str | None) -> str | None:
    """Lightweight existence check without creating a row."""
    from education_system.shared.auth.db import connect
    conn = connect(db_path)
    try:
        row = conn.execute(
            """SELECT journey_id FROM student_journey
                WHERE date_of_birth = ?
                  AND lower(legal_last_name) = lower(?)
                  AND lower(legal_first_name) = lower(?)""",
            (dob, last, first),
        ).fetchone()
        return row["journey_id"] if row else None
    finally:
        conn.close()


def _flush(conn: sqlite3.Connection, spec: _SystemSpec,
           buf: Iterable[tuple]) -> None:
    """Write a batch of (journey_id, pk_or_sid) updates back to the system DB."""
    key_col = spec.id_col or spec.sid_col
    conn.executemany(
        f"UPDATE {spec.table} SET journey_id = ? WHERE {key_col} = ?",  # nosec B608
        list(buf),
    )


__all__ = ["BackfillReport", "backfill_system", "backfill_all"]
