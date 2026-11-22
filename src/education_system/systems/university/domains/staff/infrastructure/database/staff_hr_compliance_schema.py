"""Staff HR schema — Compliance: staff equality monitoring, gender pay gap, HESA staff
return, HR record retention; and the end of the ``staff`` table as a login store.

Applied by ``staff_hr_ddl`` (see there for the module contract).

* ``staff_equality_declarations`` — one voluntary declaration per member of
  staff (username), kept apart from the personnel record. Read by the person
  and, only in aggregate, by HR (``domain/staff_hr/equality.py``).
* ``staff_compliance_settings`` — key/value settings (smallest reportable
  group, standard working week, UKPRN for the HESA return).
* ``staff_retention_policies`` — how long each kind of HR record is kept
  after its trigger, and whether it is then anonymised or deleted
  (``domain/staff_hr/retention.py``); ``staff_retention_holds`` stops that
  for a person under a legal or investigative hold; ``staff_retention_runs``
  logs every preview-applied run.

:func:`migrate_data` (idempotent) — the ``staff`` table:

The university ``staff`` table is the staff *directory* many screens read
for a name and e-mail address. It also carried a password hash for every
member of staff — a third store of staff credentials beside ``auth.db`` and
``users``, used by nobody's sign-in (every university member shared one
seeded hash, and the cinema sign-in that reads the table cannot accept it).

1. Anyone in ``staff`` with no ``staff_profiles`` row gets one, so Staff HR
   (keyed by username) knows every member of staff.
2. The password hash of every row that belongs to a university person (a
   ``staff_profiles`` or ``users`` username) and was not created by the
   cinema's own staff screen (which salts its hashes) becomes ``'!'`` — the
   "no password" marker batch imports already write. The column is NOT NULL.
"""

from __future__ import annotations

TABLES = (
    """CREATE TABLE IF NOT EXISTS staff_equality_declarations (
        username TEXT PRIMARY KEY,
        sex TEXT,
        gender_identity TEXT,
        ethnicity TEXT,
        disability TEXT,
        religion TEXT,
        sexual_orientation TEXT,
        caring_responsibilities TEXT,
        declared_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS staff_compliance_settings (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_by TEXT,
        updated_at TEXT DEFAULT (datetime('now'))
    )""",
    "INSERT OR IGNORE INTO staff_compliance_settings (key, value) VALUES ('equality_min_group', '5')",
    "INSERT OR IGNORE INTO staff_compliance_settings (key, value) VALUES ('standard_hours_per_week', '37.5')",
    "INSERT OR IGNORE INTO staff_compliance_settings (key, value) VALUES ('ukprn', '')",
    """CREATE TABLE IF NOT EXISTS staff_retention_policies (
        record_type TEXT PRIMARY KEY,
        label TEXT NOT NULL,
        keep_months INTEGER NOT NULL CHECK (keep_months >= 0),
        trigger TEXT NOT NULL,
        action TEXT NOT NULL DEFAULT 'anonymise' CHECK (action IN ('anonymise', 'delete')),
        enabled INTEGER NOT NULL DEFAULT 0,
        updated_by TEXT,
        updated_at TEXT DEFAULT (datetime('now'))
    )""",
    "INSERT OR IGNORE INTO staff_retention_policies (record_type, label, keep_months, trigger, action) "
    "VALUES ('leaver_file', 'Leavers'' personnel files', 72, 'after leaving', 'anonymise')",
    "INSERT OR IGNORE INTO staff_retention_policies (record_type, label, keep_months, trigger, action) "
    "VALUES ('grievance', 'Grievance cases', 72, 'after closure', 'delete')",
    "INSERT OR IGNORE INTO staff_retention_policies (record_type, label, keep_months, trigger, action) "
    "VALUES ('discipline', 'Disciplinary cases', 72, 'after closure', 'delete')",
    "INSERT OR IGNORE INTO staff_retention_policies (record_type, label, keep_months, trigger, action) "
    "VALUES ('unsuccessful_applicant', 'Unsuccessful applicants', 6, 'after the decision', 'delete')",
    "INSERT OR IGNORE INTO staff_retention_policies (record_type, label, keep_months, trigger, action) "
    "VALUES ('right_to_work', 'Right to work checks', 24, 'after employment ends', 'delete')",
    "INSERT OR IGNORE INTO staff_retention_policies (record_type, label, keep_months, trigger, action) "
    "VALUES ('sickness', 'Sickness absence records', 36, 'after the absence', 'delete')",
    "INSERT OR IGNORE INTO staff_retention_policies (record_type, label, keep_months, trigger, action) "
    "VALUES ('payroll', 'Payroll records', 72, 'after the pay period', 'anonymise')",
    """CREATE TABLE IF NOT EXISTS staff_retention_holds (
        hold_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        reason TEXT NOT NULL,
        placed_by TEXT,
        placed_at TEXT NOT NULL DEFAULT (datetime('now')),
        released_by TEXT,
        released_at TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS ix_staff_retention_holds_user ON staff_retention_holds (username)",
    """CREATE TABLE IF NOT EXISTS staff_retention_runs (
        run_id INTEGER PRIMARY KEY AUTOINCREMENT,
        at TEXT NOT NULL DEFAULT (datetime('now')),
        actor TEXT,
        record_type TEXT NOT NULL,
        table_name TEXT NOT NULL,
        action TEXT NOT NULL,
        rows_affected INTEGER NOT NULL DEFAULT 0,
        details TEXT
    )""",
)

#: The HESA staff return needs these and the personnel record had neither.
ADDED_COLUMNS = (
    ('staff_profiles', 'date_of_birth', 'TEXT'),
    ('staff_profiles', 'nationality', 'TEXT'),
)


def _rows(execute, sql, params=()):
    return execute(sql, params).fetchall()


def _staff_directory(execute) -> None:
    from education_system.systems.university.domains.staff.infrastructure.database.staff_hr_ddl import (
        columns,
        table_exists,
    )
    if not (table_exists(execute, 'staff') and table_exists(execute, 'staff_profiles')):
        return
    staff_cols = columns(execute, 'staff')
    if 'username' not in staff_cols:
        return
    profiles = {u for (u,) in _rows(execute, "SELECT user_id FROM staff_profiles")}
    hire = 'hire_date' if 'hire_date' in staff_cols else 'NULL'
    for username, hired in _rows(execute, f"SELECT username, {hire} FROM staff "  # nosec B608
                                          "WHERE username IS NOT NULL AND username != ''"):
        if username in profiles:
            continue
        execute("INSERT INTO staff_profiles (user_id, hire_date) VALUES (?, ?)", (username, hired))
        profiles.add(username)
    if 'password_hash' not in staff_cols:
        return
    people = set(profiles)
    if table_exists(execute, 'users'):
        people |= {u for (u,) in _rows(execute, "SELECT username FROM users "
                                                "WHERE username IS NOT NULL")}
    salted = "AND (salt IS NULL OR salt = '')" if 'salt' in staff_cols else ""
    for row_id, username in _rows(execute, "SELECT id, username FROM staff WHERE "  # nosec B608
                                           f"password_hash != '!' {salted}"):
        if username in people:
            execute("UPDATE staff SET password_hash = '!' WHERE id = ?", (row_id,))


def migrate_data(execute) -> None:
    _staff_directory(execute)


__all__ = ["TABLES", "ADDED_COLUMNS", "migrate_data"]
