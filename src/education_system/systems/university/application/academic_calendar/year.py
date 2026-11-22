"""Academic years: draft → published.

A year (``2026/2027``, the format the registration and evaluation rules
use) holds its terms and key dates. Calendar administrators edit a draft;
publishing it:

* writes its terms into ``academic_terms`` as "<term> <year>" (the name is
  unique across years), updating rows of that name in place so course
  sections keep their term — the table timetables,
  registers, module registration and evaluation already read — and marks
  other terms that overlap the year ``Superseded``;
* writes closures, bank holidays and reading weeks into ``holidays`` (so no
  teaching or registers fall on them);
* keeps the older ``academic_years`` / ``semesters`` tables in step;
* records a snapshot and tells staff and students what changed since the
  last publication.

A published year can be reopened as a draft; nothing changes for anyone
until it is published again.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

import json
import re
from datetime import date

from education_system.systems.university.application.academic_calendar import access as ca

KINDS = {
    "enrolment": "Enrolment / registration week", "teaching": "Teaching",
    "reading_week": "Reading week", "exam_period": "Exam period",
    "resit_period": "Resit period", "assessment_board": "Assessment board",
    "results_release": "Results release", "census_hesa": "HESA census date",
    "census_slc": "Student Loans Company attendance confirmation", "closure": "University closure",
    "bank_holiday": "Bank holiday", "registration": "Module registration",
    "graduation": "Graduation", "deadline": "Deadline", "other": "Other",
}
NO_TEACHING = ("closure", "bank_holiday", "reading_week")
RECOMMENDED = ("enrolment", "exam_period", "results_release", "census_hesa")
_YEAR = re.compile(r"^(\d{4})/(\d{4})$")


def _year_code(value) -> str:
    text = str(value or "").strip().replace("-", "/")
    m = _YEAR.match(text)
    if not m or int(m.group(2)) != int(m.group(1)) + 1:
        raise ValueError("The year looks like 2026/2027")
    return text


def year(conn, year_code) -> dict:
    ca.ensure(conn)
    row = ca.one(conn, "SELECT * FROM calendar_years WHERE year_code = ?", (year_code,))
    if not row:
        raise ValueError(f"No academic year {year_code}")
    return row


def years(conn) -> list[dict]:
    ca.ensure(conn)
    return ca.dicts(conn.execute("SELECT * FROM calendar_years ORDER BY start_date DESC"))


def _draft(conn, who, year_code) -> dict:
    ca.require_admin(who)
    row = year(conn, year_code)
    if row["status"] != "draft":
        raise ValueError(f"{year_code} is published; reopen it as a draft to change it")
    return row


def create_year(conn, who, year_code, start, end, region="england-and-wales") -> str:
    ca.ensure(conn)
    ca.require_admin(who)
    code = _year_code(year_code)
    start = ca.iso_date(start, "Year start", True)
    end = ca.iso_date(end, "Year end", True)
    if end <= start:
        raise ValueError("The year must end after it starts")
    if conn.execute("SELECT 1 FROM calendar_years WHERE year_code = ?", (code,)).fetchone():
        raise ValueError(f"{code} already exists")
    clash = conn.execute("SELECT year_code FROM calendar_years WHERE start_date <= ? AND end_date "
                         ">= ?", (end, start)).fetchone()
    if clash:
        raise ValueError(f"The dates overlap {clash[0]}")
    from education_system.systems.university.application.academic_calendar import (
        dates as calendar_dates,
    )
    if region not in calendar_dates.REGIONS:
        raise ValueError("Region must be one of " + ", ".join(calendar_dates.REGIONS))
    conn.execute("INSERT INTO calendar_years (year_code, start_date, end_date, "
                 "bank_holiday_region, created_by) VALUES (?, ?, ?, ?, ?)",
                 (code, start, end, region, who.username))
    calendar_dates.add_bank_holidays(conn, code)
    ca.audit(conn, who, "year", code, "created", {"start": start, "end": end})
    return code


def update_year(conn, who, year_code, start=None, end=None, notes=None) -> None:
    row = _draft(conn, who, year_code)
    start = ca.iso_date(start, "Year start") or row["start_date"]
    end = ca.iso_date(end, "Year end") or row["end_date"]
    if end <= start:
        raise ValueError("The year must end after it starts")
    conn.execute("UPDATE calendar_years SET start_date = ?, end_date = ?, notes = COALESCE(?, "
                 "notes) WHERE year_code = ?", (start, end, notes, year_code))
    from education_system.systems.university.application.academic_calendar import (
        dates as calendar_dates,
    )
    calendar_dates.add_bank_holidays(conn, year_code)
    ca.audit(conn, who, "year", year_code, "edited", {"start": start, "end": end})


def reopen(conn, who, year_code) -> None:
    ca.require_admin(who)
    row = year(conn, year_code)
    if row["status"] != "published":
        raise ValueError("Only a published year can be reopened")
    conn.execute("UPDATE calendar_years SET status = 'draft' WHERE year_code = ?", (year_code,))
    ca.audit(conn, who, "year", year_code, "reopened")


# ── terms ───────────────────────────────────────────────────────────────


def terms(conn, year_code) -> list[dict]:
    ca.ensure(conn)
    return ca.dicts(conn.execute("SELECT * FROM calendar_terms WHERE year_code = ? ORDER BY "
                                 "start_date", (year_code,)))


def save_term(conn, who, year_code, name, start, end, term_id=None) -> int:
    row = _draft(conn, who, year_code)
    name = ca.text(name, "Term name", True)
    start = ca.iso_date(start, "Term start", True)
    end = ca.iso_date(end, "Term end", True)
    if end <= start:
        raise ValueError("A term must end after it starts")
    if start < row["start_date"] or end > row["end_date"]:
        raise ValueError(f"Terms must fall inside {row['start_date']} – {row['end_date']}")
    for other in terms(conn, year_code):
        if other["term_id"] != term_id and other["start_date"] <= end and \
                other["end_date"] >= start:
            raise ValueError(f"That overlaps {other['name']}")
    if term_id:
        if not conn.execute("UPDATE calendar_terms SET name = ?, start_date = ?, end_date = ? "
                            "WHERE term_id = ? AND year_code = ?",
                            (name, start, end, term_id, year_code)).rowcount:
            raise ValueError("No such term")
    else:
        term_id = conn.execute("INSERT INTO calendar_terms (year_code, name, start_date, "
                               "end_date) VALUES (?, ?, ?, ?)",
                               (year_code, name, start, end)).lastrowid
    _renumber(conn, year_code)
    ca.audit(conn, who, "term", f"{year_code}:{name}", "saved", {"start": start, "end": end})
    return int(term_id)


def delete_term(conn, who, year_code, term_id) -> None:
    _draft(conn, who, year_code)
    if not conn.execute("DELETE FROM calendar_terms WHERE term_id = ? AND year_code = ?",
                        (term_id, year_code)).rowcount:
        raise ValueError("No such term")
    _renumber(conn, year_code)
    ca.audit(conn, who, "term", term_id, "deleted")


def _renumber(conn, year_code) -> None:
    for n, t in enumerate(terms(conn, year_code), 1):
        conn.execute("UPDATE calendar_terms SET sort_order = ? WHERE term_id = ?",
                     (n, t["term_id"]))


# ── key dates ───────────────────────────────────────────────────────────


def key_dates(conn, year_code, audience=None) -> list[dict]:
    ca.ensure(conn)
    sql = "SELECT * FROM calendar_key_dates WHERE year_code = ?"
    params = [year_code]
    if audience:
        sql += " AND audience IN ('all', ?)"
        params.append(audience)
    return ca.dicts(conn.execute(sql + " ORDER BY start_date, kind", params))


def save_key_date(conn, who, year_code, kind, title, start, end=None, audience="all",
                  notes="", key_date_id=None) -> int:
    row = _draft(conn, who, year_code)
    if kind not in KINDS:
        raise ValueError("Kind must be one of " + ", ".join(KINDS))
    if audience not in ("all", "students", "staff"):
        raise ValueError("Audience must be all, students or staff")
    start = ca.iso_date(start, "Date", True)
    end = ca.iso_date(end, "End date")
    if end and end < start:
        raise ValueError("The end cannot be before the start")
    if start < row["start_date"] or (end or start) > row["end_date"]:
        raise ValueError(f"Key dates must fall inside {row['start_date']} – {row['end_date']}")
    values = (kind, ca.text(title, "Title", True) or KINDS[kind], start, end, audience,
              notes or None)
    if key_date_id:
        if not conn.execute("UPDATE calendar_key_dates SET kind = ?, title = ?, start_date = ?, "
                            "end_date = ?, audience = ?, notes = ? WHERE key_date_id = ? AND "
                            "year_code = ? AND source = 'manual'",
                            (*values, key_date_id, year_code)).rowcount:
            raise ValueError("No such key date (imported dates change at their source)")
    else:
        key_date_id = conn.execute("INSERT INTO calendar_key_dates (kind, title, start_date, "
                                   "end_date, audience, notes, year_code) VALUES (?, ?, ?, ?, ?, "
                                   "?, ?)", (*values, year_code)).lastrowid
    ca.audit(conn, who, "key_date", key_date_id, "saved", {"kind": kind, "start": start})
    return int(key_date_id)


def delete_key_date(conn, who, year_code, key_date_id) -> None:
    _draft(conn, who, year_code)
    if not conn.execute("DELETE FROM calendar_key_dates WHERE key_date_id = ? AND year_code = ?",
                        (key_date_id, year_code)).rowcount:
        raise ValueError("No such key date")
    ca.audit(conn, who, "key_date", key_date_id, "deleted")


# ── publishing ──────────────────────────────────────────────────────────


def _snapshot(conn, year_code) -> dict:
    return {"terms": [{k: t[k] for k in ("name", "start_date", "end_date")}
                      for t in terms(conn, year_code)],
            "key_dates": [{k: d[k] for k in ("kind", "title", "start_date", "end_date",
                                              "audience")} for d in key_dates(conn, year_code)]}


def _diff(old, new) -> list[str]:
    changes = []
    key = lambda d: (d.get("kind", "term"), d.get("title") or d.get("name"))  # noqa: E731
    for section in ("terms", "key_dates"):
        before = {key(d): d for d in old.get(section, [])}
        after = {key(d): d for d in new.get(section, [])}
        for k, d in after.items():
            label = d.get("title") or d.get("name")
            when = d["start_date"] + (f" – {d['end_date']}" if d.get("end_date") else "")
            if k not in before:
                changes.append(f"Added: {label} ({when})")
            elif (before[k]["start_date"], before[k].get("end_date")) != (d["start_date"],
                                                                           d.get("end_date")):
                changes.append(f"Moved: {label} from {before[k]['start_date']} to {when}")
        changes += [f"Removed: {d.get('title') or d.get('name')}" for k, d in before.items()
                    if k not in after]
    return changes


def preview_publish(conn, who, year_code) -> dict:
    """What publishing would do: problems that block it, warnings, the
    changes since last time and the existing terms it would supersede."""
    from education_system.systems.university.application.academic_calendar import (
        dates as calendar_dates,
    )
    ca.require_admin(who)
    row = year(conn, year_code)
    check = calendar_dates.check_year(conn, year_code)
    last = ca.one(conn, "SELECT snapshot_json FROM calendar_published_snapshots WHERE year_code "
                        "= ? ORDER BY version DESC LIMIT 1", (year_code,))
    changes = _diff(json.loads(last["snapshot_json"]) if last else {}, _snapshot(conn, year_code))
    overlapping = ca.dicts(conn.execute(
        "SELECT id, name, academic_year, start_date, end_date FROM academic_terms WHERE "
        "COALESCE(source, '') <> 'calendar' AND COALESCE(status, '') <> 'Superseded' AND "
        "start_date <= ? AND end_date >= ? AND NOT (academic_year = ? AND name IN (SELECT name "
        "FROM calendar_terms WHERE year_code = ?)) AND name NOT IN (SELECT name || ' ' || "
        "year_code FROM calendar_terms WHERE year_code = ?)",
        (row["end_date"], row["start_date"], year_code, year_code, year_code)))
    return {**check, "changes": changes, "supersedes": overlapping,
            "version": row["version"] + 1}


def publish(conn, who, year_code, note="") -> dict:
    """Publish the draft (see the module docstring). Returns the preview
    plus ``emails`` for the change notice."""
    preview = preview_publish(conn, who, year_code)
    if preview["errors"]:
        raise ValueError("Cannot publish: " + "; ".join(preview["errors"]))
    row = _draft(conn, who, year_code)
    _write_terms(conn, year_code, preview["supersedes"])
    _write_holidays(conn, year_code)
    _write_legacy(conn, row)
    version = row["version"] + 1
    conn.execute("UPDATE calendar_years SET status = 'published', version = ?, published_at = ?, "
                 "published_by = ? WHERE year_code = ?",
                 (version, ca.now(), who.username, year_code))
    conn.execute("INSERT INTO calendar_published_snapshots (year_code, version, snapshot_json, "
                 "published_by, changes_json) VALUES (?, ?, ?, ?, ?)",
                 (year_code, version, json.dumps(_snapshot(conn, year_code)), who.username,
                  json.dumps(preview["changes"])))
    ca.audit(conn, who, "year", year_code, "published",
             {"version": version, "changes": preview["changes"], "note": note})
    emails = _announce(conn, year_code, version, preview["changes"], note)
    _publish_event(year_code)
    return {**preview, "version": version, "emails": emails}


def published_term_name(year_code, name) -> str:
    """``academic_terms.name`` is unique across years, so a published term is
    named with its year: "Autumn 2026/2027"."""
    return f"{name} {year_code}"


def _write_terms(conn, year_code, supersede) -> None:
    for t in terms(conn, year_code):
        weeks = _teaching_weeks(conn, year_code, t)
        full = published_term_name(year_code, t["name"])
        # Adopt the row already published under this name (or under the bare
        # term name for this year), so course sections keep their term id.
        updated = conn.execute(
            "UPDATE academic_terms SET name = ?, academic_year = ?, start_date = ?, end_date = ?, "
            "source = 'calendar', teaching_weeks = ?, sort_order = ?, term_type = 'Term', "
            "status = 'Planned', updated_at = datetime('now') WHERE name = ? OR (academic_year "
            "= ? AND name = ?)",
            (full, year_code, t["start_date"], t["end_date"], weeks, t["sort_order"], full,
             year_code, t["name"])).rowcount
        if not updated:
            conn.execute("INSERT INTO academic_terms (name, term_type, academic_year, start_date, "
                         "end_date, status, source, teaching_weeks, sort_order, created_at, "
                         "updated_at) VALUES (?, 'Term', ?, ?, ?, 'Planned', 'calendar', ?, ?, "
                         "datetime('now'), datetime('now'))",
                         (full, year_code, t["start_date"], t["end_date"], weeks,
                          t["sort_order"]))
    for old in supersede:
        conn.execute("UPDATE academic_terms SET status = 'Superseded', updated_at = "
                     "datetime('now') WHERE id = ?", (old["id"],))


def _teaching_weeks(conn, year_code, term) -> int:
    from education_system.systems.university.application.academic_calendar import (
        dates as calendar_dates,
    )
    return sum(1 for w in calendar_dates.weeks(conn, year_code)
               if w["term"] == term["name"] and w["teaching"])


def _write_holidays(conn, year_code) -> None:
    conn.execute("DELETE FROM holidays WHERE source = 'calendar' AND year_code = ?",
                 (year_code,))
    for d in key_dates(conn, year_code):
        if d["kind"] in NO_TEACHING:
            conn.execute("INSERT INTO holidays (holiday_name, name, start_date, end_date, "
                         "description, recurring, source, year_code) VALUES (?, ?, ?, ?, ?, 0, "
                         "'calendar', ?)", (d["title"], d["title"], d["start_date"],
                                            d["end_date"] or d["start_date"], KINDS[d["kind"]],
                                            year_code))


def _write_legacy(conn, row) -> None:
    """Keep the older year/semester tables (still read by some screens) in step."""
    legacy_id = row["year_code"].replace("/", "-")
    if ca.has_table(conn, "academic_years"):
        conn.execute("INSERT INTO academic_years (id, start_date, end_date, date_added) VALUES "
                     "(?, ?, ?, datetime('now')) ON CONFLICT (id) DO UPDATE SET start_date = "
                     "excluded.start_date, end_date = excluded.end_date",
                     (legacy_id, row["start_date"], row["end_date"]))
    if ca.has_table(conn, "semesters"):
        exams = {d["start_date"][:4]: d for d in key_dates(conn, row["year_code"])
                 if d["kind"] == "exam_period"}
        for t in terms(conn, row["year_code"]):
            exam = next((e for e in exams.values() if t["start_date"] <= e["start_date"] <=
                         t["end_date"]), None)
            if not conn.execute("UPDATE semesters SET start_date = ?, end_date = ?, "
                                "final_exams_start = ?, final_exams_end = ? WHERE "
                                "academic_year_id = ? AND name = ?",
                                (t["start_date"], t["end_date"], exam and exam["start_date"],
                                 exam and exam["end_date"], legacy_id, t["name"])).rowcount:
                conn.execute("INSERT INTO semesters (academic_year_id, name, start_date, "
                             "end_date, final_exams_start, final_exams_end, date_added) VALUES "
                             "(?, ?, ?, ?, ?, ?, datetime('now'))",
                             (legacy_id, t["name"], t["start_date"], t["end_date"],
                              exam and exam["start_date"], exam and exam["end_date"]))


def _announce(conn, year_code, version, changes, note) -> list:
    if version > 1 and not changes:
        return []
    recipients = [r[0] for r in conn.execute(
        "SELECT student_id FROM students WHERE COALESCE(status, 'Active') = 'Active'")]
    recipients += [r[0] for r in conn.execute(
        "SELECT username FROM staff WHERE COALESCE(status, 'active') <> 'inactive'")]
    title = (f"The {year_code} academic calendar is published" if version == 1 else
             f"The {year_code} academic calendar has changed")
    body = "\n".join(changes[:40]) or "See the academic calendar for the year's dates."
    if note:
        body = f"{note}\n\n{body}"
    return ca.notify(conn, recipients, title, body)


def _publish_event(year_code) -> None:
    try:
        from education_system.systems.university.infrastructure.event_bus import (
            EVENT_CALENDAR_CHANGED, publish,
        )
        publish(EVENT_CALENDAR_CHANGED, source="calendar_year", year=year_code)
    except Exception:
        pass


def published_year_for(conn, day=None) -> dict | None:
    ca.ensure(conn)
    day = ca.iso_date(day, "Date") or ca.today()
    return ca.one(conn, "SELECT * FROM calendar_years WHERE status = 'published' AND start_date "
                        "<= ? AND end_date >= ?", (day, day))


def change_log(conn, year_code) -> list[dict]:
    ca.ensure(conn)
    rows = ca.dicts(conn.execute("SELECT version, published_by, published_at, changes_json FROM "
                                 "calendar_published_snapshots WHERE year_code = ? ORDER BY "
                                 "version DESC", (year_code,)))
    for r in rows:
        r["changes"] = json.loads(r.pop("changes_json") or "[]")
    return rows


def default_year_dates(start_year: int) -> tuple[str, str]:
    """1 September to 31 August."""
    return date(start_year, 9, 1).isoformat(), date(start_year + 1, 8, 31).isoformat()
