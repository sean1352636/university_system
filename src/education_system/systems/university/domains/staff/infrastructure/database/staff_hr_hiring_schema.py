"""Staff HR schema — Hiring: pre-employment checks (right to work, DBS) with expiry and
re-checks, references, offers, converting a hire into a staff record;
HR reminders.

* ``staff_hr_pre_employment_checks`` — one row per check per application
  (``right_to_work``, ``dbs``, ``qualifications``, ``health``). Right to
  work keeps the document type, share code, who checked it, when, and the
  follow-up date (time-limited permission / visa expiry); DBS keeps the
  level, certificate number, issue date, update-service subscription and
  the re-check date. ``staff_username`` is filled in at hire so the
  follow-up and re-check reminders reach the person.
* ``staff_hr_check_requirements`` — which checks must clear before a start
  date can be confirmed, per posting ``job_type`` (``'*'`` = every job).
  ``references`` here means the required satisfactory references.
* ``staff_hr_references`` — references requested (by e-mail through the
  outbox), recorded and judged satisfactory or not.
* ``staff_hr_offers`` — conditional / unconditional offers with salary,
  grade, start date and FTE; accepted, declined, withdrawn, hired.
* ``staff_hr_reminder_log`` — one row per reminder sent to a person, so the
  daily reminder job never sends the same reminder twice.
* ``staff_recruitment_interviews`` — interviews for staff vacancies.
  ``interview_schedules`` belongs to Careers Services (its application_id
  references the students' ``job_applications``), so staff interviews could
  never be saved there with foreign keys on, and retention clearing staff
  applicants would have deleted students' interviews by matching ids.

:func:`migrate_data` (idempotent): every job requires a right-to-work check
and references unless HR configures otherwise.
"""

from __future__ import annotations

CHECK_TYPES = ('right_to_work', 'dbs', 'qualifications', 'health')
REQUIREMENT_TYPES = CHECK_TYPES + ('references',)

TABLES = (
    """CREATE TABLE IF NOT EXISTS staff_hr_pre_employment_checks (
        check_id INTEGER PRIMARY KEY AUTOINCREMENT,
        application_id INTEGER,
        staff_username TEXT,
        check_type TEXT NOT NULL CHECK (check_type IN
            ('right_to_work', 'dbs', 'qualifications', 'health')),
        status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN
            ('pending', 'in_progress', 'cleared', 'failed', 'waived')),
        document_type TEXT,
        share_code TEXT,
        checked_by TEXT,
        check_date TEXT,
        follow_up_date TEXT,
        dbs_level TEXT CHECK (dbs_level IS NULL OR dbs_level IN
            ('basic', 'standard', 'enhanced', 'enhanced_barred')),
        certificate_number TEXT,
        issue_date TEXT,
        update_service INTEGER NOT NULL DEFAULT 0,
        recheck_date TEXT,
        details TEXT,
        notes TEXT,
        created_by TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (application_id, check_type)
    )""",
    "CREATE INDEX IF NOT EXISTS ix_staff_hr_checks_staff ON staff_hr_pre_employment_checks "
    "(staff_username)",
    """CREATE TABLE IF NOT EXISTS staff_hr_check_requirements (
        job_type TEXT NOT NULL,
        check_type TEXT NOT NULL CHECK (check_type IN
            ('right_to_work', 'dbs', 'qualifications', 'health', 'references')),
        set_by TEXT,
        set_at TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (job_type, check_type)
    )""",
    """CREATE TABLE IF NOT EXISTS staff_hr_references (
        reference_id INTEGER PRIMARY KEY AUTOINCREMENT,
        application_id INTEGER NOT NULL,
        referee_name TEXT NOT NULL,
        referee_email TEXT,
        relationship TEXT,
        status TEXT NOT NULL DEFAULT 'requested' CHECK (status IN
            ('requested', 'received', 'declined')),
        requested_by TEXT,
        requested_at TEXT,
        received_at TEXT,
        content TEXT,
        satisfactory INTEGER,
        assessed_by TEXT,
        notes TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "CREATE INDEX IF NOT EXISTS ix_staff_hr_refs_app ON staff_hr_references (application_id)",
    """CREATE TABLE IF NOT EXISTS staff_hr_offers (
        offer_id INTEGER PRIMARY KEY AUTOINCREMENT,
        application_id INTEGER NOT NULL,
        offer_type TEXT NOT NULL DEFAULT 'conditional' CHECK (offer_type IN
            ('conditional', 'unconditional')),
        job_title TEXT,
        department TEXT,
        contract_type TEXT NOT NULL DEFAULT 'permanent',
        salary REAL,
        grade TEXT,
        fte REAL NOT NULL DEFAULT 1.0,
        start_date TEXT,
        end_date TEXT,
        probation_months INTEGER NOT NULL DEFAULT 6,
        manager_id TEXT,
        onboarding_template_id INTEGER,
        conditions TEXT,
        status TEXT NOT NULL DEFAULT 'made' CHECK (status IN
            ('made', 'accepted', 'declined', 'withdrawn', 'hired')),
        start_confirmed INTEGER NOT NULL DEFAULT 0,
        made_by TEXT,
        made_at TEXT NOT NULL DEFAULT (datetime('now')),
        responded_at TEXT,
        response_note TEXT,
        withdrawn_by TEXT,
        withdraw_reason TEXT,
        staff_username TEXT,
        contract_id INTEGER,
        hired_by TEXT,
        hired_at TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS ix_staff_hr_offers_app ON staff_hr_offers (application_id)",
    """CREATE TABLE IF NOT EXISTS staff_hr_reminder_log (
        reminder_key TEXT NOT NULL,
        recipient TEXT NOT NULL,
        kind TEXT,
        subject_username TEXT,
        sent_at TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (reminder_key, recipient)
    )""",
    """CREATE TABLE IF NOT EXISTS staff_recruitment_interviews (
        interview_id INTEGER PRIMARY KEY AUTOINCREMENT,
        application_id INTEGER NOT NULL
            REFERENCES staff_recruitment_applications (application_id) ON DELETE CASCADE,
        applicant_name TEXT,
        interview_type TEXT NOT NULL DEFAULT 'in-person',
        interview_round INTEGER DEFAULT 1,
        interview_date TEXT NOT NULL,
        interview_time TEXT NOT NULL,
        duration_minutes INTEGER DEFAULT 60,
        location TEXT,
        video_link TEXT,
        interviewers TEXT,
        status TEXT DEFAULT 'scheduled',
        feedback TEXT,
        strengths TEXT,
        concerns TEXT,
        recommendation TEXT,
        overall_score INTEGER,
        notes TEXT,
        scheduled_by TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
    "CREATE INDEX IF NOT EXISTS ix_staff_recruitment_interviews_app "
    "ON staff_recruitment_interviews (application_id)",
)

ADDED_COLUMNS = (
    ('staff_recruitment_applications', 'hired_username', 'TEXT'),
)

#: Required for every job unless HR changes it.
DEFAULT_REQUIREMENTS = ('right_to_work', 'references')


def migrate_data(execute) -> None:
    """Every job requires the default checks unless any requirement is set."""
    if execute("SELECT 1 FROM staff_hr_check_requirements LIMIT 1").fetchall():
        return
    for check in DEFAULT_REQUIREMENTS:
        execute("INSERT OR IGNORE INTO staff_hr_check_requirements (job_type, check_type, set_by) "
                "VALUES ('*', ?, 'migration')", (check,))


__all__ = ["TABLES", "ADDED_COLUMNS", "CHECK_TYPES", "REQUIREMENT_TYPES",
           "DEFAULT_REQUIREMENTS", "migrate_data"]
