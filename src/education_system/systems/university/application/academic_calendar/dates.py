"""Working out dates from an academic year: UK bank holidays, teaching
weeks, term time and vacations (UKVI work limits, sponsor monitoring),
the checks run before publishing, dates imported from the systems that
own them, and rolling a year forward.

* **Bank holidays** are computed for England & Wales, Scotland or Northern
  Ireland, with weekend substitutes. One-off holidays (a coronation, say)
  are added by hand as key dates.
* **Weeks** count from the Monday of each term's first week (as the
  timetable does); a week is a teaching week unless it is a reading week
  or entirely a closure.
* **Term time** is inside a published term and not on a closure, bank
  holiday or reading week; everything else in the year is vacation.
* **Imports** replace this year's imported key dates from module
  registration periods, published exams, graduation ceremonies and
  assessment boards.
* **Rollover** copies a year forward by whole weeks (so weekdays stay the
  same), recomputes bank holidays and leaves imported dates behind.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

from datetime import date, timedelta

from education_system.systems.university.application.academic_calendar import access as ca
from education_system.systems.university.application.academic_calendar import year as cy

REGIONS = ("england-and-wales", "scotland", "northern-ireland")


# ── bank holidays ───────────────────────────────────────────────────────


def _easter(year: int) -> date:
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    month = (h + l_ - 7 * m + 114) // 31
    day = (h + l_ - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def _first_monday(year, month) -> date:
    d = date(year, month, 1)
    return d + timedelta(days=(0 - d.weekday()) % 7)


def _last_monday(year, month) -> date:
    d = date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)
    return d - timedelta(days=d.weekday())


def _substitute(days: list[tuple[str, date]]) -> list[tuple[str, date]]:
    """Move weekend holidays to the next free weekday."""
    taken, out = set(), []
    for name, day in sorted(days, key=lambda x: x[1]):
        actual = day
        while actual.weekday() >= 5 or actual in taken:
            actual += timedelta(days=1)
        taken.add(actual)
        out.append((name + (" (substitute day)" if actual != day else ""), actual))
    return out


def bank_holidays(year: int, region="england-and-wales") -> list[tuple[str, date]]:
    easter = _easter(year)
    fixed = [("New Year's Day", date(year, 1, 1)), ("Christmas Day", date(year, 12, 25)),
             ("Boxing Day", date(year, 12, 26))]
    if region == "scotland":
        fixed += [("2nd January", date(year, 1, 2)), ("St Andrew's Day", date(year, 11, 30))]
    if region == "northern-ireland":
        fixed += [("St Patrick's Day", date(year, 3, 17)),
                  ("Battle of the Boyne", date(year, 7, 12))]
    moving = [("Good Friday", easter - timedelta(days=2)),
              ("Early May bank holiday", _first_monday(year, 5)),
              ("Spring bank holiday", _last_monday(year, 5))]
    if region == "scotland":
        moving.append(("Summer bank holiday", _first_monday(year, 8)))
    else:
        moving += [("Easter Monday", easter + timedelta(days=1)),
                   ("Summer bank holiday", _last_monday(year, 8))]
    return sorted(_substitute(fixed) + moving, key=lambda x: x[1])


def add_bank_holidays(conn, year_code) -> int:
    """Replace the year's computed bank holidays (manual ones are kept)."""
    row = cy.year(conn, year_code)
    start, end = date.fromisoformat(row["start_date"]), date.fromisoformat(row["end_date"])
    conn.execute("DELETE FROM calendar_key_dates WHERE year_code = ? AND kind = 'bank_holiday' "
                 "AND source = 'computed'", (year_code,))
    added = 0
    for y in range(start.year, end.year + 1):
        for name, day in bank_holidays(y, row["bank_holiday_region"]):
            if start <= day <= end:
                conn.execute("INSERT INTO calendar_key_dates (year_code, kind, title, start_date, "
                             "audience, source) VALUES (?, 'bank_holiday', ?, ?, 'all', "
                             "'computed')", (year_code, name, day.isoformat()))
                added += 1
    return added


# ── weeks, term time, vacations ─────────────────────────────────────────


def _no_teaching_days(conn, year_code) -> tuple[set, set]:
    """``(reading-week days, closure/bank-holiday days)``."""
    reading, closed = set(), set()
    for d in cy.key_dates(conn, year_code):
        if d["kind"] not in cy.NO_TEACHING:
            continue
        s = date.fromisoformat(d["start_date"])
        e = date.fromisoformat(d["end_date"] or d["start_date"])
        target = reading if d["kind"] == "reading_week" else closed
        while s <= e:
            target.add(s)
            s += timedelta(days=1)
    return reading, closed


def weeks(conn, year_code) -> list[dict]:
    """Every week of every term: term week number, teaching week number
    (reading weeks and fully closed weeks don't count) and why not."""
    reading, closed = _no_teaching_days(conn, year_code)
    out = []
    for t in cy.terms(conn, year_code):
        start, end = date.fromisoformat(t["start_date"]), date.fromisoformat(t["end_date"])
        monday = start - timedelta(days=start.weekday())
        n, teaching_n = 0, 0
        while monday <= end:
            n += 1
            weekdays = [monday + timedelta(days=i) for i in range(5)
                        if start <= monday + timedelta(days=i) <= end]
            is_reading = any(d in reading for d in weekdays)
            all_closed = bool(weekdays) and all(d in closed for d in weekdays)
            teaching = bool(weekdays) and not is_reading and not all_closed
            teaching_n += teaching
            out.append({"term": t["name"], "week": n, "teaching_week": teaching_n if teaching
                        else None, "start": monday.isoformat(),
                        "end": (monday + timedelta(days=6)).isoformat(), "teaching": teaching,
                        "why_not": "reading week" if is_reading else ("closed" if all_closed
                                                                      else None)})
            monday += timedelta(days=7)
    return out


def _published_year(conn, day: date) -> dict | None:
    return cy.published_year_for(conn, day.isoformat())


def term_for(conn, day=None) -> dict | None:
    """The published term containing ``day``, or None (vacation)."""
    day = date.fromisoformat(ca.iso_date(day, "Date") or ca.today())
    row = _published_year(conn, day)
    if not row:
        return None
    for t in cy.terms(conn, row["year_code"]):
        if t["start_date"] <= day.isoformat() <= t["end_date"]:
            return {**t, "year_code": row["year_code"]}
    return None


def is_term_time(conn, day=None) -> bool | None:
    """True in term (not on a closure, bank holiday or reading week), False
    in vacation, None when no published year covers the day."""
    day = date.fromisoformat(ca.iso_date(day, "Date") or ca.today())
    row = _published_year(conn, day)
    if not row:
        return None
    if term_for(conn, day) is None:
        return False
    reading, closed = _no_teaching_days(conn, row["year_code"])
    return day not in reading and day not in closed


def vacation_periods(conn, year_code) -> list[dict]:
    """Gaps between terms (and before/after them) inside the year."""
    row = cy.year(conn, year_code)
    out, cursor = [], date.fromisoformat(row["start_date"])
    for t in cy.terms(conn, year_code):
        start = date.fromisoformat(t["start_date"])
        if start > cursor:
            out.append({"start": cursor.isoformat(),
                        "end": (start - timedelta(days=1)).isoformat(),
                        "before": t["name"]})
        cursor = max(cursor, date.fromisoformat(t["end_date"]) + timedelta(days=1))
    end = date.fromisoformat(row["end_date"])
    if cursor <= end:
        out.append({"start": cursor.isoformat(), "end": end.isoformat(), "before": None})
    return out


# ── checks ──────────────────────────────────────────────────────────────


def _off_days(conn, year_code) -> dict:
    """date → why nothing should be scheduled (closure / bank holiday)."""
    off = {}
    for d in cy.key_dates(conn, year_code):
        if d["kind"] in ("closure", "bank_holiday"):
            s = date.fromisoformat(d["start_date"])
            e = date.fromisoformat(d["end_date"] or d["start_date"])
            while s <= e:
                off[s.isoformat()] = d["title"]
                s += timedelta(days=1)
    return off


def _scheduled_things(conn, start, end) -> list[tuple[str, str]]:
    """``(date, what)`` for exams and deadlines in the period."""
    found = []
    if ca.has_table(conn, "exams"):
        found += [(str(r[0])[:10], f"Exam {r[1]}") for r in conn.execute(
            "SELECT date, COALESCE(exam_name, module_code) FROM exams WHERE date BETWEEN ? AND ? "
            "AND COALESCE(status, 'published') <> 'cancelled'", (start, end))]
    if ca.has_table(conn, "unified_events"):
        found += [(str(r[0])[:10], f"{r[2]}: {r[1]}") for r in conn.execute(
            "SELECT COALESCE(start_datetime, event_date), title, event_type FROM unified_events "
            "WHERE LOWER(COALESCE(event_type, '')) IN ('exam', 'assignment deadline', "
            "'deadline', 'assessment') AND COALESCE(start_datetime, event_date) BETWEEN ? AND ?",
            (start, end + "T23:59"))]
    return found


def _clashes(conn, year_code, row, term_list) -> list[str]:
    """Exams and deadlines on closures / bank holidays, and exams outside term."""
    off = _off_days(conn, year_code)
    things = _scheduled_things(conn, row["start_date"], row["end_date"])
    clashes = [f"{what} on {day} ({off[day]})" for day, what in things if day in off]
    in_term = [(t["start_date"], t["end_date"]) for t in term_list]
    clashes += [f"{what} on {day} is outside term" for day, what in things
                if what.startswith("Exam") and not any(s <= day <= e for s, e in in_term)]
    return clashes


def check_year(conn, year_code) -> dict:
    """``errors`` stop publishing; ``warnings`` and ``clashes`` are shown."""
    row = cy.year(conn, year_code)
    errors, warnings = [], []
    term_list = cy.terms(conn, year_code)
    if not term_list:
        errors.append("The year has no terms")
    for a, b in zip(term_list, term_list[1:]):
        if b["start_date"] <= a["end_date"]:
            errors.append(f"{a['name']} and {b['name']} overlap")
    by_term: dict[str, int] = {}
    for w in weeks(conn, year_code):
        by_term[w["term"]] = by_term.get(w["term"], 0) + int(w["teaching"])
    errors += [f"{name} has no teaching weeks" for name, n in by_term.items() if n == 0]
    kinds = {d["kind"] for d in cy.key_dates(conn, year_code)}
    warnings += [f"No {cy.KINDS[k].lower()} date" for k in cy.RECOMMENDED if k not in kinds]
    clashes = _clashes(conn, year_code, row, term_list)
    if ca.has_table(conn, "registration_periods"):
        for r in ca.dicts(conn.execute("SELECT name, registration_opens, registration_closes "
                                       "FROM registration_periods WHERE academic_year = ?",
                                       (year_code,))):
            if r["registration_opens"] < row["start_date"] and \
                    r["registration_closes"] < row["start_date"]:
                warnings.append(f"Registration period {r['name']} ends before the year starts")
    return {"errors": errors, "warnings": warnings, "clashes": clashes,
            "teaching_weeks": by_term}


# ── imports from the systems that own the dates ─────────────────────────


def _imported(conn, year_code, kind, title, start, end, source, ref, audience="all"):
    conn.execute("INSERT INTO calendar_key_dates (year_code, kind, title, start_date, end_date, "
                 "audience, source, source_ref) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                 (year_code, kind, title, start[:10], end[:10] if end else None, audience,
                  source, ref))


def import_dates(conn, who, year_code) -> dict:
    """Replace the year's imported key dates from their owning systems."""
    row = cy._draft(conn, who, year_code)
    s, e = row["start_date"], row["end_date"]
    conn.execute("DELETE FROM calendar_key_dates WHERE year_code = ? AND source NOT IN "
                 "('manual', 'computed')", (year_code,))
    counts = {}
    if ca.has_table(conn, "registration_periods"):
        for r in ca.dicts(conn.execute("SELECT * FROM registration_periods WHERE "
                                       "registration_opens <= ? AND registration_closes >= ?",
                                       (e, s))):
            _imported(conn, year_code, "registration", r.get("name") or "Module registration",
                      max(r["registration_opens"], s), min(r["registration_closes"], e),
                      "registration_periods", r["period_id"], "students")
            counts["registration"] = counts.get("registration", 0) + 1
    if ca.has_table(conn, "exams"):
        span = conn.execute("SELECT MIN(date), MAX(date), COUNT(*) FROM exams WHERE "
                            "COALESCE(status, 'published') = 'published' AND date BETWEEN ? AND "
                            "?", (s, e)).fetchone()
        if span and span[2]:
            _imported(conn, year_code, "exam_period", "Exams (published timetable)", span[0],
                      span[1], "exams", f"{span[2]} sittings")
            counts["exams"] = span[2]
    if ca.has_table(conn, "graduation_ceremonies"):
        for r in ca.dicts(conn.execute("SELECT ceremony_id, ceremony_name, ceremony_date FROM "
                                       "graduation_ceremonies WHERE COALESCE(status, "
                                       "'scheduled') = 'scheduled' AND ceremony_date BETWEEN ? "
                                       "AND ?", (s, e))):
            _imported(conn, year_code, "graduation", r["ceremony_name"], r["ceremony_date"], None,
                      "graduation_ceremonies", r["ceremony_id"])
            counts["graduation"] = counts.get("graduation", 0) + 1
    if ca.has_table(conn, "assessment_boards"):
        for r in ca.dicts(conn.execute("SELECT board_id, name, meeting_at FROM assessment_boards "
                                       "WHERE meeting_at BETWEEN ? AND ?", (s, e + "T23:59"))):
            _imported(conn, year_code, "assessment_board", r["name"], r["meeting_at"], None,
                      "assessment_boards", r["board_id"], "staff")
            counts["boards"] = counts.get("boards", 0) + 1
    ca.audit(conn, who, "year", year_code, "imported", counts)
    return counts


# ── rollover ────────────────────────────────────────────────────────────


def rollover(conn, who, from_code, to_code=None) -> str:
    """Create the next year as a draft from ``from_code``."""
    src = cy.year(conn, from_code)
    first = int(from_code[:4]) + 1
    to_code = cy._year_code(to_code or f"{first}/{first + 1}")
    old_start = date.fromisoformat(src["start_date"])
    target = date(old_start.year + 1, old_start.month, min(old_start.day, 28))
    shift = timedelta(weeks=round((target - old_start).days / 7))
    move = lambda d: (date.fromisoformat(d) + shift).isoformat() if d else None  # noqa: E731
    # The year itself moves by a calendar year; its terms and dates by whole weeks.
    one_year = lambda d: date(d.year + 1, d.month, min(d.day, 28) if d.month == 2  # noqa: E731
                              else d.day).isoformat()
    cy.create_year(conn, who, to_code, one_year(old_start),
                   one_year(date.fromisoformat(src["end_date"])), src["bank_holiday_region"])
    for t in cy.terms(conn, from_code):
        conn.execute("INSERT INTO calendar_terms (year_code, name, start_date, end_date, "
                     "sort_order) VALUES (?, ?, ?, ?, ?)",
                     (to_code, t["name"], move(t["start_date"]), move(t["end_date"]),
                      t["sort_order"]))
    for d in cy.key_dates(conn, from_code):
        if d["source"] != "manual":
            continue
        conn.execute("INSERT INTO calendar_key_dates (year_code, kind, title, start_date, "
                     "end_date, audience, notes, source) VALUES (?, ?, ?, ?, ?, ?, ?, 'manual')",
                     (to_code, d["kind"], d["title"], move(d["start_date"]),
                      move(d["end_date"]), d["audience"],
                      ((d["notes"] or "") + " — check: rolled forward").strip(" —")))
    ca.audit(conn, who, "year", to_code, "rolled_over", {"from": from_code,
                                                          "shift_days": shift.days})
    return to_code
