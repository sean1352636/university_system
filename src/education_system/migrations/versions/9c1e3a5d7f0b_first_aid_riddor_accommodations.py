"""university health: first aid registers + RIDDOR, accommodations reach
exams, one emergency-contact layout, medical history on the real tables

1. First aid (``pastoral/infrastructure/health/first_aid_schema``): RIDDOR
   columns on ``first_aid_incidents`` (person type, category, reportable,
   deadline, status, HSE reference, the linked ``hs_incidents`` id), the
   first-aider certificate register, kits/AEDs with inspections, real
   course sessions (registrations gain ``session_id``) and reminder
   bookkeeping.
2. Medical accommodations (``accommodation_schema``): ``source_accommodation_id``
   on ``exam_accommodations`` / ``student_accommodations`` /
   ``extension_requests`` and ``accommodation_shares``, so
   ``services/bus/accommodation_bus`` can carry approvals to exams,
   assessments and (with consent) module staff, and withdraw them again.
3. Emergency contacts: one layout (contact_name / relationship /
   phone_primary / phone_secondary / email / is_primary, keyed on the
   student number). Rows written in the CLI's old layout (``name`` /
   ``phone``, keyed on ``users.id``) are copied across; ``student_id``
   values that are a ``users.id`` are mapped to that user's student number
   where one exists (0 rows on the live database when written).
4. Medical history: there is no ``medical_history`` table in the university
   database; readers now use ``medical_conditions`` + ``health_records``
   (``application/health/medical_history``). Where a stray
   ``medical_history`` table exists (the old CLI created one on demand), its
   rows are copied into ``medical_conditions``; the table is left in place.
5. Data fix: disciplinary record 12 ("First-aid Illness (high) at Lab",
   student S12345, reported by 'tester', 2026-06-15) was a first-aid
   escalation filed as a disciplinary case against the reporter. It becomes
   H&S incident ``FA-DISC-12``, the disciplinary record is voided (status
   'Void', which the misconduct sync trigger ignores) with a note, and its
   risk-register row (reference ``case:12``) is repointed at the H&S
   incident. Matched on every field, so a different row 12 is left alone.

Idempotent.

Revision ID: 9c1e3a5d7f0b
Revises: 8b0d2f4c6e9a
Create Date: 2026-10-18 15:00:00.000000
"""
import logging
from datetime import datetime
from typing import Sequence, Union

from alembic import op


revision: str = '9c1e3a5d7f0b'
down_revision: Union[str, Sequence[str], None] = '8b0d2f4c6e9a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger(__name__)

HS_REF = "FA-DISC-12"


def _columns(execute, table) -> set:
    return {r[1] for r in execute(f'PRAGMA table_info("{table}")').fetchall()}


def _has(execute, table) -> bool:
    return bool(execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                        (table,)).fetchone())


def _student_number_for(execute, value):
    """``value`` if it is a student number; else, if it is a ``users.id``,
    that user's student number (students.student_id = username); else None."""
    if value is None:
        return None
    if execute("SELECT 1 FROM students WHERE student_id = ?", (str(value),)).fetchone():
        return str(value)
    if not str(value).isdigit() or not _has(execute, "users"):
        return None
    row = execute("SELECT s.student_id FROM users u JOIN students s "
                  "ON s.student_id = u.username WHERE u.id = ?", (int(value),)).fetchone()
    return row[0] if row else None


def _emergency_contacts(execute) -> None:
    if not _has(execute, "emergency_contacts"):
        return
    cols = _columns(execute, "emergency_contacts")
    for column, decl in (("contact_name", "TEXT"), ("phone_primary", "TEXT"),
                         ("phone_secondary", "TEXT"), ("is_primary", "INTEGER DEFAULT 0"),
                         ("relationship", "TEXT"), ("email", "TEXT")):
        if column not in cols:
            execute(f'ALTER TABLE emergency_contacts ADD COLUMN "{column}" {decl}')
    cols = _columns(execute, "emergency_contacts")
    if "name" in cols:
        n = execute("UPDATE emergency_contacts SET contact_name = name WHERE "
                    "COALESCE(contact_name, '') = '' AND COALESCE(name, '') <> ''").rowcount
        logger.info("emergency_contacts: %s name -> contact_name", n)
    if "phone" in cols:
        n = execute("UPDATE emergency_contacts SET phone_primary = phone WHERE "
                    "COALESCE(phone_primary, '') = '' AND COALESCE(phone, '') <> ''").rowcount
        logger.info("emergency_contacts: %s phone -> phone_primary", n)
    if not _has(execute, "students"):
        return
    for row_id, value in execute(
            "SELECT id, student_id FROM emergency_contacts WHERE student_id IS NOT NULL AND "
            "CAST(student_id AS TEXT) NOT IN (SELECT student_id FROM students)").fetchall():
        number = _student_number_for(execute, value)
        if number:
            execute("UPDATE emergency_contacts SET student_id = ? WHERE id = ?", (number, row_id))
            logger.info("emergency_contacts %s: users.id %s -> student %s", row_id, value, number)
        else:
            logger.warning("emergency_contacts %s keeps student_id %r (no student found)",
                           row_id, value)


def _medical_history(execute) -> None:
    if not _has(execute, "medical_history") or not _has(execute, "medical_conditions"):
        return
    cols = _columns(execute, "medical_history")
    if not {"student_id", "diagnosis"} <= cols:
        return
    pick = [c for c in ("id", "student_id", "diagnosis", "treatment", "date", "provider",
                        "notes", "created_at") if c in cols]
    copied = 0
    for values in execute(f"SELECT {', '.join(pick)} FROM medical_history").fetchall():  # nosec B608
        row = dict(zip(pick, values))
        number = _student_number_for(execute, row.get("student_id"))
        if not number:
            logger.warning("medical_history %s: no student for %r; not copied", row.get("id"),
                           row.get("student_id"))
            continue
        marker = f"[from medical_history #{row.get('id')}]"
        if execute("SELECT 1 FROM medical_conditions WHERE notes LIKE ?",
                   (f"%{marker}%",)).fetchone():
            continue
        notes = " ".join(p for p in (row.get("notes"), (f"Treatment: {row['treatment']}"
                                                         if row.get("treatment") else None),
                                     marker) if p)
        execute("INSERT INTO medical_conditions (student_id, condition_name, diagnosed_date, "
                "status, provider, notes, created_at) VALUES (?, ?, ?, 'active', ?, ?, ?)",
                (number, row["diagnosis"], row.get("date"), row.get("provider"), notes,
                 row.get("created_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        copied += 1
    logger.info("medical_history: %s rows copied into medical_conditions", copied)


def _disciplinary_first_aid_fix(execute) -> None:
    if not (_has(execute, "disciplinary_records") and _has(execute, "hs_incidents")):
        return
    row = execute(
        "SELECT record_id, offense_type, severity, description, date_occurred, location, "
        "reported_by, status FROM disciplinary_records WHERE record_id = 12 AND user_id = 'S12345' "
        "AND description = 'First-aid Illness (high) at Lab. demo' AND reported_by = 'tester' "
        "AND created_at LIKE '2026-06-15%'").fetchone()
    if row is None:
        return
    _, offense_type, severity, description, occurred, location, reported_by, status = row
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    found = execute("SELECT id FROM hs_incidents WHERE ref = ?", (HS_REF,)).fetchone()
    if found:
        hs_id = found[0]
    else:
        hs_id = execute(
            "INSERT INTO hs_incidents (ref, incident_type, location, incident_date, severity, "
            "people_involved, description, actions_taken, reported_by, department, status, "
            "reported_at) VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, 'Health & Safety', 'Open', ?)",
            (HS_REF, offense_type or "Illness", location, occurred, severity or "High",
             description, "Moved from disciplinary record 12, where a first-aid escalation "
             "had been filed against the reporter (migration 9c1e3a5d7f0b).",
             reported_by, now)).lastrowid
    if status != "Void":
        note = (f"Voided {now[:10]}: a first-aid incident escalation, not a disciplinary "
                f"matter. Recorded as Health & Safety incident {HS_REF} (#{hs_id}).")
        execute("UPDATE disciplinary_records SET status = 'Void', investigation_notes = "
                "CASE WHEN COALESCE(investigation_notes, '') = '' THEN ? "
                "ELSE investigation_notes || char(10) || ? END, updated_at = ? "
                "WHERE record_id = 12", (note, note, now))
    if _has(execute, "risks"):
        execute("UPDATE risks SET reference_id = ?, title = ?, category = 'Safety', "
                "department = 'Health & Safety', updated = ? WHERE reference_id = 'case:12' "
                "AND title LIKE 'hs_incident #12%'",
                (f"hs_incident:{hs_id}", f"H&S incident {HS_REF}: {offense_type or 'Illness'}",
                 now))
    logger.info("Disciplinary record 12 -> H&S incident %s (#%s)", HS_REF, hs_id)


def upgrade() -> None:
    execute = op.get_bind().exec_driver_sql
    from education_system.systems.university.domains.health.infrastructure.health import (
        accommodation_schema,
        first_aid_schema,
    )
    first_aid_schema.apply(execute)
    accommodation_schema.apply(execute)
    _emergency_contacts(execute)
    _medical_history(execute)
    _disciplinary_first_aid_fix(execute)


def downgrade() -> None:
    # The new tables and columns are additive and harmless to older code, so
    # they stay. The data fix is not reversed: re-filing a first-aid incident
    # as a disciplinary case against its reporter was the bug.
    pass
