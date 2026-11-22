"""Expected sessions, register compliance and honest attendance figures.

Attendance percentages used to be "attended ÷ sessions with a record". A
session where nobody took the register simply did not exist, so a student
could look 100% present, and nothing showed which registers were missing.

Here the timetable (``module_schedule``) defines the sessions that should
have happened: each published weekly slot, on its weekday, inside an
academic term, outside holidays, up to its ``recurrence_until``. For each
one we know whether a register was taken (any attendance record for that
module that day). A student's figures then separate:

* attendance rate — present or late, over sessions with a register
  (an excused absence counts neither way; on a register that was taken, a
  student with no record — e.g. never scanned the QR code — was absent);
* register coverage — how many of their expected sessions had a register.

Functions take an open connection and only read.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

WEEKDAYS = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4,
            "saturday": 5, "sunday": 6}
ATTENDED = ("present", "late")
DEFAULT_WINDOW_DAYS = 28


def _d(value):
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _columns(conn, table):
    return {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}


def setting(conn, name, default):
    """An attendance_settings value as an int/float where possible."""
    try:
        row = conn.execute("SELECT setting_value FROM attendance_settings WHERE setting_name = ?",
                           (name,)).fetchone()
    except Exception:
        return default
    if not row or row[0] in (None, ""):
        return default
    try:
        return type(default)(row[0])
    except (TypeError, ValueError):
        return default


# ── calendar ────────────────────────────────────────────────────────────


def term_ranges(conn) -> list[tuple[date, date]]:
    if not _columns(conn, "academic_terms"):
        return []
    out = []
    for start, end in conn.execute("SELECT start_date, end_date FROM academic_terms WHERE "
                                    "COALESCE(status, '') <> 'Superseded'"):
        s, e = _d(start), _d(end)
        if s and e:
            out.append((s, e))
    return out


def current_term(conn, today=None):
    """(start, end) of the term containing today, else None."""
    today = today or date.today()
    for s, e in term_ranges(conn):
        if s <= today <= e:
            return s, e
    return None


def holiday_dates(conn) -> set[date]:
    if not _columns(conn, "holidays"):
        return set()
    days = set()
    for start, end in conn.execute("SELECT start_date, end_date FROM holidays"):
        s, e = _d(start), _d(end) or _d(start)
        while s and e and s <= e:
            days.add(s)
            s += timedelta(days=1)
    return days


def default_window(conn, today=None):
    today = today or date.today()
    term = current_term(conn, today)
    return (term[0], today) if term else (today - timedelta(days=DEFAULT_WINDOW_DAYS), today)


# ── expected sessions ───────────────────────────────────────────────────


def _slots(conn, module_codes=None):
    cols = _columns(conn, "module_schedule")
    if not cols:
        return []
    status = "AND COALESCE(status, 'published') = 'published' " if "status" in cols else ""
    until = "recurrence_until" if "recurrence_until" in cols else "NULL"
    rows = conn.execute(
        f"SELECT id, module_code, day_of_week, start_time, end_time, instructor_id, {until} "
        f"FROM module_schedule WHERE module_code IS NOT NULL {status}").fetchall()  # nosec B608
    return [r for r in rows if module_codes is None or r[1] in module_codes]


def _in_term(day, terms):
    return not terms or any(s <= day <= e for s, e in terms)


def expected_sessions(conn, start=None, end=None, module_codes=None) -> list[dict]:
    """Timetabled sessions between ``start`` and ``end`` (inclusive)."""
    if start is None or end is None:
        start, end = default_window(conn)
    start, end = _d(start) or start, _d(end) or end
    terms, holidays = term_ranges(conn), holiday_dates(conn)
    out = []
    for slot_id, module, weekday, st, et, instructor, until in _slots(conn, module_codes):
        target = WEEKDAYS.get(str(weekday or "").strip().lower())
        if target is None:
            continue
        stop = min(end, _d(until)) if _d(until) else end
        day = start + timedelta(days=(target - start.weekday()) % 7)
        while day <= stop:
            if _in_term(day, terms) and day not in holidays:
                out.append({"slot_id": slot_id, "module_code": module, "date": day.isoformat(),
                            "start_time": st, "end_time": et, "instructor_id": instructor})
            day += timedelta(days=7)
    return sorted(out, key=lambda s: (s["date"], s["start_time"] or "", s["module_code"]))


def registers_taken(conn, start, end) -> set[tuple[str, str]]:
    """{(module_code, date)} with at least one attendance record."""
    return {(r[0], r[1]) for r in conn.execute(
        "SELECT DISTINCT module_code, substr(date, 1, 10) FROM attendance_records "
        "WHERE substr(date, 1, 10) BETWEEN ? AND ?", (str(start), str(end)))}


def register_compliance(conn, start=None, end=None) -> list[dict]:
    """Timetabled sessions in the past with no register, newest first."""
    if start is None or end is None:
        start, end = default_window(conn)
    end = min(_d(end) or end, date.today() - timedelta(days=1))
    if end < (_d(start) or start):
        return []
    taken = registers_taken(conn, start, end)
    names = {r[0]: r[1] for r in conn.execute("SELECT id, COALESCE(first_name || ' ' || last_name, '') "
                                              "FROM instructors")} if _columns(conn, "instructors") else {}
    missing = [dict(s, instructor=names.get(s["instructor_id"], "")) for s in expected_sessions(conn, start, end)
               if (s["module_code"], s["date"]) not in taken]
    return list(reversed(missing))


# ── per-student figures ─────────────────────────────────────────────────


def _student_modules(conn, student_id):
    return {r[0]: _d(r[1]) for r in conn.execute(
        "SELECT module_code, enrollment_date FROM student_modules WHERE student_id = ? "
        "AND LOWER(COALESCE(status, 'enrolled')) IN ('enrolled', 'completed')", (str(student_id),))}


def student_sessions(conn, student_id, start=None, end=None) -> list[dict]:
    """Each expected session for the student, in date order, with an outcome:
    present / late / excused / absent / no_register."""
    if start is None or end is None:
        start, end = default_window(conn)
    modules = _student_modules(conn, student_id)
    if not modules:
        return []
    taken = registers_taken(conn, start, end)
    marks = {}
    for module, day, status in conn.execute(
            "SELECT module_code, substr(date, 1, 10), LOWER(status) FROM attendance_records "
            "WHERE student_id = ? AND substr(date, 1, 10) BETWEEN ? AND ? ORDER BY id",
            (str(student_id), str(start), str(end))):
        marks[(module, day)] = status
    out = []
    for s in expected_sessions(conn, start, end, set(modules)):
        enrolled = modules.get(s["module_code"])
        if enrolled and s["date"] < enrolled.isoformat():
            continue
        key = (s["module_code"], s["date"])
        if key in marks:
            outcome = marks[key] if marks[key] in ("present", "late", "excused") else "absent"
        else:
            outcome = "absent" if key in taken else "no_register"
        out.append(dict(s, outcome=outcome))
    return out


def student_summary(conn, student_id, start=None, end=None) -> dict:
    sessions = student_sessions(conn, student_id, start, end)
    count = {k: sum(1 for s in sessions if s["outcome"] == k)
             for k in ("present", "late", "excused", "absent", "no_register")}
    registered = len(sessions) - count["no_register"]
    counted = count["present"] + count["late"] + count["absent"]
    return {"student_id": str(student_id), "expected": len(sessions), "registered": registered, **count,
            "attendance_pct": round((count["present"] + count["late"]) / counted * 100, 1) if counted else None,
            "coverage_pct": round(registered / len(sessions) * 100, 1) if sessions else None,
            "consecutive_missed": consecutive_missed(sessions)}


def consecutive_missed(sessions) -> int:
    """Unexcused absences in a row, counting back from the latest register.
    Excused sessions and sessions with no register neither count nor break the run."""
    run = 0
    for s in reversed(sessions):
        if s["outcome"] in ("present", "late"):
            break
        if s["outcome"] == "absent":
            run += 1
    return run


def last_engaged(sessions):
    for s in reversed(sessions):
        if s["outcome"] in ATTENDED:
            return s["date"]
    return None
