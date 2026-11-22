"""Acting on attendance: self-certification, UKVI monitoring, non-engagement
cases and student-funding attendance confirmations.

* Self-certification — a student can certify a short illness themselves
  (up to ``self_cert_max_days``, ``self_cert_per_year`` times a year, never
  over an exam). It is an approved absence request, so the database triggers
  mark the covered absences 'excused'.
* UKVI — sponsored students (an active ``visa_records`` row) who miss
  ``ukvi_missed_contact_points`` timetabled sessions in a row are flagged,
  with the reporting deadline (``ukvi_report_working_days`` working days)
  tracked until the case is reported or the student re-engages.
* Non-engagement — a staged case: tutor contact → formal warning → final
  warning → withdrawal recommended → withdrawn, each with a response deadline.
  Withdrawal goes through the student lifecycle service.
* Funding — the per-term list of students to confirm as attending to the
  student finance body, with students who have stopped engaging held back.

Functions take an open connection and do not commit, except
:func:`confirm_withdrawal`, which uses the lifecycle service's transaction.
"""

from __future__ import annotations

import csv
from datetime import date, datetime, timedelta

from education_system.systems.university.application.attendance import registers

ENGAGEMENT_STAGES = ("tutor_contact", "formal_warning", "final_warning", "withdrawal_recommended", "withdrawn")
UKVI_OUTCOMES = ("reported", "re_engaged", "authorised_absence", "closed")
FUNDING_STATUSES = ("attending", "held", "not_attending", "withdrawn")


class EngagementError(ValueError):
    """A rule refused the action; the message is safe to show."""


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _d(value):
    return registers._d(value)


def _reading_week_days(conn) -> set:
    """Published reading weeks: no teaching, but still working days."""
    if not registers._columns(conn, "calendar_key_dates"):
        return set()
    days = set()
    for start, end in conn.execute(
            "SELECT k.start_date, COALESCE(k.end_date, k.start_date) FROM calendar_key_dates k "
            "JOIN calendar_years y ON y.year_code = k.year_code WHERE y.status = 'published' AND "
            "k.kind = 'reading_week'"):
        s, e = _d(start), _d(end)
        while s and e and s <= e:
            days.add(s)
            s += timedelta(days=1)
    return days


def working_days_after(conn, start: date, days: int) -> date:
    """Working days skip weekends, closures and bank holidays (the published
    calendar writes those to ``holidays``) but not reading weeks."""
    holidays = registers.holiday_dates(conn) - _reading_week_days(conn)
    current, left = start, days
    while left > 0:
        current += timedelta(days=1)
        if current.weekday() < 5 and current not in holidays:
            left -= 1
    return current


def academic_year_start(today=None, conn=None) -> date:
    """The published academic year's start; 1 September when none is published."""
    today = today or date.today()
    if conn is not None and registers._columns(conn, "calendar_years"):
        from education_system.systems.university.application.academic_calendar import (
            year as calendar_year,
        )
        row = calendar_year.published_year_for(conn, today.isoformat())
        if row:
            return date.fromisoformat(row["start_date"])
    return date(today.year if today.month >= 9 else today.year - 1, 9, 1)


#: Student route, degree level: the most a sponsored student may work in term time.
TERM_TIME_WORK_HOURS = 20


def student_work_limit(conn, day=None) -> dict:
    """Whether ``day`` is term time for a sponsored student's work limit, from
    the published calendar. Official vacation is the time between terms;
    reading weeks and closures inside a term are still term time."""
    from education_system.systems.university.application.academic_calendar import (
        dates as calendar_dates,
    )
    day = day or date.today()
    covered = calendar_dates.is_term_time(conn, day.isoformat())
    if covered is None:
        return {"date": day.isoformat(), "term_time": None, "weekly_hours": None,
                "term": None, "message": "No published academic year covers this date; "
                                         "check the term dates before advising."}
    term = calendar_dates.term_for(conn, day.isoformat())
    if term:
        return {"date": day.isoformat(), "term_time": True, "weekly_hours": TERM_TIME_WORK_HOURS,
                "term": term["name"], "message": f"Term time ({term['name']} "
                f"{term['year_code']}): up to {TERM_TIME_WORK_HOURS} hours of work a week."}
    return {"date": day.isoformat(), "term_time": False, "weekly_hours": None, "term": None,
            "message": "Official vacation: full-time work is allowed."}


# ── self-certification ──────────────────────────────────────────────────


def _exam_in_range(conn, student_id, start, end):
    if not registers._columns(conn, "exams"):
        return None
    published = "AND COALESCE(e.status, 'published') = 'published' " if "status" in registers._columns(conn, "exams") else ""
    return conn.execute(
        "SELECT e.module_code, e.date FROM exams e JOIN student_modules sm ON sm.module_code = e.module_code "
        f"WHERE sm.student_id = ? AND e.date BETWEEN ? AND ? {published}LIMIT 1",  # nosec B608
        (str(student_id), start.isoformat(), end.isoformat())).fetchone()


def self_certifications(conn, student_id, since=None) -> list[dict]:
    since = since or academic_year_start(conn=conn)
    # One illness is stored as one request per module; count it once.
    cur = conn.execute("SELECT MIN(id), date, date_end, MIN(reason) FROM absence_requests WHERE student_id = ? "
                       "AND COALESCE(self_certified, 0) = 1 AND date >= ? GROUP BY date, date_end ORDER BY date",
                       (str(student_id), since.isoformat()))
    return [dict(zip(("id", "date", "date_end", "reason"), r)) for r in cur.fetchall()]


def self_certify(conn, student_id, start, end, reason, module_code=None) -> int:
    """Record a self-certified illness. Returns the first absence request id."""
    s, e = _d(start), _d(end) or _d(start)
    if not s or not e or e < s:
        raise EngagementError("Give the first and last day of the illness (YYYY-MM-DD).")
    if not (reason or "").strip():
        raise EngagementError("Say briefly what the illness was.")
    max_days = registers.setting(conn, "self_cert_max_days", 7)
    if (e - s).days + 1 > max_days:
        raise EngagementError(f"Self-certification covers up to {max_days} days; longer absences need "
                              "an absence request with evidence.")
    if s > date.today() + timedelta(days=1):
        raise EngagementError("Self-certification is for illness that has started.")
    per_year = registers.setting(conn, "self_cert_per_year", 3)
    if len(self_certifications(conn, student_id)) >= per_year:
        raise EngagementError(f"You have used your {per_year} self-certifications this year; "
                              "please submit an absence request with evidence.")
    exam = _exam_in_range(conn, student_id, s, e)
    if exam:
        raise EngagementError(f"This covers your {exam[0]} exam on {exam[1]}. A missed exam needs a "
                              "missed-exam request so a deferred sitting can be arranged.")
    # absence_requests.module_code is required, so an illness is recorded
    # against each module the student is enrolled on (or the one given).
    modules = [module_code] if module_code else [r[0] for r in conn.execute(
        "SELECT module_code FROM student_modules WHERE student_id = ? "
        "AND LOWER(COALESCE(status, 'enrolled')) = 'enrolled'", (str(student_id),))]
    if not modules:
        raise EngagementError("You are not enrolled on any module.")
    ids = [conn.execute(
        "INSERT INTO absence_requests (student_id, module_code, date, date_end, reason, status, submitted_at, "
        "decided_by, decided_at, decision_reason, is_missed_exam, self_certified) "
        "VALUES (?, ?, ?, ?, ?, 'approved', ?, 'self-certification', ?, 'Self-certified illness', 0, 1)",
        (str(student_id), m, s.isoformat(), e.isoformat(), f"Self-certified: {reason.strip()}",
         _now(), _now())).lastrowid for m in modules]
    return ids[0]


# ── UKVI ────────────────────────────────────────────────────────────────


def sponsored_students(conn) -> list[str]:
    if not registers._columns(conn, "visa_records"):
        return []
    return [r[0] for r in conn.execute(
        "SELECT student_id FROM visa_records WHERE LOWER(COALESCE(status, '')) = 'active' "
        "AND LOWER(COALESCE(visa_type, 'student_route')) IN ('student_route', 'student', 'tier4', 'tier_4')")]


def ukvi_scan(conn, start=None, end=None) -> list[dict]:
    """Flag sponsored students past the missed-contact-point limit (one open
    alert per student). Returns the alerts created."""
    limit = registers.setting(conn, "ukvi_missed_contact_points", 10)
    days = registers.setting(conn, "ukvi_report_working_days", 10)
    if start is None:
        start = date.today() - timedelta(days=120)
    created = []
    for sid in sponsored_students(conn):
        if conn.execute("SELECT 1 FROM ukvi_engagement_alerts WHERE student_id = ? AND status = 'open'",
                        (sid,)).fetchone():
            continue
        sessions = registers.student_sessions(conn, sid, start, end or date.today())
        missed = registers.consecutive_missed(sessions)
        if missed < limit:
            continue
        today = date.today()
        due = working_days_after(conn, today, days)
        alert_id = conn.execute(
            "INSERT INTO ukvi_engagement_alerts (student_id, detected_on, consecutive_missed, last_engaged_on, "
            "report_due) VALUES (?, ?, ?, ?, ?)",
            (sid, today.isoformat(), missed, registers.last_engaged(sessions), due.isoformat())).lastrowid
        conn.execute("INSERT INTO ukvi_engagement_events (student_id, event_type, event_date, notes, recorded_by) "
                     "VALUES (?, 'non_engagement_detected', ?, ?, 'attendance monitor')",
                     (sid, today.isoformat(), f"{missed} consecutive contact points missed"))
        created.append({"id": alert_id, "student_id": sid, "missed": missed, "report_due": due.isoformat()})
    return created


def ukvi_alerts(conn, include_closed=False) -> list[dict]:
    where = "" if include_closed else "WHERE a.status = 'open' "
    cur = conn.execute(
        "SELECT a.*, TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, '')) AS name "
        f"FROM ukvi_engagement_alerts a LEFT JOIN students s ON s.student_id = a.student_id {where}"
        "ORDER BY a.report_due", ())  # nosec B608 - fixed clause
    cols = [d[0] for d in cur.description]
    today = date.today().isoformat()
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    for r in rows:
        r["overdue"] = r["status"] == "open" and r["report_due"] < today
    return rows


def resolve_ukvi_alert(conn, alert_id, outcome, by, reference=None, notes=None) -> None:
    if outcome not in UKVI_OUTCOMES:
        raise EngagementError(f"Outcome must be one of {', '.join(UKVI_OUTCOMES)}.")
    if outcome == "reported" and not (reference or "").strip():
        raise EngagementError("Record the UKVI reference (or the date and method) of the report.")
    row = conn.execute("SELECT student_id, status FROM ukvi_engagement_alerts WHERE id = ?", (alert_id,)).fetchone()
    if row is None:
        raise EngagementError("Alert not found.")
    if row[1] != "open":
        raise EngagementError("This alert is already resolved.")
    conn.execute("UPDATE ukvi_engagement_alerts SET status = ?, ukvi_reference = ?, outcome_notes = ?, "
                 "resolved_by = ?, resolved_at = ? WHERE id = ?",
                 (outcome, reference, notes, by, _now(), alert_id))
    conn.execute("INSERT INTO ukvi_engagement_events (student_id, event_type, event_date, notes, recorded_by) "
                 "VALUES (?, ?, ?, ?, ?)",
                 (row[0], f"alert_{outcome}", date.today().isoformat(),
                  (reference or "") + (f" — {notes}" if notes else ""), by))


# ── non-engagement cases ────────────────────────────────────────────────


def _tutor_for(conn, student_id):
    if registers._columns(conn, "tutor_group_members") and registers._columns(conn, "tutor_groups"):
        row = conn.execute(
            "SELECT g.lead_tutor_id FROM tutor_group_members m JOIN tutor_groups g ON g.group_id = m.group_id "
            "WHERE CAST(m.student_id AS TEXT) = ? AND COALESCE(m.is_active, 1) = 1 LIMIT 1",
            (str(student_id),)).fetchone()
        if row and row[0]:
            return str(row[0])
    return None


def open_case(conn, student_id, reason, actor=None) -> int:
    if conn.execute("SELECT 1 FROM engagement_cases WHERE student_id = ? AND status = 'open'",
                    (str(student_id),)).fetchone():
        raise EngagementError("This student already has an open engagement case.")
    days = registers.setting(conn, "engagement_stage_days", 10)
    case_id = conn.execute(
        "INSERT INTO engagement_cases (student_id, stage, opened_on, opened_reason, tutor_id, due_on) "
        "VALUES (?, 'tutor_contact', ?, ?, ?, ?)",
        (str(student_id), date.today().isoformat(), reason, _tutor_for(conn, student_id),
         (date.today() + timedelta(days=days)).isoformat())).lastrowid
    conn.execute("INSERT INTO engagement_case_history (case_id, from_stage, to_stage, actor, notes, changed_at) "
                 "VALUES (?, NULL, 'tutor_contact', ?, ?, ?)", (case_id, actor, reason, _now()))
    return case_id


def engagement_scan(conn, start=None, end=None, actor="attendance monitor") -> list[dict]:
    """Open a case for each enrolled student below the critical attendance rate
    (with at least four registered sessions) or past the consecutive-absence limit."""
    critical_pct = registers.setting(conn, "attendance_threshold_critical", 70.0)
    critical_run = registers.setting(conn, "consecutive_absences_critical", 3)
    students = [r[0] for r in conn.execute(
        "SELECT DISTINCT student_id FROM student_modules WHERE LOWER(COALESCE(status, 'enrolled')) = 'enrolled' "
        "AND student_id IS NOT NULL")]
    opened = []
    for sid in students:
        if conn.execute("SELECT 1 FROM engagement_cases WHERE student_id = ? AND status = 'open'",
                        (sid,)).fetchone():
            continue
        s = registers.student_summary(conn, sid, start, end)
        low = s["attendance_pct"] is not None and s["registered"] >= 4 and s["attendance_pct"] < critical_pct
        if not low and s["consecutive_missed"] < critical_run:
            continue
        reason = (f"attendance {s['attendance_pct']}% over {s['registered']} registered sessions"
                  if low else f"{s['consecutive_missed']} consecutive unexcused absences")
        opened.append({"case_id": open_case(conn, sid, reason, actor), "student_id": sid, "reason": reason})
    return opened


def cases(conn, include_closed=False) -> list[dict]:
    where = "" if include_closed else "WHERE c.status = 'open' "
    cur = conn.execute(
        "SELECT c.*, TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, '')) AS name "
        f"FROM engagement_cases c LEFT JOIN students s ON s.student_id = c.student_id {where}"
        "ORDER BY c.due_on", ())  # nosec B608 - fixed clause
    cols = [d[0] for d in cur.description]
    today = date.today().isoformat()
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    for r in rows:
        r["overdue"] = r["status"] == "open" and bool(r["due_on"]) and r["due_on"] < today
    return rows


def _case(conn, case_id):
    cur = conn.execute("SELECT * FROM engagement_cases WHERE id = ?", (case_id,))
    row = cur.fetchone()
    if row is None:
        raise EngagementError("Case not found.")
    return dict(zip([d[0] for d in cur.description], row))


def advance_case(conn, case_id, actor, notes=None) -> str:
    """Move a case to its next stage (not to 'withdrawn': see confirm_withdrawal)."""
    case = _case(conn, case_id)
    if case["status"] != "open":
        raise EngagementError("This case is closed.")
    index = ENGAGEMENT_STAGES.index(case["stage"])
    target = ENGAGEMENT_STAGES[index + 1]
    if target == "withdrawn":
        raise EngagementError("Withdrawal is confirmed separately, by someone with authority to withdraw.")
    if not (notes or "").strip():
        raise EngagementError("Record what has happened at this stage (contact made, letter sent…).")
    days = registers.setting(conn, "engagement_stage_days", 10)
    conn.execute("UPDATE engagement_cases SET stage = ?, due_on = ? WHERE id = ?",
                 (target, (date.today() + timedelta(days=days)).isoformat(), case_id))
    conn.execute("INSERT INTO engagement_case_history (case_id, from_stage, to_stage, actor, notes, changed_at) "
                 "VALUES (?, ?, ?, ?, ?, ?)", (case_id, case["stage"], target, actor, notes, _now()))
    return target


def resolve_case(conn, case_id, actor, reason) -> None:
    """The student re-engaged (or the case was raised in error)."""
    case = _case(conn, case_id)
    if case["status"] != "open":
        raise EngagementError("This case is already closed.")
    if not (reason or "").strip():
        raise EngagementError("Say why the case is being closed.")
    conn.execute("UPDATE engagement_cases SET status = 'resolved', closed_on = ?, closed_reason = ? WHERE id = ?",
                 (date.today().isoformat(), reason, case_id))
    conn.execute("INSERT INTO engagement_case_history (case_id, from_stage, to_stage, actor, notes, changed_at) "
                 "VALUES (?, ?, 'resolved', ?, ?, ?)", (case_id, case["stage"], actor, reason, _now()))


def case_history(conn, case_id) -> list[dict]:
    cur = conn.execute("SELECT from_stage, to_stage, actor, notes, changed_at FROM engagement_case_history "
                       "WHERE case_id = ? ORDER BY id", (case_id,))
    return [dict(zip(("from_stage", "to_stage", "actor", "notes", "changed_at"), r)) for r in cur.fetchall()]


def confirm_withdrawal(case_id, actor, reason, db_path=None) -> None:
    """Withdraw the student through the lifecycle service, then close the case.

    The case must have reached 'withdrawal_recommended'. Uses its own
    connections: the lifecycle service runs its own transaction.
    """
    from education_system.systems.university.application.students.lifecycle import StudentLifecycleService
    from education_system.systems.university.infrastructure.database.db import get_connection
    conn = get_connection(db_path)
    try:
        case = _case(conn, case_id)
    finally:
        conn.close()
    if case["status"] != "open" or case["stage"] != "withdrawal_recommended":
        raise EngagementError("Only an open case at 'withdrawal recommended' can be confirmed.")
    StudentLifecycleService(db_path).deactivate(
        case["student_id"], actor_id=actor, reason=f"Non-engagement: {reason}",
        idempotency_key=f"engagement-case:{case_id}:withdrawn")
    conn = get_connection(db_path)
    try:
        conn.execute("UPDATE engagement_cases SET stage = 'withdrawn', status = 'withdrawn', closed_on = ?, "
                     "closed_reason = ? WHERE id = ?", (date.today().isoformat(), reason, case_id))
        conn.execute("INSERT INTO engagement_case_history (case_id, from_stage, to_stage, actor, notes, changed_at) "
                     "VALUES (?, 'withdrawal_recommended', 'withdrawn', ?, ?, ?)", (case_id, actor, reason, _now()))
        conn.commit()
    finally:
        conn.close()


# ── student funding attendance confirmation ─────────────────────────────


def funding_candidates(conn, term_name) -> list[dict]:
    """Suggested confirmation per enrolled student for a term."""
    row = conn.execute("SELECT start_date, end_date, academic_year FROM academic_terms WHERE name = ? "
                       "ORDER BY COALESCE(status, '') = 'Superseded'",
                       (term_name,)).fetchone() if registers._columns(conn, "academic_terms") else None
    if row is None:
        raise EngagementError(f"No academic term called {term_name!r}.")
    start, end = _d(row[0]), min(_d(row[1]) or date.today(), date.today())
    open_stage = {r[0]: r[1] for r in conn.execute(
        "SELECT student_id, stage FROM engagement_cases WHERE status = 'open'")}
    out = []
    for sid, status, name in conn.execute(
            "SELECT DISTINCT s.student_id, COALESCE(s.status, 'Active'), "
            "       TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, '')) "
            "FROM students s JOIN student_modules sm ON sm.student_id = s.student_id"):
        summary = registers.student_summary(conn, sid, start, end)
        stage = open_stage.get(sid)
        if str(status).lower() in ("withdrawn", "inactive"):
            suggested, why = "withdrawn", "student record withdrawn"
        elif stage and ENGAGEMENT_STAGES.index(stage) >= ENGAGEMENT_STAGES.index("formal_warning"):
            suggested, why = "held", f"engagement case at {stage.replace('_', ' ')}"
        elif summary["registered"] and not (summary["present"] + summary["late"]):
            suggested, why = "held", "no recorded attendance this term"
        else:
            suggested, why = "attending", ""
        out.append({"student_id": sid, "name": name, "suggested": suggested, "why": why,
                    "attendance_pct": summary["attendance_pct"], "academic_year": row[2]})
    return out


def confirm_funding(conn, term_name, decisions, by, academic_year=None, notes=None) -> int:
    """Record confirmations: {student_id: status}."""
    bad = {s for s in decisions.values() if s not in FUNDING_STATUSES}
    if bad:
        raise EngagementError(f"Status must be one of {', '.join(FUNDING_STATUSES)}.")
    for sid, status in decisions.items():
        conn.execute(
            "INSERT INTO funding_attendance_confirmations (student_id, term_name, academic_year, status, notes, "
            "confirmed_by, confirmed_at) VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (student_id, term_name) DO UPDATE SET status = excluded.status, notes = excluded.notes, "
            "confirmed_by = excluded.confirmed_by, confirmed_at = excluded.confirmed_at",
            (str(sid), term_name, academic_year, status, notes, by, _now()))
    return len(decisions)


def export_funding(conn, term_name, path) -> int:
    rows = conn.execute("SELECT student_id, term_name, academic_year, status, confirmed_by, confirmed_at, notes "
                        "FROM funding_attendance_confirmations WHERE term_name = ? ORDER BY student_id",
                        (term_name,)).fetchall()
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["StudentID", "Term", "AcademicYear", "Status", "ConfirmedBy", "ConfirmedAt", "Notes"])
        writer.writerows(rows)
    return len(rows)
