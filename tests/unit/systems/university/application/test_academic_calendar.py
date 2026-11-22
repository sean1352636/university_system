"""Academic calendar rules: who may change it, years / terms / key dates
with draft → publish (writing academic_terms and holidays, superseding
overlapping terms, change notices), UK bank holidays, teaching weeks, term
time and vacations, publish checks and clashes, imported dates, rollover,
event visibility (private invitations), personal feeds, reminders and
repairing undated events. Temporary databases only."""

import json
import sqlite3
from datetime import date

import pytest

from education_system.systems.university.application.academic_calendar import access as ca
from education_system.systems.university.application.academic_calendar import dates as cd
from education_system.systems.university.application.academic_calendar import events as ce
from education_system.systems.university.application.academic_calendar import year as cy

#: The university's existing calendar tables, before migration f7b9d1e3a5c8.
EXISTING = [
"CREATE TABLE academic_terms ( id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, term_type TEXT NOT NULL DEFAULT 'Semester', academic_year TEXT NOT NULL DEFAULT '', start_date TEXT DEFAULT '', end_date TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'Planned', created_at TEXT NOT NULL DEFAULT (datetime('now')), updated_at TEXT NOT NULL DEFAULT (datetime('now')) )",
'CREATE TABLE holidays ( id INTEGER PRIMARY KEY AUTOINCREMENT, holiday_name TEXT, start_date DATE, end_date DATE, description TEXT, recurring BOOLEAN DEFAULT 0 , "name" TEXT)',
'CREATE TABLE academic_years ( id TEXT PRIMARY KEY, start_date TEXT NOT NULL, end_date TEXT NOT NULL, date_added TEXT NOT NULL, CONSTRAINT valid_dates CHECK (start_date < end_date) )',
'CREATE TABLE semesters ( id INTEGER PRIMARY KEY AUTOINCREMENT, academic_year_id TEXT NOT NULL, name TEXT NOT NULL, start_date TEXT NOT NULL, end_date TEXT NOT NULL, registration_start TEXT, registration_end TEXT, final_exams_start TEXT, final_exams_end TEXT, date_added TEXT NOT NULL, UNIQUE(academic_year_id, name), CONSTRAINT valid_semester_dates CHECK (start_date < end_date) )',
'CREATE TABLE unified_events ( event_id INTEGER PRIMARY KEY AUTOINCREMENT, source_type TEXT NOT NULL, source_event_id INTEGER, title TEXT NOT NULL, description TEXT, event_type TEXT, event_category TEXT, start_datetime TEXT, end_datetime TEXT, location TEXT, building TEXT, room TEXT, room_id INTEGER, organizer_id TEXT, organizer_name TEXT, organizer_type TEXT, max_capacity INTEGER, registration_required INTEGER DEFAULT 0, registration_deadline TEXT, is_public INTEGER DEFAULT 1, is_featured INTEGER DEFAULT 0, status TEXT DEFAULT \'scheduled\', tags TEXT, image_url TEXT, virtual_link TEXT, event_fee REAL DEFAULT 0, payment_required INTEGER DEFAULT 0, waitlist_enabled INTEGER DEFAULT 0, qr_code_path TEXT, club_id INTEGER, created_by TEXT, created_at TEXT DEFAULT (datetime(\'now\')), updated_at TEXT, notes TEXT , "event_name" TEXT, "id" TEXT, "event_date" TEXT, "start_time" TEXT, "end_time" TEXT, "assignment_id" INTEGER, "trip_id" INTEGER, "audience" TEXT, "participants" TEXT, "country_code" TEXT, "region" TEXT, "is_active" BOOLEAN DEFAULT 1, "committee_id" INTEGER, "secretary_id" TEXT, "recurrence" TEXT)',
'CREATE TABLE exams ( id INTEGER PRIMARY KEY AUTOINCREMENT, module_code TEXT NOT NULL, module_name TEXT, date TEXT NOT NULL, start_time TEXT NOT NULL, end_time TEXT NOT NULL, room TEXT, instructor_id INTEGER, instructor_name TEXT, students_enrolled INTEGER DEFAULT 0, enrolled_student_ids TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, parent_exam_id INTEGER, overflow_room TEXT, "exam_name" TEXT, "assessment_id" INTEGER, "status" TEXT DEFAULT \'published\', "published_at" TEXT, "published_by" TEXT )',
"CREATE TABLE registration_periods ( period_id INTEGER PRIMARY KEY AUTOINCREMENT, term_id INTEGER, academic_year TEXT NOT NULL DEFAULT '', name TEXT NOT NULL DEFAULT '', registration_opens TEXT NOT NULL, registration_closes TEXT NOT NULL, add_deadline TEXT, drop_deadline TEXT, withdraw_deadline TEXT, late_add_allowed INTEGER NOT NULL DEFAULT 0, is_active INTEGER NOT NULL DEFAULT 1, notes TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now')), updated_at TEXT NOT NULL DEFAULT (datetime('now')) )",
'CREATE TABLE graduation_ceremonies ( ceremony_id INTEGER PRIMARY KEY AUTOINCREMENT, ceremony_name TEXT NOT NULL, ceremony_date TEXT NOT NULL, ceremony_time TEXT NOT NULL, venue TEXT NOT NULL, capacity INTEGER NOT NULL DEFAULT 200, cohort_filter TEXT DEFAULT \'\', rsvp_deadline TEXT, guest_tickets_per_graduand INTEGER DEFAULT 2, status TEXT DEFAULT \'scheduled\', notes TEXT DEFAULT \'\', created_at TEXT NOT NULL DEFAULT (datetime(\'now\')) , "gown_order_deadline" TEXT)',
"CREATE TABLE assessment_boards ( board_id INTEGER PRIMARY KEY AUTOINCREMENT, board_type TEXT NOT NULL, name TEXT NOT NULL, academic_year TEXT NOT NULL, programme_code TEXT, module_code TEXT, meeting_at TEXT, status TEXT NOT NULL DEFAULT 'draft', version INTEGER NOT NULL DEFAULT 1, chair_id TEXT, chair_approved_at TEXT, ratified_at TEXT, ratified_by TEXT, reopened_at TEXT, reopened_by TEXT, reopen_reason TEXT, created_by TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP )",
    "CREATE TABLE students (student_id TEXT PRIMARY KEY, first_name TEXT, last_name TEXT, "
    "email_address TEXT, status TEXT)",
    "CREATE TABLE staff (id INTEGER PRIMARY KEY, username TEXT UNIQUE, name TEXT, email TEXT, "
    "role TEXT, status TEXT DEFAULT 'active')",
    "CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, last_name TEXT, "
    "email TEXT, role TEXT, student_id TEXT, service_account INTEGER DEFAULT 0)",
    "CREATE TABLE messages (id INTEGER PRIMARY KEY, sender_id INTEGER, recipient_id INTEGER, "
    "subject TEXT, message TEXT, content TEXT, is_read INTEGER, sent_at TEXT)",
]
YEAR = "2026/2027"


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    for ddl in EXISTING:
        c.execute(ddl)
    c.execute("INSERT INTO students VALUES ('S1', 'Sam', 'Student', 's1@uni.test', 'Active')")
    c.execute("INSERT INTO users (username, role, student_id) VALUES ('S1', 'student', 'S1')")
    for username in ("lecturer", "registry"):
        c.execute("INSERT INTO staff (username, name, role) VALUES (?, ?, 'staff')",
                  (username, username.title()))
        c.execute("INSERT INTO users (username, role) VALUES (?, 'staff')", (username,))
    c.execute("INSERT INTO users (username, role) VALUES ('admin', 'admin')")
    ca.ensure(c)
    c.commit()
    yield c
    c.close()


def who(c, username, role="staff"):
    return ca.user(c, username, role, "S1" if role == "student" else None)


def refused(fn, *args, **kwargs) -> str:
    with pytest.raises((ValueError, PermissionError)) as exc:
        fn(*args, **kwargs)
    return str(exc.value)


def _year(c):
    admin = who(c, "admin", "admin")
    cy.create_year(c, admin, YEAR, "2026-09-01", "2027-08-31")
    cy.save_term(c, admin, YEAR, "Autumn", "2026-09-21", "2026-12-11")
    cy.save_term(c, admin, YEAR, "Spring", "2027-01-11", "2027-03-26")
    cy.save_term(c, admin, YEAR, "Summer", "2027-04-19", "2027-06-11")
    cy.save_key_date(c, admin, YEAR, "reading_week", "Reading week", "2026-11-02", "2026-11-06")
    cy.save_key_date(c, admin, YEAR, "closure", "Christmas closure", "2026-12-24", "2027-01-01")
    return admin


# ── access ──────────────────────────────────────────────────────────────


def test_only_calendar_admins_change_institution_dates(conn):
    lecturer = who(conn, "lecturer")
    assert refused(cy.create_year, conn, lecturer, YEAR, "2026-09-01", "2027-08-31")
    ca.grant(conn, who(conn, "admin", "admin"), "registry")
    assert who(conn, "registry").is_admin
    assert refused(ca.grant, conn, who(conn, "registry"), "lecturer")
    assert "2026/2027" in refused(cy.create_year, conn, who(conn, "admin", "admin"), "2026/2028",
                                  "2026-09-01", "2027-08-31")


# ── bank holidays and weeks ─────────────────────────────────────────────


def test_bank_holidays():
    eng = dict((name, d) for name, d in cd.bank_holidays(2027))
    assert eng["Good Friday"] == date(2027, 3, 26) and eng["Easter Monday"] == date(2027, 3, 29)
    assert eng["Early May bank holiday"] == date(2027, 5, 3)
    assert eng["Summer bank holiday"] == date(2027, 8, 30)
    days = dict((n, d) for n, d in cd.bank_holidays(2026))
    assert days["Boxing Day (substitute day)"] == date(2026, 12, 28)      # 26th is a Saturday
    scot = dict(cd.bank_holidays(2027, "scotland"))
    assert "Easter Monday" not in scot and scot["Summer bank holiday"] == date(2027, 8, 2)


def test_year_gets_bank_holidays_and_teaching_weeks(conn):
    _year(conn)
    kinds = [d["kind"] for d in cy.key_dates(conn, YEAR)]
    assert kinds.count("bank_holiday") == 8
    autumn = [w for w in cd.weeks(conn, YEAR) if w["term"] == "Autumn"]
    assert len(autumn) == 12 and sum(w["teaching"] for w in autumn) == 11
    assert [w["why_not"] for w in autumn if not w["teaching"]] == ["reading week"]
    assert [v["start"] for v in cd.vacation_periods(conn, YEAR)][:2] == ["2026-09-01",
                                                                        "2026-12-12"]


def test_terms_must_fit_and_not_overlap(conn):
    admin = _year(conn)
    assert "overlaps" in refused(cy.save_term, conn, admin, YEAR, "X", "2026-12-01", "2027-01-20")
    assert "inside" in refused(cy.save_term, conn, admin, YEAR, "X", "2027-08-01", "2027-09-30")
    assert "inside" in refused(cy.save_key_date, conn, admin, YEAR, "other", "x", "2028-01-01")


# ── publishing ──────────────────────────────────────────────────────────


def test_publish_writes_terms_holidays_and_supersedes(conn):
    conn.execute("INSERT INTO academic_terms (name, term_type, academic_year, start_date, "
                 "end_date, status) VALUES ('Fall 2026', 'Semester', '2026-2027', '2026-09-01', "
                 "'2026-12-20', 'Planned')")
    admin = _year(conn)
    preview = cy.preview_publish(conn, admin, YEAR)
    assert not preview["errors"]
    assert [t["name"] for t in preview["supersedes"]] == ["Fall 2026"]
    result = cy.publish(conn, admin, YEAR)
    rows = conn.execute("SELECT name, status, teaching_weeks FROM academic_terms ORDER BY "
                        "start_date").fetchall()
    assert ("Fall 2026", "Superseded", None) in rows
    assert ("Autumn 2026/2027", "Planned", 11) in rows     # names are unique across years
    assert conn.execute("SELECT COUNT(*) FROM holidays WHERE source = 'calendar'").fetchone()[0] \
        == 10
    assert result["emails"]                          # staff and students are told
    from education_system.systems.university.application.teaching import (
        occurrences as timetable_occurrences,
    )
    assert "Fall 2026" not in [t[0] for t in timetable_occurrences.terms(conn)]


def test_republish_keeps_term_ids_and_reports_changes(conn):
    admin = _year(conn)
    cy.publish(conn, admin, YEAR)
    term_id = conn.execute("SELECT id FROM academic_terms WHERE name = 'Autumn 2026/2027'"
                           ).fetchone()[0]
    autumn = next(t for t in cy.terms(conn, YEAR) if t["name"] == "Autumn")
    assert "reopen" in refused(cy.save_term, conn, admin, YEAR, "Autumn", "2026-09-28",
                               "2026-12-11", autumn["term_id"])
    cy.reopen(conn, admin, YEAR)
    cy.save_term(conn, admin, YEAR, "Autumn", "2026-09-28", "2026-12-11", autumn["term_id"])
    result = cy.publish(conn, admin, YEAR)
    assert result["changes"] == ["Moved: Autumn from 2026-09-21 to 2026-09-28 – 2026-12-11"]
    assert conn.execute("SELECT id, start_date FROM academic_terms WHERE name = "
                        "'Autumn 2026/2027'").fetchone() == (term_id, "2026-09-28")
    assert [c["version"] for c in cy.change_log(conn, YEAR)] == [2, 1]


def test_checks_block_publishing_and_find_clashes(conn):
    admin = who(conn, "admin", "admin")
    cy.create_year(conn, admin, YEAR, "2026-09-01", "2027-08-31")
    assert "no terms" in refused(cy.publish, conn, admin, YEAR)
    cy.save_term(conn, admin, YEAR, "Short", "2026-11-02", "2026-11-06")
    cy.save_key_date(conn, admin, YEAR, "reading_week", "Reading week", "2026-11-02",
                     "2026-11-06")
    assert "no teaching weeks" in refused(cy.publish, conn, admin, YEAR)
    conn.execute("INSERT INTO exams (module_code, module_name, date, start_time, end_time, room, "
                 "status) VALUES ('X1', 'X', '2026-12-25', '09:00', '11:00', 'Hall', 'published')")
    clashes = cd.check_year(conn, YEAR)["clashes"]
    assert any("Christmas Day" in c for c in clashes)
    assert any("outside term" in c for c in clashes)


def test_import_dates_from_other_systems(conn):
    admin = _year(conn)
    conn.executemany("INSERT INTO exams (module_code, module_name, date, start_time, end_time, "
                     "room, status) VALUES (?, 'X', ?, '09:00', '11:00', 'Hall', ?)",
                     [("X1", "2027-01-04", "published"), ("X2", "2027-01-08", "published"),
                      ("X3", "2027-01-09", "draft")])
    conn.execute("INSERT INTO graduation_ceremonies (ceremony_name, ceremony_date, ceremony_time, "
                 "venue) VALUES ('Summer graduation', '2027-07-14', '10:00', 'Hall')")
    counts = cd.import_dates(conn, admin, YEAR)
    assert counts == {"exams": 2, "graduation": 1}
    exam = next(d for d in cy.key_dates(conn, YEAR) if d["kind"] == "exam_period")
    assert (exam["start_date"], exam["end_date"]) == ("2027-01-04", "2027-01-08")
    assert cd.import_dates(conn, admin, YEAR) == counts            # replaced, not doubled


def test_two_years_can_both_be_published(conn):
    admin = _year(conn)
    cy.publish(conn, admin, YEAR)
    nxt = cd.rollover(conn, admin, YEAR)
    cy.publish(conn, admin, nxt)
    names = {r[0] for r in conn.execute("SELECT name FROM academic_terms")}
    assert {"Autumn 2026/2027", "Autumn 2027/2028"} <= names


def test_term_time(conn):
    admin = _year(conn)
    assert cd.is_term_time(conn, "2026-10-05") is None            # nothing published yet
    cy.publish(conn, admin, YEAR)
    assert cd.is_term_time(conn, "2026-10-05") is True
    assert cd.is_term_time(conn, "2026-11-03") is False           # reading week
    assert cd.is_term_time(conn, "2026-12-28") is False           # vacation / closure
    assert cd.term_for(conn, "2027-02-01")["name"] == "Spring"


def test_rollover(conn):
    admin = _year(conn)
    nxt = cd.rollover(conn, admin, YEAR)
    assert nxt == "2027/2028" and cy.year(conn, nxt)["start_date"] == "2027-09-01"
    autumn = next(t for t in cy.terms(conn, nxt) if t["name"] == "Autumn")
    assert autumn["start_date"] == "2027-09-20"                    # same weekday, a year on
    assert date.fromisoformat(autumn["start_date"]).weekday() == 0
    kinds = [d["kind"] for d in cy.key_dates(conn, nxt)]
    assert kinds.count("reading_week") == 1 and kinds.count("bank_holiday") == 8
    assert cy.year(conn, nxt)["status"] == "draft"


# ── events ──────────────────────────────────────────────────────────────


def _event(c, title, audience=None, participants=None, start="2026-10-10T10:00"):
    c.execute("INSERT INTO unified_events (source_event_id, title, event_date, start_datetime, "
              "audience, participants, source_type, is_active) VALUES (?, ?, ?, ?, ?, ?, "
              "'academic_calendar', 1)",
              (title, title, start[:10], start, audience, participants))


def test_private_events_only_reach_the_people_they_name(conn):
    _event(conn, "Training for lecturer", "Private",
           json.dumps([{"user_id": 9, "username": "lecturer"}]))
    _event(conn, "Staff meeting", "staff")
    _event(conn, "Open day", "all")
    seen = lambda u: {e["title"] for e in ce.visible_events(conn, u, "2026-10-01",  # noqa: E731
                                                              "2026-10-31")}
    assert seen(who(conn, "lecturer")) == {"Training for lecturer", "Staff meeting", "Open day"}
    assert seen(who(conn, "registry")) == {"Staff meeting", "Open day"}
    assert seen(who(conn, "S1", "student")) == {"Open day"}
    assert "Training for lecturer" not in seen(who(conn, "admin", "admin"))


def test_feed_links(conn):
    admin = _year(conn)
    cy.save_key_date(conn, admin, YEAR, "census_hesa", "HESA census", "2026-12-01",
                     audience="staff")
    cy.publish(conn, admin, YEAR)
    student = who(conn, "S1", "student")
    feed = ce.create_feed(conn, student)
    stored = conn.execute("SELECT token_hash FROM calendar_feed_tokens").fetchone()[0]
    assert stored != feed["token"]
    text = ce.feed_ics(conn, feed["token"])
    assert "Reading week" in text and "HESA census" not in text
    ce.revoke_feed(conn, student)
    assert ce.feed_ics(conn, feed["token"]) is None


def test_reminders(conn):
    _event(conn, "Open day", "all", start="2030-01-01T10:00")
    lecturer = who(conn, "lecturer")
    ce.add_reminder(conn, lecturer, "Open day", 30)
    assert ce.send_due(conn, "2030-01-01T09:00")["sent"] == 0
    assert ce.send_due(conn, "2030-01-01T09:31")["sent"] == 1
    assert ce.send_due(conn, "2030-01-01T09:40")["sent"] == 0
    _event(conn, "Old", "all", start="2000-01-01T10:00")
    assert "passed" in refused(ce.add_reminder, conn, lecturer, "Old", 30)


def test_repair_undated_events(conn):
    conn.execute("INSERT INTO unified_events (source_event_id, title, event_date, source_type) "
                 "VALUES ('r1', 'test event (Recurring)', '2026-10-01', 'academic_calendar')")
    conn.execute("INSERT INTO unified_events (source_event_id, title, source_type) VALUES ('r2', "
                 "'no date', 'academic_calendar')")
    assert len(ce.undated_events(conn)) == 2
    assert refused(ce.repair_undated, conn, who(conn, "lecturer"))
    assert ce.repair_undated(conn, who(conn, "admin", "admin")) == {"fixed": 1, "removed": 0}
    assert len(ce.undated_events(conn)) == 1
