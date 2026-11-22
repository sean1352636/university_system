"""One attendance store, consistent statuses, and the attendance office tables.

Attendance was split across two tables. The absence tracker's registers,
self check-in, bulk tools and kiosk wrote ``attendance``; QR, geofencing,
face recognition, the Attendance GUI and exam days wrote
``attendance_records``. About forty readers used each, so every report,
alert, eligibility check and export saw part of the picture (the HESA
export read ``attendance``, which was empty). Statuses were stored as both
'Present' and 'present', and most checks compared exact strings.

Now:

* ``attendance_records`` is the only table. Its ``status`` column is
  ``COLLATE NOCASE`` so every SQL comparison ('Present', 'present', IN (...))
  matches regardless of case, and a trigger stores statuses lower-case, which
  is what every Python-side comparison expects.
* ``attendance`` is a view over it with INSTEAD OF triggers, so the code that
  reads and writes the old name keeps working, against the same rows.
* Absences covered by an approved absence request (including a student's
  self-certification) are stored as 'excused' automatically, whichever screen
  recorded them and whichever order the request and the register arrive in.

The conversion of the old table into the view is done once by migration
``e9b2d4f6a8c1``. :func:`apply` (also run by runtime bootstraps) only adds
the office tables, columns and triggers.
"""

RECORD_COLUMNS = (
    ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
    ("student_id", "TEXT"),
    ("module_code", "TEXT"),
    ("date", "TEXT"),
    ("status", "TEXT COLLATE NOCASE"),
    ("notes", "TEXT"),
    ("reason", "TEXT"),
    ("recorded_by", "TEXT"),
    ("recorded_at", "TEXT"),
    ("check_in_method", "TEXT DEFAULT 'manual'"),
    ("location_data", "TEXT"),
    ("ip_address", "TEXT"),
    ("session_id", "TEXT"),
    ("makeup_for_date", "TEXT"),
    ("verification_status", "TEXT"),
    ("record_id", "INTEGER"),
    ("latitude", "REAL"),
    ("longitude", "REAL"),
    ("device_id", "TEXT"),
    ("facial_recognition_confidence", "REAL"),
    ("check_in_time", "TEXT"),
    ("departure_time", "TEXT"),
)

_RECORD_CONSTRAINTS = (
    "FOREIGN KEY (student_id) REFERENCES students (student_id)",
)


def create_records_sql(table="attendance_records") -> str:
    body = ",\n    ".join([f"{n} {d}" for n, d in RECORD_COLUMNS] + list(_RECORD_CONSTRAINTS))
    return f"CREATE TABLE IF NOT EXISTS {table} (\n    {body}\n)"


RECORD_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_attendance_records_student_id ON attendance_records (student_id)",
    "CREATE INDEX IF NOT EXISTS idx_attendance_records_date ON attendance_records (date)",
    "CREATE INDEX IF NOT EXISTS idx_attendance_records_module_date ON attendance_records (module_code, date)",
)

#: The old ``attendance`` shape, served from ``attendance_records``.
COMPAT_VIEW = """
CREATE VIEW IF NOT EXISTS attendance AS
SELECT id, student_id, module_code, date, status, reason,
       check_in_time AS arrival_time, record_id AS attendance_id, date AS class_date,
       departure_time, NULL AS module_id, notes, recorded_by, recorded_at AS created_at,
       NULL AS prior, NULL AS course_name, NULL AS recent
  FROM attendance_records
"""

COMPAT_TRIGGERS = (
    """
    CREATE TRIGGER IF NOT EXISTS attendance_view_insert INSTEAD OF INSERT ON attendance
    BEGIN
        INSERT INTO attendance_records (id, student_id, module_code, date, status, reason, notes,
                                        recorded_by, recorded_at, check_in_time, departure_time,
                                        check_in_method)
        VALUES (NEW.id, NEW.student_id, NEW.module_code, COALESCE(NEW.date, NEW.class_date),
                LOWER(NEW.status), NEW.reason, NEW.notes, COALESCE(NEW.recorded_by, 'register'),
                COALESCE(NEW.created_at, datetime('now')), NEW.arrival_time, NEW.departure_time,
                'register');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS attendance_view_update INSTEAD OF UPDATE ON attendance
    BEGIN
        UPDATE attendance_records
           SET student_id = NEW.student_id, module_code = NEW.module_code, date = NEW.date,
               status = LOWER(NEW.status), reason = NEW.reason, notes = NEW.notes,
               recorded_by = NEW.recorded_by, check_in_time = NEW.arrival_time,
               departure_time = NEW.departure_time
         WHERE id = OLD.id;
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS attendance_view_delete INSTEAD OF DELETE ON attendance
    BEGIN
        DELETE FROM attendance_records WHERE id = OLD.id;
    END
    """,
)

# Lower-case storage. COLLATE BINARY: the column is NOCASE, so a plain <>
# would call 'Present' and 'present' equal and never fire. The SET lowers the
# *current* value, so it cannot undo an 'excused' set by another trigger on
# the same insert, whichever fires first.
STATUS_TRIGGERS = (
    """
    CREATE TRIGGER IF NOT EXISTS attendance_status_lower_insert AFTER INSERT ON attendance_records
    WHEN NEW.status IS NOT NULL AND NEW.status <> LOWER(NEW.status) COLLATE BINARY
    BEGIN
        UPDATE attendance_records SET status = LOWER(status) WHERE id = NEW.id;
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS attendance_status_lower_update AFTER UPDATE OF status ON attendance_records
    WHEN NEW.status IS NOT NULL AND NEW.status <> LOWER(NEW.status) COLLATE BINARY
    BEGIN
        UPDATE attendance_records SET status = LOWER(status) WHERE id = NEW.id;
    END
    """,
)

_COVERS = (
    "r.student_id = {rec}.student_id AND LOWER(r.status) = 'approved' "
    "AND (r.module_code IS NULL OR r.module_code = '' OR r.module_code = {rec}.module_code) "
    "AND {rec}.date BETWEEN r.date AND COALESCE(NULLIF(r.date_end, ''), r.date)"
)
EXCUSE_MARK = "authorised absence (request #"

EXCUSE_TRIGGERS = (
    # A register marked absent on a day an approved request already covers.
    f"""
    CREATE TRIGGER IF NOT EXISTS attendance_auto_excuse AFTER INSERT ON attendance_records
    WHEN LOWER(NEW.status) = 'absent' AND EXISTS (
        SELECT 1 FROM absence_requests r WHERE {_COVERS.format(rec='NEW')})
    BEGIN
        UPDATE attendance_records
           SET status = 'excused',
               reason = '{EXCUSE_MARK}' || (SELECT r.id FROM absence_requests r
                                            WHERE {_COVERS.format(rec='NEW')} LIMIT 1) || ')'
         WHERE id = NEW.id;
    END
    """,
    # A request approved after the absences were recorded.
    f"""
    CREATE TRIGGER IF NOT EXISTS absence_request_approved AFTER UPDATE OF status ON absence_requests
    WHEN LOWER(NEW.status) = 'approved' AND LOWER(COALESCE(OLD.status, '')) <> 'approved'
    BEGIN
        UPDATE attendance_records
           SET status = 'excused', reason = '{EXCUSE_MARK}' || NEW.id || ')'
         WHERE student_id = NEW.student_id AND LOWER(status) = 'absent'
           AND (NEW.module_code IS NULL OR NEW.module_code = '' OR module_code = NEW.module_code)
           AND date BETWEEN NEW.date AND COALESCE(NULLIF(NEW.date_end, ''), NEW.date);
    END
    """,
    # Approved on creation (self-certification, staff-entered).
    f"""
    CREATE TRIGGER IF NOT EXISTS absence_request_inserted_approved AFTER INSERT ON absence_requests
    WHEN LOWER(NEW.status) = 'approved'
    BEGIN
        UPDATE attendance_records
           SET status = 'excused', reason = '{EXCUSE_MARK}' || NEW.id || ')'
         WHERE student_id = NEW.student_id AND LOWER(status) = 'absent'
           AND (NEW.module_code IS NULL OR NEW.module_code = '' OR module_code = NEW.module_code)
           AND date BETWEEN NEW.date AND COALESCE(NULLIF(NEW.date_end, ''), NEW.date);
    END
    """,
    # Approval withdrawn: the absences it excused count again.
    f"""
    CREATE TRIGGER IF NOT EXISTS absence_request_unapproved AFTER UPDATE OF status ON absence_requests
    WHEN LOWER(COALESCE(OLD.status, '')) = 'approved' AND LOWER(NEW.status) <> 'approved'
    BEGIN
        UPDATE attendance_records SET status = 'absent', reason = NULL
         WHERE reason = '{EXCUSE_MARK}' || OLD.id || ')';
    END
    """,
)

PARENT_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS notify_parent_on_absence AFTER INSERT ON attendance_records
WHEN LOWER(NEW.status) <> 'present'
BEGIN
    INSERT INTO parent_notifications (parent_id, student_id, notification_type,
                                      notification_content, created_date, read_status)
    SELECT psr.parent_id, NEW.student_id, 'attendance',
           'Absence recorded: ' || NEW.status || ' on ' || NEW.date, datetime('now'), 0
      FROM parent_student_relationships psr
      JOIN parent_preferences pp ON psr.parent_id = pp.parent_id
     WHERE psr.student_id = NEW.student_id AND pp.attendance_alerts = 1;
END
"""

OFFICE_TABLES = (
    """
    CREATE TABLE IF NOT EXISTS ukvi_engagement_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        detected_on TEXT NOT NULL,
        consecutive_missed INTEGER NOT NULL,
        last_engaged_on TEXT,
        report_due TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'open',
        ukvi_reference TEXT,
        outcome_notes TEXT,
        resolved_by TEXT,
        resolved_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS engagement_cases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        stage TEXT NOT NULL DEFAULT 'tutor_contact',
        status TEXT NOT NULL DEFAULT 'open',
        opened_on TEXT NOT NULL,
        opened_reason TEXT NOT NULL,
        tutor_id TEXT,
        due_on TEXT,
        closed_on TEXT,
        closed_reason TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS engagement_case_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER NOT NULL,
        from_stage TEXT,
        to_stage TEXT NOT NULL,
        actor TEXT,
        notes TEXT,
        changed_at TEXT NOT NULL,
        FOREIGN KEY (case_id) REFERENCES engagement_cases (id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS funding_attendance_confirmations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        term_name TEXT NOT NULL,
        academic_year TEXT,
        status TEXT NOT NULL,
        notes TEXT,
        confirmed_by TEXT,
        confirmed_at TEXT NOT NULL,
        UNIQUE (student_id, term_name)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_engagement_cases_student ON engagement_cases (student_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_ukvi_alerts_student ON ukvi_engagement_alerts (student_id, status)",
)

SETTINGS = (
    ("ukvi_missed_contact_points", "10", "Consecutive missed contact points before a sponsored student is flagged", "compliance", "integer"),
    ("ukvi_report_working_days", "10", "Working days allowed to report a non-engaging sponsored student to UKVI", "compliance", "integer"),
    ("self_cert_max_days", "7", "Longest absence a student may self-certify (calendar days)", "absences", "integer"),
    ("self_cert_per_year", "3", "Self-certifications allowed per academic year", "absences", "integer"),
    ("engagement_stage_days", "10", "Days a student has to respond at each engagement stage", "engagement", "integer"),
)


def apply(execute, existing_columns, fetchone=None):
    """Office tables, columns, settings and triggers. Safe to run repeatedly.

    Does nothing to ``attendance`` itself — converting it to a view is the
    migration's job, because it moves data.
    """
    records = existing_columns("attendance_records")
    if not records:
        return False
    for name, decl in RECORD_COLUMNS:
        if name not in records and "PRIMARY KEY" not in decl:
            execute(f'ALTER TABLE "attendance_records" ADD COLUMN "{name}" {decl.replace(" COLLATE NOCASE", "")}')
    requests = existing_columns("absence_requests")
    if requests and "self_certified" not in requests:
        execute('ALTER TABLE "absence_requests" ADD COLUMN "self_certified" INTEGER DEFAULT 0')
    for ddl in OFFICE_TABLES + RECORD_INDEXES + STATUS_TRIGGERS:
        execute(ddl)
    if requests:
        for ddl in EXCUSE_TRIGGERS:
            execute(ddl)
    if existing_columns("attendance_settings"):
        for name, value, desc, category, kind in SETTINGS:
            execute(
                "INSERT INTO attendance_settings (setting_name, setting_value, description, category, data_type) "
                f"SELECT '{name}', '{value}', '{desc}', '{category}', '{kind}' "
                f"WHERE NOT EXISTS (SELECT 1 FROM attendance_settings WHERE setting_name = '{name}')")
    return True


def apply_to_connection(conn):
    def columns(table):
        return {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}
    applied = apply(conn.execute, columns)
    conn.commit()
    return applied
