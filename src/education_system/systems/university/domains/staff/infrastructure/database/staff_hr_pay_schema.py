"""Staff HR schema — Pay structure: pay spine and grades, annual increments, pension schemes
and membership; payroll proration inputs.

Applied by ``staff_hr_ddl`` (see there for the module contract).

* ``pay_spine_points`` / ``pay_spine_values`` — the pay spine; one value per
  point per pay year (``'2025/26'``), so a pay award adds a year rather than
  overwriting the last one.
* ``pay_grades`` — a grade's normal point range (``min_point`` ..
  ``max_point``, the top the annual increment reaches) and its contribution
  points (``max_point`` + 1 .. ``contribution_max_point``, awarded by hand).
* ``pay_grade_jobs`` — job title → grade, used when a contract names a job
  but no grade.
* ``pay_settings`` — the increment date (``'08-01'``), the service a starter
  needs before their first increment.
* ``pay_increment_runs`` / ``pay_increment_moves`` — one run per increment
  date; every point moved or held.
* ``pay_awards`` — pay award uplifts (a new pay year's values).
* ``pension_schemes`` / ``pension_scheme_tiers`` / ``pension_memberships`` —
  USS, TPS, LGPS and none; employee rates flat or tiered; who is in which
  scheme, with their opt-out date.

``staff_contracts`` gains ``grade_code``, ``spine_point``, ``fte``,
``pension_scheme`` and a salary override with its reason; ``salary`` stays
the full-time annual salary (payroll applies ``fte``). ``payroll_records``
gains the employer pension, the scheme, FTE, days paid, unpaid leave and
when the payslip notice went.

:func:`migrate_data` (idempotent): default schemes and tiers, settings,
``fte`` = 1 where unset, and a membership for every contract naming a
scheme.
"""

from __future__ import annotations

TABLES = (
    """CREATE TABLE IF NOT EXISTS pay_spine_points (
        point INTEGER PRIMARY KEY,
        label TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS pay_spine_values (
        point INTEGER NOT NULL REFERENCES pay_spine_points (point) ON DELETE CASCADE,
        pay_year TEXT NOT NULL,
        annual_value REAL NOT NULL CHECK (annual_value >= 0),
        set_by TEXT,
        set_at TEXT DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (point, pay_year)
    )""",
    """CREATE TABLE IF NOT EXISTS pay_grades (
        grade_code TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        min_point INTEGER NOT NULL,
        max_point INTEGER NOT NULL,
        contribution_max_point INTEGER,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT,
        CHECK (min_point <= max_point),
        CHECK (contribution_max_point IS NULL OR contribution_max_point >= max_point)
    )""",
    """CREATE TABLE IF NOT EXISTS pay_grade_jobs (
        job_title TEXT PRIMARY KEY COLLATE NOCASE,
        grade_code TEXT NOT NULL REFERENCES pay_grades (grade_code) ON DELETE CASCADE,
        created_by TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS pay_settings (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_by TEXT,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS pay_increment_runs (
        run_id INTEGER PRIMARY KEY AUTOINCREMENT,
        effective_date TEXT NOT NULL UNIQUE,
        pay_year TEXT NOT NULL,
        run_by TEXT,
        run_at TEXT DEFAULT CURRENT_TIMESTAMP,
        moved INTEGER NOT NULL DEFAULT 0,
        held INTEGER NOT NULL DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS pay_increment_moves (
        move_id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL REFERENCES pay_increment_runs (run_id) ON DELETE CASCADE,
        contract_id INTEGER NOT NULL,
        user_id TEXT NOT NULL,
        from_point INTEGER,
        to_point INTEGER,
        outcome TEXT NOT NULL,
        reason TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS ix_pay_increment_moves_run ON pay_increment_moves (run_id)",
    """CREATE TABLE IF NOT EXISTS pay_awards (
        award_id INTEGER PRIMARY KEY AUTOINCREMENT,
        pay_year TEXT NOT NULL UNIQUE,
        from_pay_year TEXT NOT NULL,
        uplift_percent REAL NOT NULL,
        minimum_uplift REAL NOT NULL DEFAULT 0,
        points_updated INTEGER NOT NULL DEFAULT 0,
        notes TEXT,
        applied_by TEXT,
        applied_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS pension_schemes (
        scheme_code TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        employee_rate_pct REAL NOT NULL DEFAULT 0,
        employer_rate_pct REAL NOT NULL DEFAULT 0,
        tiered INTEGER NOT NULL DEFAULT 0,
        tier_basis TEXT NOT NULL DEFAULT 'actual' CHECK (tier_basis IN ('actual', 'fte')),
        is_active INTEGER NOT NULL DEFAULT 1,
        updated_by TEXT,
        updated_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS pension_scheme_tiers (
        scheme_code TEXT NOT NULL REFERENCES pension_schemes (scheme_code) ON DELETE CASCADE,
        lower_limit REAL NOT NULL,
        upper_limit REAL,
        employee_rate_pct REAL NOT NULL,
        PRIMARY KEY (scheme_code, lower_limit)
    )""",
    """CREATE TABLE IF NOT EXISTS pension_memberships (
        membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        scheme_code TEXT NOT NULL REFERENCES pension_schemes (scheme_code),
        joined_on TEXT NOT NULL,
        opted_out_on TEXT,
        opt_out_reason TEXT,
        created_by TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS ix_pension_memberships_user ON pension_memberships (user_id)",
)

ADDED_COLUMNS = (
    ('staff_contracts', 'fte', 'REAL DEFAULT 1.0'),
    ('staff_contracts', 'grade_code', 'TEXT'),
    ('staff_contracts', 'spine_point', 'INTEGER'),
    ('staff_contracts', 'pension_scheme', 'TEXT'),
    ('staff_contracts', 'salary_override', 'REAL'),
    ('staff_contracts', 'salary_override_reason', 'TEXT'),
    ('staff_contracts', 'salary_override_by', 'TEXT'),
    ('payroll_records', 'employer_pension', 'REAL DEFAULT 0'),
    ('payroll_records', 'pension_scheme', 'TEXT'),
    ('payroll_records', 'fte', 'REAL'),
    ('payroll_records', 'days_paid', 'INTEGER'),
    ('payroll_records', 'period_days', 'INTEGER'),
    ('payroll_records', 'unpaid_leave_days', 'REAL DEFAULT 0'),
    ('payroll_records', 'salary_source', 'TEXT'),
    ('payroll_records', 'notice_sent_at', 'TEXT'),
)

#: (code, name, employee %, employer %, tiered, tier basis). Rates are the
#: published ones at the time of writing — payroll keeps them up to date on
#: the Pensions tab. An LGPS employer rate is set per fund, so it starts at 0.
DEFAULT_SCHEMES = (
    ('USS', 'Universities Superannuation Scheme', 6.1, 14.5, 0, 'actual'),
    ('TPS', "Teachers' Pension Scheme", 0.0, 28.68, 1, 'fte'),
    ('LGPS', 'Local Government Pension Scheme', 0.0, 0.0, 1, 'actual'),
    ('NONE', 'No pension scheme', 0.0, 0.0, 0, 'actual'),
)

#: (code, lower, upper, employee %).
DEFAULT_TIERS = (
    ('TPS', 0.0, 34290.0, 7.4),
    ('TPS', 34290.0, 46159.0, 8.6),
    ('TPS', 46159.0, 54730.0, 9.6),
    ('TPS', 54730.0, 72207.0, 10.2),
    ('TPS', 72207.0, 98237.0, 11.3),
    ('TPS', 98237.0, None, 11.7),
    ('LGPS', 0.0, 17800.0, 5.5),
    ('LGPS', 17800.0, 27900.0, 5.8),
    ('LGPS', 27900.0, 45200.0, 6.5),
    ('LGPS', 45200.0, 57200.0, 6.8),
    ('LGPS', 57200.0, 80200.0, 8.5),
    ('LGPS', 80200.0, 113400.0, 9.9),
    ('LGPS', 113400.0, 133100.0, 10.5),
    ('LGPS', 133100.0, 199700.0, 11.4),
    ('LGPS', 199700.0, None, 12.5),
)

DEFAULT_SETTINGS = (
    ('increment_date', '08-01'),           # MM-DD, start of the pay year
    ('increment_min_service_months', '6'),  # starters need this much service first
)


def seed_defaults(execute) -> None:
    """Default schemes, tiers and settings (only where missing)."""
    for code, name, ee, er, tiered, basis in DEFAULT_SCHEMES:
        execute("INSERT OR IGNORE INTO pension_schemes (scheme_code, name, employee_rate_pct, "
                "employer_rate_pct, tiered, tier_basis) VALUES (?, ?, ?, ?, ?, ?)",
                (code, name, ee, er, tiered, basis))
    for code in {t[0] for t in DEFAULT_TIERS}:
        if execute("SELECT 1 FROM pension_scheme_tiers WHERE scheme_code = ?",
                   (code,)).fetchall():
            continue
        for scheme, lower, upper, rate in DEFAULT_TIERS:
            if scheme == code:
                execute("INSERT INTO pension_scheme_tiers (scheme_code, lower_limit, upper_limit, "
                        "employee_rate_pct) VALUES (?, ?, ?, ?)", (scheme, lower, upper, rate))
    for key, value in DEFAULT_SETTINGS:
        execute("INSERT OR IGNORE INTO pay_settings (key, value) VALUES (?, ?)", (key, value))


def migrate_data(execute) -> None:
    from education_system.systems.university.domains.staff.infrastructure.database.staff_hr_ddl import (
        columns,
        table_exists,
    )
    seed_defaults(execute)
    if not table_exists(execute, 'staff_contracts') or \
            'pension_scheme' not in columns(execute, 'staff_contracts'):
        return
    execute("UPDATE staff_contracts SET fte = 1.0 WHERE fte IS NULL")
    for user, scheme, start in execute(
            "SELECT user_id, pension_scheme, start_date FROM staff_contracts "
            "WHERE pension_scheme IS NOT NULL AND pension_scheme != '' "
            "AND status = 'active'").fetchall():
        if execute("SELECT 1 FROM pension_memberships WHERE user_id = ? AND scheme_code = ?",
                   (user, scheme)).fetchall():
            continue
        execute("INSERT INTO pension_memberships (user_id, scheme_code, joined_on, created_by) "
                "VALUES (?, ?, ?, 'migration')", (user, scheme, start or '1970-01-01'))


__all__ = ["TABLES", "ADDED_COLUMNS", "DEFAULT_SCHEMES", "DEFAULT_TIERS", "DEFAULT_SETTINGS",
           "seed_defaults", "migrate_data"]
