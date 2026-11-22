"""Staff HR schema — Leave entitlements (yearly allocation, pro rata, carry-over), sickness absence
(episodes, fit notes, return-to-work, triggers, occupational health),
family leave (maternity / paternity / adoption / shared parental, KIT days)
and flexible working requests.

* ``staff_leave_settings`` — key/value policy (leave year start, full-time
  hours, carry-over cap and expiry, absence trigger points, statutory
  family-leave weeks and rates). Defaults live in
  ``domain/staff_hr/leave_rules.DEFAULTS``; a row overrides one.
* ``staff_leave_entitlements`` — per leave type: how the yearly allocation
  is worked out (``fte_pro_rata`` / ``fixed`` / ``absence`` / ``case`` /
  ``none``), the full-time days, whether it carries over and its cap.
* ``staff_working_patterns`` — which weekdays someone works and their FTE
  (a flexible working decision writes here).
* ``staff_leave_holidays`` — closure days HR adds on top of the computed
  UK bank holidays.
* ``leave_balances`` gains the bank holidays booked against annual leave,
  the carry-over expiry and the expired days, and how the allocation was
  worked out; ``leave_requests`` gains its working days, half days and
  where it came from (``leave`` / ``absence`` / ``family_leave``).
* ``staff_absence_episodes`` / ``staff_fit_notes`` / ``staff_rtw_interviews``
  / ``staff_absence_alerts`` / ``staff_oh_referrals`` — sickness absence.
* ``staff_family_leave_cases`` / ``staff_kit_days`` — family leave.
* ``staff_flexible_working_requests`` — statutory flexible working.
* ``staff_leave_reminders`` — which reminder went to whom (sent once).

Applied by ``staff_hr_ddl`` (see there for the module contract).
"""

from __future__ import annotations

TABLES = (
    """CREATE TABLE IF NOT EXISTS staff_leave_settings (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_by TEXT,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS staff_leave_entitlements (
        leave_type_id INTEGER PRIMARY KEY,
        basis TEXT NOT NULL DEFAULT 'fixed' CHECK (basis IN
            ('fte_pro_rata', 'fixed', 'absence', 'case', 'none')),
        full_time_days REAL,
        pro_rata_service INTEGER NOT NULL DEFAULT 1,
        carry_over INTEGER NOT NULL DEFAULT 0,
        carry_over_cap REAL,
        includes_bank_holidays INTEGER NOT NULL DEFAULT 0,
        updated_by TEXT,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS staff_working_patterns (
        user_id TEXT PRIMARY KEY,
        work_days TEXT NOT NULL DEFAULT '0,1,2,3,4',
        hours_per_week REAL,
        fte REAL,
        effective_from TEXT,
        source TEXT,
        updated_by TEXT,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS staff_leave_holidays (
        holiday_date TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        kind TEXT NOT NULL DEFAULT 'closure' CHECK (kind IN ('closure', 'bank_holiday')),
        added_by TEXT,
        added_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS staff_absence_episodes (
        episode_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT,
        first_day_half INTEGER NOT NULL DEFAULT 0,
        reason_category TEXT NOT NULL DEFAULT 'Other',
        reason_detail TEXT,
        certification TEXT NOT NULL DEFAULT 'self' CHECK (certification IN
            ('self', 'fit_note', 'none')),
        working_days REAL NOT NULL DEFAULT 0,
        work_related INTEGER NOT NULL DEFAULT 0,
        disability_related INTEGER NOT NULL DEFAULT 0,
        pregnancy_related INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed', 'cancelled')),
        reported_by TEXT,
        reported_at TEXT NOT NULL DEFAULT (datetime('now')),
        closed_by TEXT,
        closed_at TEXT,
        leave_request_id INTEGER,
        notes TEXT,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "CREATE INDEX IF NOT EXISTS ix_staff_absence_user ON staff_absence_episodes (user_id, start_date)",
    """CREATE TABLE IF NOT EXISTS staff_fit_notes (
        fit_note_id INTEGER PRIMARY KEY AUTOINCREMENT,
        episode_id INTEGER NOT NULL REFERENCES staff_absence_episodes (episode_id)
            ON DELETE CASCADE,
        issued_date TEXT NOT NULL,
        from_date TEXT NOT NULL,
        to_date TEXT NOT NULL,
        assessment TEXT NOT NULL DEFAULT 'not_fit' CHECK (assessment IN
            ('not_fit', 'may_be_fit')),
        adjustments TEXT,
        condition TEXT,
        issued_by TEXT,
        document_path TEXT,
        received_by TEXT,
        received_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "CREATE INDEX IF NOT EXISTS ix_staff_fit_notes_episode ON staff_fit_notes (episode_id)",
    """CREATE TABLE IF NOT EXISTS staff_rtw_interviews (
        rtw_id INTEGER PRIMARY KEY AUTOINCREMENT,
        episode_id INTEGER NOT NULL UNIQUE REFERENCES staff_absence_episodes (episode_id)
            ON DELETE CASCADE,
        interview_date TEXT NOT NULL,
        conducted_by TEXT NOT NULL,
        fit_to_return INTEGER NOT NULL DEFAULT 1,
        adjustments_agreed TEXT,
        support_offered TEXT,
        wellbeing_notes TEXT,
        triggers_discussed INTEGER NOT NULL DEFAULT 0,
        oh_referral_recommended INTEGER NOT NULL DEFAULT 0,
        employee_comments TEXT,
        employee_confirmed INTEGER NOT NULL DEFAULT 0,
        employee_confirmed_at TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS staff_absence_alerts (
        alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        trigger_kind TEXT NOT NULL CHECK (trigger_kind IN ('bradford', 'episodes', 'days')),
        value REAL NOT NULL,
        threshold REAL NOT NULL,
        window_start TEXT NOT NULL,
        window_end TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'open' CHECK (status IN
            ('open', 'reviewed', 'actioned', 'dismissed')),
        raised_at TEXT NOT NULL DEFAULT (datetime('now')),
        reviewed_by TEXT,
        reviewed_at TEXT,
        outcome TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS ix_staff_absence_alerts_user ON staff_absence_alerts (user_id, status)",
    """CREATE TABLE IF NOT EXISTS staff_oh_referrals (
        referral_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        episode_id INTEGER,
        referred_by TEXT NOT NULL,
        referred_at TEXT NOT NULL DEFAULT (datetime('now')),
        reason TEXT NOT NULL,
        questions TEXT,
        consent_given INTEGER NOT NULL DEFAULT 0,
        consent_at TEXT,
        provider TEXT,
        appointment_date TEXT,
        status TEXT NOT NULL DEFAULT 'awaiting_consent' CHECK (status IN
            ('awaiting_consent', 'referred', 'appointment_booked', 'report_received',
             'closed', 'declined')),
        fitness TEXT CHECK (fitness IS NULL OR fitness IN
            ('fit', 'fit_with_adjustments', 'temporarily_unfit', 'long_term_unfit')),
        adjustments TEXT,
        outcome TEXT,
        report_received_at TEXT,
        review_date TEXT,
        closed_by TEXT,
        closed_at TEXT,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "CREATE INDEX IF NOT EXISTS ix_staff_oh_user ON staff_oh_referrals (user_id)",
    """CREATE TABLE IF NOT EXISTS staff_family_leave_cases (
        case_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        kind TEXT NOT NULL CHECK (kind IN
            ('maternity', 'paternity', 'adoption', 'shared_parental')),
        status TEXT NOT NULL DEFAULT 'notified' CHECK (status IN
            ('notified', 'confirmed', 'on_leave', 'returned', 'cancelled')),
        ewc TEXT,
        birth_date TEXT,
        matching_date TEXT,
        placement_date TEXT,
        qualifying_week TEXT,
        leave_start TEXT,
        leave_weeks INTEGER,
        leave_end TEXT,
        return_date TEXT,
        actual_return_date TEXT,
        statutory_weeks_used INTEGER NOT NULL DEFAULT 0,
        average_weekly_earnings REAL,
        service_start TEXT,
        leave_eligible INTEGER,
        pay_eligible INTEGER,
        eligibility_notes TEXT,
        pay_schedule TEXT,
        leave_request_id INTEGER,
        notes TEXT,
        created_by TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "CREATE INDEX IF NOT EXISTS ix_staff_family_user ON staff_family_leave_cases (user_id)",
    """CREATE TABLE IF NOT EXISTS staff_kit_days (
        kit_id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER NOT NULL REFERENCES staff_family_leave_cases (case_id)
            ON DELETE CASCADE,
        day TEXT NOT NULL,
        hours REAL,
        notes TEXT,
        agreed_by TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (case_id, day)
    )""",
    """CREATE TABLE IF NOT EXISTS staff_flexible_working_requests (
        fw_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        submitted_at TEXT NOT NULL DEFAULT (datetime('now')),
        change_type TEXT NOT NULL DEFAULT 'hours',
        current_pattern TEXT,
        requested_pattern TEXT NOT NULL,
        requested_days TEXT,
        requested_hours REAL,
        requested_start TEXT,
        temporary_until TEXT,
        effect_notes TEXT,
        approver TEXT,
        status TEXT NOT NULL DEFAULT 'submitted' CHECK (status IN
            ('submitted', 'meeting_scheduled', 'approved', 'approved_trial', 'rejected',
             'withdrawn', 'appealed', 'appeal_upheld', 'appeal_dismissed')),
        decision_due TEXT NOT NULL,
        extended_to TEXT,
        meeting_date TEXT,
        meeting_notes TEXT,
        consulted INTEGER NOT NULL DEFAULT 0,
        decision_by TEXT,
        decided_at TEXT,
        decision_notes TEXT,
        rejection_reason TEXT,
        trial_end TEXT,
        appeal_grounds TEXT,
        appealed_at TEXT,
        appeal_decided_by TEXT,
        appeal_decided_at TEXT,
        appeal_notes TEXT,
        contract_variation TEXT,
        varied_at TEXT,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "CREATE INDEX IF NOT EXISTS ix_staff_fw_user ON staff_flexible_working_requests (user_id)",
    """CREATE TABLE IF NOT EXISTS staff_leave_reminders (
        reminder_key TEXT NOT NULL,
        recipient TEXT NOT NULL,
        sent_at TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (reminder_key, recipient)
    )""",
)

ADDED_COLUMNS = (
    ('leave_balances', 'bank_holiday_days', 'REAL DEFAULT 0'),
    ('leave_balances', 'carry_over_expires', 'TEXT'),
    ('leave_balances', 'carry_over_expired', 'REAL DEFAULT 0'),
    ('leave_balances', 'allocation_basis', 'TEXT'),
    ('leave_requests', 'working_days', 'REAL'),
    ('leave_requests', 'start_half', 'INTEGER DEFAULT 0'),
    ('leave_requests', 'end_half', 'INTEGER DEFAULT 0'),
    ('leave_requests', 'source', "TEXT DEFAULT 'leave'"),
    ('leave_requests', 'source_id', 'INTEGER'),
    ('leave_requests', 'cancelled_by', 'TEXT'),
)

#: Leave types family leave cases book against (inactive: never picked in the
#: ordinary request dialog; the case creates the booking).
FAMILY_TYPES = (
    ('Maternity Leave', '#e83e8c'),
    ('Paternity Leave', '#6f42c1'),
    ('Adoption Leave', '#fd7e14'),
    ('Shared Parental Leave', '#20c997'),
)


def migrate_data(execute) -> None:
    """Annual leave is pro rata to FTE with carry-over; sick leave is absence,
    not an allowance; the family leave types exist and are case-booked."""
    rows = execute("SELECT leave_type_id, name, max_days_per_year FROM leave_types").fetchall()
    for type_id, name, days in rows:
        lowered = str(name or '').lower()
        if lowered.startswith('annual'):
            execute("INSERT OR IGNORE INTO staff_leave_entitlements (leave_type_id, basis, "
                    "full_time_days, carry_over, updated_by) VALUES (?, 'fte_pro_rata', ?, 1, "
                    "'migration')", (type_id, days or 25))
        elif lowered.startswith('sick'):
            execute("INSERT OR IGNORE INTO staff_leave_entitlements (leave_type_id, basis, "
                    "updated_by) VALUES (?, 'absence', 'migration')", (type_id,))
    for name, colour in FAMILY_TYPES:
        execute("INSERT OR IGNORE INTO leave_types (name, description, max_days_per_year, "
                "requires_approval, is_paid, color_code, is_active) VALUES (?, ?, 0, 0, 1, ?, 0)",
                (name, 'Booked from a family leave case', colour))
        found = execute("SELECT leave_type_id FROM leave_types WHERE name = ?", (name,)).fetchall()
        if found:
            execute("INSERT OR IGNORE INTO staff_leave_entitlements (leave_type_id, basis, "
                    "updated_by) VALUES (?, 'case', 'migration')", (found[0][0],))
    execute("UPDATE leave_requests SET source = 'leave' WHERE source IS NULL")
    execute("UPDATE leave_requests SET working_days = total_days WHERE working_days IS NULL")


__all__ = ["TABLES", "ADDED_COLUMNS", "FAMILY_TYPES", "migrate_data"]
