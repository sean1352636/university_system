"""university health: one health schema, one profile store, test incidents archived

1. **One schema.** Applies ``domains/health/infrastructure/health/
   health_schema`` — every health table with its live column set (the
   portal used to declare them at runtime in four places), the columns older
   databases lacked, the integration / security alias columns (backfilled
   when added), the retention-policy and security-setting seeds (empty
   tables only), ``personal_health_metrics`` (students' own logged metrics),
   and the sibling first-aid / workflow / accommodation schemas — including
   the new ``first_aid_incidents.archived`` / ``archived_at`` /
   ``archived_by`` / ``archive_reason`` (soft delete). ``students`` gains
   ``dob`` only on a database that has just ``date_of_birth``.
2. **One profile store.** ``medical_info`` is the per-student health profile.
   Duplicate rows for one student are folded into the newest when their
   values don't conflict (conflicting ones are left, and the unique index
   waits); then ``ux_medical_info_student`` makes it one row per student.
   Profile values found in the retired ``health_records`` columns
   (``blood_type`` / ``allergies`` / ``medications`` / ``conditions`` /
   ``insurance_provider`` / ``insurance_policy_number``) fill the
   student's ``medical_info`` fields that are empty — an existing profile
   value always wins. Nothing is removed from ``health_records``.
3. **Test incidents archived.** The 51 first-aid incidents a test run wrote
   into the live database on 2026-08-09 (reporter "Ann Reporter",
   description "Sprained ankle on the stairs.", no phone or e-mail,
   submitted 19:19–19:22, ids 4–54) are archived — hidden from lists, the
   RIDDOR queue, reminders and exports — never deleted. Matched on every one
   of those markers, so no real incident can be caught.

Idempotent: re-running changes nothing.

Revision ID: a0d2f4b6c8e1
Revises: c2f4a6b8d0e3
Create Date: 2026-10-18 20:00:00.000000
"""
import logging
from typing import Sequence, Union

from alembic import op


revision: str = 'a0d2f4b6c8e1'
down_revision: Union[str, Sequence[str], None] = 'c2f4a6b8d0e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger(__name__)

PROFILE = ("blood_type", "allergies", "medications", "conditions", "doctor_name",
           "doctor_phone", "insurance_provider", "insurance_policy")
# health_records (retired copy) -> medical_info
RETIRED = {"blood_type": "blood_type", "allergies": "allergies",
           "medications": "medications", "conditions": "conditions",
           "insurance_provider": "insurance_provider",
           "insurance_policy_number": "insurance_policy"}

TEST_LEAK_WHERE = (
    "reporter_name = 'Ann Reporter' "
    "AND description = 'Sprained ankle on the stairs.' "
    "AND submitted_at >= '2026-08-09 19:19:00' AND submitted_at < '2026-08-09 19:23:00' "
    "AND COALESCE(phone, '') = '' AND COALESCE(email, '') = '' "
    "AND id BETWEEN 4 AND 54"
)
ARCHIVED_BY = "maintenance"
ARCHIVE_REASON = ("Test data leaked by a 2026-08-09 test run; archived at the owner's "
                  "request")


def _columns(execute, table) -> set:
    return {r[1] for r in execute(f'PRAGMA table_info("{table}")').fetchall()}


def _blank(value) -> bool:
    return value is None or str(value).strip() == ""


def _fold_profile_duplicates(execute) -> None:
    if not _columns(execute, "medical_info"):
        return
    for (student_id,) in execute("SELECT student_id FROM medical_info GROUP BY student_id "
                                 "HAVING COUNT(*) > 1").fetchall():
        rows = execute(f"SELECT id, {', '.join(PROFILE)} FROM medical_info "  # nosec B608
                       "WHERE student_id = ? ORDER BY COALESCE(last_updated, '') DESC, id DESC",
                       (student_id,)).fetchall()
        merged, conflict = {}, False
        for row in rows:
            for field, value in zip(PROFILE, row[1:]):
                if _blank(value):
                    continue
                if field in merged and str(merged[field]).strip() != str(value).strip():
                    conflict = True
                merged.setdefault(field, value)
        if conflict:
            logger.warning("medical_info: student %s has conflicting profile rows; left for "
                           "review (no unique index until resolved)", student_id)
            continue
        keep = rows[0][0]
        if merged:
            execute(f"UPDATE medical_info SET {', '.join(f'{k} = ?' for k in merged)} "  # nosec
                    "WHERE id = ?", (*merged.values(), keep))
        for row in rows[1:]:
            execute("DELETE FROM medical_info WHERE id = ?", (row[0],))
        logger.info("medical_info: folded %d duplicate row(s) for student %s into %s",
                    len(rows) - 1, student_id, keep)


def _move_retired_profile(execute) -> None:
    cols = _columns(execute, "health_records")
    have = [c for c in RETIRED if c in cols]
    if not have or not _columns(execute, "medical_info"):
        return
    where = " OR ".join(f"COALESCE(TRIM({c}), '') <> ''" for c in have)
    # Newest record first, so its values win over older ones.
    for row in execute(f"SELECT student_id, {', '.join(have)} FROM health_records "  # nosec B608
                       f"WHERE student_id IS NOT NULL AND ({where}) ORDER BY id DESC"
                       ).fetchall():
        student_id, values = row[0], dict(zip((RETIRED[c] for c in have), row[1:]))
        values = {k: v for k, v in values.items() if not _blank(v)}
        current = execute(f"SELECT id, {', '.join(PROFILE)} FROM medical_info "  # nosec B608
                          "WHERE student_id = ? ORDER BY id DESC LIMIT 1",
                          (str(student_id),)).fetchone()
        if current is None:
            execute(f"INSERT INTO medical_info (student_id, {', '.join(values)}) "  # nosec
                    f"VALUES (?, {', '.join('?' * len(values))})",
                    (str(student_id), *values.values()))
            continue
        existing = dict(zip(PROFILE, current[1:]))
        fill = {k: v for k, v in values.items() if _blank(existing.get(k))}
        if fill:
            execute(f"UPDATE medical_info SET {', '.join(f'{k} = ?' for k in fill)} "  # nosec
                    "WHERE id = ?", (*fill.values(), current[0]))


def _archive_test_leak(execute) -> None:
    if "archived" not in _columns(execute, "first_aid_incidents"):
        return
    ids = [r[0] for r in execute(
        f"SELECT id FROM first_aid_incidents WHERE {TEST_LEAK_WHERE} "  # nosec B608 - literal
        "AND COALESCE(archived, 0) = 0 ORDER BY id").fetchall()]
    if not ids:
        return
    from datetime import datetime
    execute(f"UPDATE first_aid_incidents SET archived = 1, "  # nosec B608 - literal
            "archived_at = ?, archived_by = ?, archive_reason = ? "
            f"WHERE {TEST_LEAK_WHERE} AND COALESCE(archived, 0) = 0",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ARCHIVED_BY, ARCHIVE_REASON))
    logger.info("Archived %d test-leak first-aid incidents: %s", len(ids),
                ", ".join(map(str, ids)))


def upgrade() -> None:
    from education_system.systems.university.domains.health.infrastructure.health import (
        health_schema,
    )
    execute = op.get_bind().exec_driver_sql
    _fold_profile_duplicates(execute)        # before the unique index
    health_schema.apply(execute)
    _move_retired_profile(execute)
    _archive_test_leak(execute)


def downgrade() -> None:
    # Un-archives the test incidents this migration archived (they were
    # never deleted). The schema stays: the tables hold health records, the
    # added columns are harmless to older code, and moved profile values are
    # still in health_records too.
    execute = op.get_bind().exec_driver_sql
    if "archived" in _columns(execute, "first_aid_incidents"):
        execute(f"UPDATE first_aid_incidents SET archived = 0, archived_at = NULL, "  # nosec
                "archived_by = NULL, archive_reason = NULL "
                f"WHERE {TEST_LEAK_WHERE} AND archived_by = ? AND archive_reason = ?",
                (ARCHIVED_BY, ARCHIVE_REASON))
