"""``student_modules`` is the one module-enrolment record; ``module_enrolments``
follows it.

Every screen, rule and report writes ``student_modules`` (one row per
student and module). ``module_enrolments`` is the per-registration view the
lifecycle code and some reports read (academic year, teaching period,
attempt, effective dates). It stays a table, not a view, because
``attendance_events`` has a foreign key to it (a view cannot be a foreign-key
target), and SQLite triggers keep it in step with ``student_modules``:

* insert into ``student_modules`` → the student's programme registration is
  made if they have none (from ``students.course`` / ``mode_of_study``, the
  current academic year), then the enrolment is copied in;
* change of status / dates / semester → copied across (status lower-cased,
  ``Enrolled`` → ``enrolled``; ``effective_to`` set when it stops being
  enrolled);
* change of student or module → the copy follows;
* delete → the copy is deleted, or marked ``withdrawn`` when attendance
  refers to it.

:func:`reconcile` brings existing data into line once (used by migration
``1a3c5e7f9b2d``). Writers must not write ``module_enrolments`` directly.
Idempotent.
"""

from __future__ import annotations

from datetime import date, datetime

MARKER = "student_modules_mirror_insert"

_STATUS = ("CASE WHEN {s} = 'Enrolled' OR LOWER({s}) = 'enrolled' THEN 'enrolled' "
           "ELSE LOWER(COALESCE({s}, 'enrolled')) END")
_YEAR = ("CASE WHEN CAST(strftime('%m', 'now') AS INTEGER) >= 9 "
         "THEN strftime('%Y', 'now') || '/' || (CAST(strftime('%Y', 'now') AS INTEGER) + 1) "
         "ELSE (CAST(strftime('%Y', 'now') AS INTEGER) - 1) || '/' || strftime('%Y', 'now') END")

_ENSURE_REGISTRATION = f"""
    INSERT INTO programme_registrations (student_id, programme_code, academic_year,
        occurrence_code, mode_of_study, status, effective_from, registered_at, registered_by)
    SELECT s.student_id, s.course, {_YEAR}, 'MAIN', COALESCE(NULLIF(s.mode_of_study, ''),
           'full-time'), 'registered', date('now'), datetime('now'), 'student_modules'
      FROM students s
     WHERE s.student_id = NEW.student_id AND COALESCE(s.course, '') <> ''
       AND NOT EXISTS (SELECT 1 FROM programme_registrations pr
                        WHERE pr.student_id = NEW.student_id);
"""

_COPY_IN = f"""
    INSERT INTO module_enrolments (registration_id, student_id, module_code, academic_year,
        teaching_period, attempt_number, status, effective_from, effective_to)
    SELECT pr.registration_id, NEW.student_id, NEW.module_code, pr.academic_year,
           NEW.semester, 1, {_STATUS.format(s='NEW.status')},
           COALESCE(NULLIF(NEW.enrollment_date, ''), date('now')),
           CASE WHEN {_STATUS.format(s='NEW.status')} = 'enrolled' THEN NULL
                ELSE COALESCE(NULLIF(NEW.completion_date, ''), date('now')) END
      FROM programme_registrations pr
     WHERE pr.student_id = NEW.student_id
       AND NOT EXISTS (SELECT 1 FROM module_enrolments me
                        WHERE me.student_id = NEW.student_id
                          AND me.module_code = NEW.module_code)
     ORDER BY pr.registration_id DESC LIMIT 1;
"""

TRIGGERS = (
    f"""CREATE TRIGGER IF NOT EXISTS {MARKER}
        AFTER INSERT ON student_modules
        WHEN NEW.student_id IS NOT NULL AND NEW.module_code IS NOT NULL
        BEGIN
        {_ENSURE_REGISTRATION}
        UPDATE module_enrolments SET status = {_STATUS.format(s='NEW.status')},
               effective_to = CASE WHEN {_STATUS.format(s='NEW.status')} = 'enrolled' THEN NULL
                                   ELSE COALESCE(effective_to, date('now')) END,
               updated_at = CURRENT_TIMESTAMP
         WHERE student_id = NEW.student_id AND module_code = NEW.module_code;
        {_COPY_IN}
        END""",
    f"""CREATE TRIGGER IF NOT EXISTS student_modules_mirror_update
        AFTER UPDATE OF status, enrollment_date, completion_date, semester ON student_modules
        WHEN NEW.student_id IS NOT NULL AND NEW.module_code IS NOT NULL
        BEGIN
        {_ENSURE_REGISTRATION}
        UPDATE module_enrolments SET status = {_STATUS.format(s='NEW.status')},
               teaching_period = COALESCE(NEW.semester, teaching_period),
               effective_from = COALESCE(NULLIF(NEW.enrollment_date, ''), effective_from),
               effective_to = CASE WHEN {_STATUS.format(s='NEW.status')} = 'enrolled' THEN NULL
                                   ELSE COALESCE(NULLIF(NEW.completion_date, ''), effective_to,
                                                 date('now')) END,
               updated_at = CURRENT_TIMESTAMP
         WHERE student_id = NEW.student_id AND module_code = NEW.module_code;
        {_COPY_IN}
        END""",
    """CREATE TRIGGER IF NOT EXISTS student_modules_mirror_rekey
        AFTER UPDATE OF student_id, module_code ON student_modules
        BEGIN
        UPDATE module_enrolments SET student_id = NEW.student_id, module_code = NEW.module_code,
               updated_at = CURRENT_TIMESTAMP
         WHERE student_id = OLD.student_id AND module_code = OLD.module_code;
        END""",
    """CREATE TRIGGER IF NOT EXISTS student_modules_mirror_delete
        AFTER DELETE ON student_modules
        BEGIN
        DELETE FROM module_enrolments
         WHERE student_id = OLD.student_id AND module_code = OLD.module_code
           AND NOT EXISTS (SELECT 1 FROM attendance_events ae
                            WHERE ae.module_enrolment_id = module_enrolments.module_enrolment_id);
        UPDATE module_enrolments SET status = 'withdrawn',
               effective_to = COALESCE(effective_to, date('now')), updated_at = CURRENT_TIMESTAMP
         WHERE student_id = OLD.student_id AND module_code = OLD.module_code;
        END""",
)

_NEEDED = ("student_modules", "module_enrolments", "programme_registrations", "students",
           "attendance_events")


def _has(execute, name) -> bool:
    return execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                   (name,)).fetchone() is not None


def ready(execute) -> bool:
    return all(_has(execute, t) for t in _NEEDED)


def installed(execute) -> bool:
    return execute("SELECT 1 FROM sqlite_master WHERE type = 'trigger' AND name = ?",
                   (MARKER,)).fetchone() is not None


def _academic_year(today=None) -> str:
    today = today or date.today()
    start = today.year if today.month >= 9 else today.year - 1
    return f"{start}/{start + 1}"


def reconcile(execute) -> dict:
    """Bring ``module_enrolments`` into line with ``student_modules`` once.

    * copies left behind by students who no longer exist are removed (with
      their programme registration), unless attendance refers to them;
    * every ``student_modules`` row gets its copy (making the student's
      programme registration first when they have none and have a course);
    * copies whose status disagrees take ``student_modules``' status.
    Returns counts."""
    done = {"orphan_enrolments_removed": 0, "orphan_registrations_removed": 0,
            "registrations_made": 0, "copies_made": 0, "statuses_fixed": 0,
            "no_course": 0}
    done["orphan_enrolments_removed"] = execute(
        "DELETE FROM module_enrolments WHERE student_id NOT IN (SELECT student_id FROM students) "
        "AND NOT EXISTS (SELECT 1 FROM attendance_events ae WHERE ae.module_enrolment_id = "
        "module_enrolments.module_enrolment_id)").rowcount
    done["orphan_registrations_removed"] = execute(
        "DELETE FROM programme_registrations WHERE student_id NOT IN (SELECT student_id FROM "
        "students) AND NOT EXISTS (SELECT 1 FROM module_enrolments me WHERE me.registration_id "
        "= programme_registrations.registration_id)").rowcount
    year, now = _academic_year(), datetime.now().isoformat(timespec="seconds")
    missing = execute(
        "SELECT sm.student_id, sm.module_code, sm.status, sm.enrollment_date, sm.completion_date, "
        "sm.semester, s.course, s.mode_of_study FROM student_modules sm JOIN students s ON "
        "s.student_id = sm.student_id WHERE NOT EXISTS (SELECT 1 FROM module_enrolments me WHERE "
        "me.student_id = sm.student_id AND me.module_code = sm.module_code)").fetchall()
    for sid, code, status, started, ended, semester, course, mode in missing:
        reg = execute("SELECT registration_id, academic_year FROM programme_registrations WHERE "
                      "student_id = ? ORDER BY registration_id DESC LIMIT 1", (sid,)).fetchone()
        if reg is None:
            if not (course or "").strip():
                done["no_course"] += 1
                continue
            cur = execute(
                "INSERT INTO programme_registrations (student_id, programme_code, academic_year, "
                "occurrence_code, mode_of_study, status, effective_from, registered_at, "
                "registered_by) VALUES (?, ?, ?, 'MAIN', ?, 'registered', ?, ?, "
                "'student_modules')",
                (sid, course, year, mode or "full-time", date.today().isoformat(), now))
            reg = (cur.lastrowid, year)
            done["registrations_made"] += 1
        canonical = "enrolled" if str(status or "Enrolled").lower() == "enrolled" else \
            str(status).lower()
        execute("INSERT INTO module_enrolments (registration_id, student_id, module_code, "
                "academic_year, teaching_period, attempt_number, status, effective_from, "
                "effective_to) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)",
                (reg[0], sid, code, reg[1], semester, canonical,
                 started or date.today().isoformat(),
                 None if canonical == "enrolled" else (ended or date.today().isoformat())))
        done["copies_made"] += 1
    done["statuses_fixed"] = execute(
        f"UPDATE module_enrolments SET status = (SELECT {_STATUS.format(s='sm.status')} FROM "
        "student_modules sm WHERE sm.student_id = module_enrolments.student_id AND "
        "sm.module_code = module_enrolments.module_code), updated_at = CURRENT_TIMESTAMP "
        "WHERE EXISTS (SELECT 1 FROM student_modules sm WHERE sm.student_id = "
        "module_enrolments.student_id AND sm.module_code = module_enrolments.module_code AND "
        f"{_STATUS.format(s='sm.status')} <> LOWER(module_enrolments.status))").rowcount
    return done


def apply(execute) -> dict:
    """Reconcile, then install the triggers. Returns the reconcile counts
    (empty when the tables aren't there yet)."""
    if not ready(execute):
        return {}
    done = reconcile(execute)
    for ddl in TRIGGERS:
        execute(ddl)
    return done
