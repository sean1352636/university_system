"""Staff HR access: HR role grants, the HR audit trail, staff-only
discipline, and one identity for staff (the username).

* ``staff_hr_roles`` — who holds an HR role (``hr_admin``, ``hr_officer``,
  ``payroll``, ``recruiter``); administrators hold every role implicitly.
  See ``domain/staff_hr/access.py``.
* ``staff_hr_audit`` — who did or read what (cases, pay, personal files).
* ``staff_disciplinary_records`` / ``_actions`` / ``_appeals`` — staff
  discipline. ``disciplinary_records`` is the university's *student*
  discipline store (academic misconduct, first-aid escalations, the
  disciplinary portal); staff cases no longer share it.

:func:`migrate_data` (idempotent):

1. Staff tables key people by username (TEXT), but screens saved the
   numeric ``users.id`` (e.g. leave request user ``'1'`` = ``admin``), so
   approvals and profiles never matched. Every person column of every
   Staff HR table holding a bare number that is ``users.id`` — and is not
   itself a username — becomes that username.
2. ``staff_profiles.manager_id`` holding an employee number becomes the
   manager's username.
3. Any staff member's case in ``disciplinary_records`` (with its actions
   and appeals) moves to the staff tables.
"""

from __future__ import annotations

import re
from pathlib import Path

TABLES = (
    """CREATE TABLE IF NOT EXISTS staff_hr_roles (
        username TEXT NOT NULL,
        role TEXT NOT NULL CHECK (role IN ('hr_admin', 'hr_officer', 'payroll', 'recruiter')),
        granted_by TEXT,
        granted_at TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (username, role)
    )""",
    """CREATE TABLE IF NOT EXISTS staff_hr_audit (
        audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
        at TEXT NOT NULL DEFAULT (datetime('now')),
        actor TEXT,
        action TEXT NOT NULL,
        subject_username TEXT,
        entity TEXT,
        entity_id TEXT,
        details TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS ix_staff_hr_audit_subject ON staff_hr_audit (subject_username, at)",
    """CREATE TABLE IF NOT EXISTS staff_disciplinary_records (
        record_id INTEGER PRIMARY KEY AUTOINCREMENT,
        reference_number TEXT UNIQUE,
        user_id TEXT NOT NULL,
        offense_type TEXT NOT NULL,
        offense_category TEXT,
        severity TEXT DEFAULT 'minor',
        description TEXT NOT NULL,
        date_occurred TEXT NOT NULL,
        date_reported TEXT,
        reported_by TEXT,
        witnesses TEXT,
        evidence_path TEXT,
        status TEXT DEFAULT 'under_review',
        investigation_notes TEXT,
        investigating_officer TEXT,
        is_confidential BOOLEAN DEFAULT 1,
        previous_warnings INTEGER DEFAULT 0,
        moved_from_record_id INTEGER UNIQUE,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
    "CREATE INDEX IF NOT EXISTS ix_staff_disc_user ON staff_disciplinary_records (user_id)",
    """CREATE TABLE IF NOT EXISTS staff_disciplinary_actions (
        action_id INTEGER PRIMARY KEY AUTOINCREMENT,
        record_id INTEGER NOT NULL REFERENCES staff_disciplinary_records (record_id)
            ON DELETE CASCADE,
        action_type TEXT NOT NULL,
        action_level TEXT,
        effective_date TEXT NOT NULL,
        end_date TEXT,
        duration_days INTEGER,
        imposed_by TEXT NOT NULL,
        reason TEXT,
        conditions TEXT,
        appeal_deadline TEXT,
        appeal_submitted BOOLEAN DEFAULT 0,
        appeal_outcome TEXT,
        document_path TEXT,
        acknowledged_by_employee BOOLEAN DEFAULT 0,
        acknowledged_date TEXT,
        expires_on TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS staff_disciplinary_appeals (
        appeal_id INTEGER PRIMARY KEY AUTOINCREMENT,
        action_id INTEGER NOT NULL REFERENCES staff_disciplinary_actions (action_id)
            ON DELETE CASCADE,
        appellant_id TEXT NOT NULL,
        appeal_date TEXT NOT NULL,
        grounds TEXT NOT NULL,
        supporting_documents TEXT,
        status TEXT DEFAULT 'submitted',
        hearing_date TEXT,
        panel_members TEXT,
        outcome TEXT,
        outcome_date TEXT,
        outcome_details TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
)

ADDED_COLUMNS = ()

#: Columns that name a person in Staff HR tables (all TEXT usernames).
PERSON_COLUMNS = (
    'user_id', 'created_by', 'approved_by', 'reviewer_id', 'approver_id', 'assigned_to',
    'requested_by', 'manager_id', 'respondent_id', 'interviewer_id', 'complainant_id',
    'appellant_id',
)

_HERE = Path(__file__).resolve().parent
_CREATE = re.compile(r"CREATE TABLE IF NOT EXISTS\s+(\w+)")


def staff_tables() -> list:
    """Every table the Staff HR schema modules create."""
    names = set()
    for path in _HERE.glob("staff_hr_*.py"):
        names.update(_CREATE.findall(path.read_text(encoding="utf-8")))
    return sorted(names)


def _rows(execute, sql, params=()):
    return execute(sql, params).fetchall()


def _normalise_people(execute) -> None:
    from education_system.systems.university.domains.staff.infrastructure.database.staff_hr_ddl import (
        columns,
        table_exists,
    )
    if not table_exists(execute, 'users'):
        return
    by_id = {str(i): u for i, u in _rows(execute, "SELECT id, username FROM users "
                                                  "WHERE username IS NOT NULL")}
    usernames = set(by_id.values())
    for table in staff_tables():
        if not table_exists(execute, table) or table == 'staff_hr_audit':
            continue
        cols = columns(execute, table) & set(PERSON_COLUMNS)
        for col in sorted(cols):
            for (value,) in _rows(execute, f'SELECT DISTINCT "{col}" FROM "{table}" '  # nosec B608
                                           f'WHERE "{col}" GLOB \'[0-9]*\''):
                text = str(value).strip()
                if not text.isdigit() or text in usernames or text not in by_id:
                    continue
                execute(f'UPDATE "{table}" SET "{col}" = ? WHERE "{col}" = ?',  # nosec B608
                        (by_id[text], value))


def _normalise_managers(execute) -> None:
    from education_system.systems.university.domains.staff.infrastructure.database.staff_hr_ddl import (
        columns,
        table_exists,
    )
    if not table_exists(execute, 'staff_profiles') or \
            'employee_id' not in columns(execute, 'staff_profiles'):
        return
    users = {u for (u,) in _rows(execute, "SELECT username FROM users")} \
        if table_exists(execute, 'users') else set()
    by_employee = {str(e): u for e, u in _rows(
        execute, "SELECT employee_id, user_id FROM staff_profiles WHERE employee_id IS NOT NULL "
                 "AND employee_id != ''")}
    for profile_id, manager in _rows(execute, "SELECT profile_id, manager_id FROM staff_profiles "
                                              "WHERE manager_id IS NOT NULL AND manager_id != ''"):
        if manager in users:
            continue
        target = by_employee.get(str(manager))
        if target:
            execute("UPDATE staff_profiles SET manager_id = ? WHERE profile_id = ?",
                    (target, profile_id))


def _move_staff_cases(execute) -> None:
    from education_system.systems.university.domains.staff.infrastructure.database.staff_hr_ddl import (
        columns,
        table_exists,
    )
    if not (table_exists(execute, 'disciplinary_records') and table_exists(execute, 'staff_profiles')):
        return
    staff = {u for (u,) in _rows(execute, "SELECT user_id FROM staff_profiles")}
    src_cols = columns(execute, 'disciplinary_records')
    shared = [c for c in ('reference_number', 'user_id', 'offense_type', 'offense_category',
                          'severity', 'description', 'date_occurred', 'date_reported',
                          'reported_by', 'witnesses', 'evidence_path', 'status',
                          'investigation_notes', 'is_confidential', 'previous_warnings',
                          'created_at', 'updated_at') if c in src_cols]
    for row in _rows(execute, f"SELECT record_id, {', '.join(shared)} "  # nosec B608
                              "FROM disciplinary_records"):
        old_id, values = row[0], dict(zip(shared, row[1:]))
        if values.get('user_id') not in staff:
            continue
        if _rows(execute, "SELECT 1 FROM staff_disciplinary_records WHERE "
                          "moved_from_record_id = ?", (old_id,)):
            continue
        values['offense_type'] = values.get('offense_type') or 'Unspecified'
        values['description'] = values.get('description') or ''
        values['date_occurred'] = values.get('date_occurred') or values.get('created_at') or ''
        names = list(values) + ['moved_from_record_id']
        execute(f"INSERT INTO staff_disciplinary_records ({', '.join(names)}) "  # nosec B608
                f"VALUES ({', '.join('?' * len(names))})", tuple(values.values()) + (old_id,))
        new_id = _rows(execute, "SELECT record_id FROM staff_disciplinary_records WHERE "
                                "moved_from_record_id = ?", (old_id,))[0][0]
        if table_exists(execute, 'disciplinary_actions'):
            for action in _rows(execute, "SELECT action_id FROM disciplinary_actions WHERE "
                                         "record_id = ?", (old_id,)):
                execute("INSERT INTO staff_disciplinary_actions (record_id, action_type, "
                        "action_level, effective_date, end_date, duration_days, imposed_by, "
                        "reason, conditions, appeal_deadline, appeal_submitted, appeal_outcome, "
                        "document_path, acknowledged_by_employee, acknowledged_date, created_at) "
                        "SELECT ?, action_type, action_level, effective_date, end_date, "
                        "duration_days, imposed_by, reason, conditions, appeal_deadline, "
                        "appeal_submitted, appeal_outcome, document_path, "
                        "acknowledged_by_employee, acknowledged_date, created_at "
                        "FROM disciplinary_actions WHERE action_id = ?", (new_id, action[0]))
                new_action = _rows(execute, "SELECT MAX(action_id) FROM staff_disciplinary_actions")[0][0]
                if table_exists(execute, 'disciplinary_appeals'):
                    execute("INSERT INTO staff_disciplinary_appeals (action_id, appellant_id, "
                            "appeal_date, grounds, supporting_documents, status, hearing_date, "
                            "panel_members, outcome, outcome_date, outcome_details, created_at) "
                            "SELECT ?, appellant_id, appeal_date, grounds, supporting_documents, "
                            "status, hearing_date, panel_members, outcome, outcome_date, "
                            "outcome_details, created_at FROM disciplinary_appeals "
                            "WHERE action_id = ?", (new_action, action[0]))
                    execute("DELETE FROM disciplinary_appeals WHERE action_id = ?", (action[0],))
                execute("DELETE FROM disciplinary_actions WHERE action_id = ?", (action[0],))
        execute("DELETE FROM disciplinary_records WHERE record_id = ?", (old_id,))


def migrate_data(execute) -> None:
    _normalise_people(execute)
    _normalise_managers(execute)
    _move_staff_cases(execute)


__all__ = ['TABLES', 'ADDED_COLUMNS', 'PERSON_COLUMNS', 'staff_tables', 'migrate_data']
