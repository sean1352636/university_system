"""Graduation rules: who may run it, eligibility (ratified award, holds,
misconduct, money only as a warning, the programme's credit rule), the
certificate name, conferral in one transaction (certificate, credential,
transcript snapshot, print job, alumni record, status), ceremonies (cohorts,
invitations, RSVP rules, named guests, extra tickets, check-in, completion,
no-shows, transfers), board reopening (suspend, reinstate, reissue),
revocation, replacement certificates, verification, transcript shares with
hashed tokens, the HEAR and gown refunds. Temporary databases only."""

import sqlite3
from datetime import date, timedelta

import pytest

from education_system.systems.university.application.graduation import access as ga
from education_system.systems.university.application.graduation import ceremonies as gcer
from education_system.systems.university.application.graduation import conferral as gc
from education_system.systems.university.application.graduation import eligibility as ge
from education_system.systems.university.application.graduation import transcripts as gt

#: The university's existing graduation tables, before migration d5f7a9b1c3e6.
EXISTING = [
"CREATE TABLE graduation_ceremonies ( ceremony_id INTEGER PRIMARY KEY AUTOINCREMENT, ceremony_name TEXT NOT NULL, ceremony_date TEXT NOT NULL, ceremony_time TEXT NOT NULL, venue TEXT NOT NULL, capacity INTEGER NOT NULL DEFAULT 200, cohort_filter TEXT DEFAULT '', rsvp_deadline TEXT, guest_tickets_per_graduand INTEGER DEFAULT 2, status TEXT DEFAULT 'scheduled', notes TEXT DEFAULT '', created_at TEXT NOT NULL DEFAULT (datetime('now')) )",
"CREATE TABLE ceremony_rsvps ( rsvp_id INTEGER PRIMARY KEY AUTOINCREMENT, ceremony_id INTEGER NOT NULL, student_id TEXT NOT NULL, rsvp_status TEXT NOT NULL DEFAULT 'pending', num_guests INTEGER NOT NULL DEFAULT 0, accessibility_notes TEXT DEFAULT '', name_pronunciation TEXT DEFAULT '', recorded_at TEXT NOT NULL DEFAULT (datetime('now')), UNIQUE(ceremony_id, student_id) )",
"CREATE TABLE ceremony_gown_orders ( order_id INTEGER PRIMARY KEY AUTOINCREMENT, ceremony_id INTEGER NOT NULL, student_id TEXT NOT NULL, gown_size TEXT DEFAULT '', hood_subject TEXT DEFAULT '', hat_size TEXT DEFAULT '', supplier TEXT DEFAULT '', collection_slot TEXT DEFAULT '', status TEXT DEFAULT 'ordered', created_at TEXT NOT NULL DEFAULT (datetime('now')), cost REAL NOT NULL DEFAULT 0, payment_method TEXT DEFAULT '', payment_status TEXT DEFAULT 'unpaid', payment_reference TEXT DEFAULT '', finance_payment_id INTEGER, paid_at TEXT, UNIQUE(ceremony_id, student_id) )",
"CREATE TABLE certificates ( id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL, certificate_number TEXT UNIQUE NOT NULL, certificate_type TEXT NOT NULL, course_name TEXT NOT NULL, award_date TEXT NOT NULL, grade TEXT, additional_info TEXT, status TEXT NOT NULL DEFAULT 'active', issued_by TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP )",
'CREATE TABLE blockchain_credentials ( credential_id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL, credential_type TEXT NOT NULL, credential_name TEXT NOT NULL, issue_date DATE NOT NULL, blockchain_hash TEXT UNIQUE NOT NULL, blockchain_address TEXT, ipfs_hash TEXT, metadata TEXT, is_revoked BOOLEAN DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP )',
"CREATE TABLE transcript_freezes ( freeze_id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL, program_id INTEGER, academic_year TEXT, snapshot_html TEXT NOT NULL, snapshot_hash TEXT NOT NULL, frozen_at TEXT NOT NULL DEFAULT (datetime('now')), frozen_by TEXT, gpa TEXT, classification TEXT, notes TEXT DEFAULT '', UNIQUE(student_id, academic_year) )",
"CREATE TABLE transcript_access_tokens ( token_id INTEGER PRIMARY KEY AUTOINCREMENT, freeze_id INTEGER NOT NULL, token TEXT UNIQUE NOT NULL, requested_by TEXT, employer_name TEXT, employer_email TEXT, purpose TEXT DEFAULT '', issued_at TEXT NOT NULL DEFAULT (datetime('now')), expires_at TEXT, accessed_at TEXT, revoked INTEGER NOT NULL DEFAULT 0 )",
"CREATE TABLE ratified_student_awards ( award_id INTEGER PRIMARY KEY AUTOINCREMENT, board_id INTEGER NOT NULL, student_id TEXT NOT NULL, programme_code TEXT NOT NULL, award_name TEXT NOT NULL, classification TEXT, academic_year TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'ratified', ratified_at TEXT NOT NULL, ratified_by TEXT NOT NULL, release_authorised INTEGER NOT NULL DEFAULT 1, superseded_by_award_id INTEGER, UNIQUE(student_id, programme_code, academic_year) )",
'CREATE TABLE course_exit_awards ( id INTEGER PRIMARY KEY AUTOINCREMENT, course_code TEXT NOT NULL, award_name TEXT NOT NULL, total_credits INTEGER NOT NULL CHECK (total_credits > 0), credits_at_level INTEGER NOT NULL DEFAULT 0 CHECK (credits_at_level >= 0), at_level INTEGER CHECK (at_level IS NULL OR at_level BETWEEN 3 AND 8), is_final INTEGER NOT NULL DEFAULT 0, UNIQUE (course_code, award_name) )',
'CREATE TABLE alumni ( alumni_id TEXT PRIMARY KEY, student_id TEXT, email_address TEXT, title TEXT, first_name TEXT, middle_name TEXT, last_name TEXT, gender TEXT, dob TEXT, graduation_year INTEGER, degree_earned TEXT, current_employer TEXT, job_title TEXT, industry TEXT, address TEXT, city TEXT, country TEXT, phone TEXT, linkedin_url TEXT, date_registered TEXT, is_donor BOOLEAN, is_mentor BOOLEAN, is_board_member BOOLEAN, profile_photo TEXT, bio TEXT, skills TEXT, achievements TEXT, privacy_level INTEGER DEFAULT 1, engagement_score INTEGER DEFAULT 0, last_activity TEXT, social_media_links TEXT, is_ambassador BOOLEAN DEFAULT 0 )',
"CREATE TABLE unified_refunds ( refund_id INTEGER PRIMARY KEY AUTOINCREMENT, source_type TEXT NOT NULL, source_refund_id INTEGER, reference_type TEXT, reference_id TEXT, student_id TEXT, customer_name TEXT, customer_email TEXT, amount DECIMAL(10,2) NOT NULL, original_amount DECIMAL(10,2), currency TEXT DEFAULT 'GBP', refund_type TEXT, refund_method TEXT, refund_reference TEXT, reason TEXT, status TEXT DEFAULT 'processed', department TEXT, processed_by TEXT, requested_by TEXT, approved_by TEXT, refund_date TEXT NOT NULL, request_date TEXT, approval_date TEXT, notes TEXT, created_at TEXT DEFAULT (datetime('now')) , vat_rate TEXT, vat_amount REAL)",
"CREATE TABLE graduation_print_queue ( queue_id INTEGER PRIMARY KEY AUTOINCREMENT, ceremony_id INTEGER NOT NULL, student_id TEXT NOT NULL, certificate_id INTEGER, certificate_number TEXT, status TEXT NOT NULL DEFAULT 'queued', printed_at TEXT, dispatched_at TEXT, notes TEXT DEFAULT '', created_at TEXT NOT NULL DEFAULT (datetime('now')), UNIQUE(ceremony_id, student_id) )",
'CREATE TABLE module_grades ( id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT, module_code TEXT, final_score REAL, final_grade TEXT, completion_date TEXT, "date_recorded" TEXT, "status" TEXT DEFAULT \'provisional\', "locked" INTEGER DEFAULT 0, "outcome" TEXT, "credits_awarded" REAL, "board_id" INTEGER, "confirmed_at" TEXT, "attempt" INTEGER DEFAULT 1, "is_complete" INTEGER DEFAULT 0 )',
'CREATE TABLE student_modules ( id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT, module_code TEXT, enrollment_date TEXT DEFAULT (date(\'now\')), status TEXT DEFAULT \'Enrolled\', module_type TEXT DEFAULT \'Standard\', module_name TEXT, grade TEXT, completion_date TEXT, "credits_earned" INTEGER DEFAULT 0, "enrollment_id" INTEGER, "module_id" TEXT, "semester" TEXT, "year" TEXT, "created_at" TIMESTAMP DEFAULT NULL, UNIQUE(student_id, module_code) )',
'CREATE TABLE modules ( module_id TEXT PRIMARY KEY, module_name TEXT NOT NULL, description TEXT, credits INTEGER DEFAULT 0, semester TEXT, year TEXT, instructor TEXT, department TEXT, prerequisites TEXT, is_active BOOLEAN DEFAULT 1, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP , module_code TEXT, module_type TEXT DEFAULT \'Standard\', "course" TEXT, "academic_year" TEXT, "instructor_id" INTEGER, "capacity" INTEGER, "difficulty_level" INTEGER, "level" INTEGER)',
    "CREATE TABLE students (student_id TEXT PRIMARY KEY, first_name TEXT, last_name TEXT, "
    "email_address TEXT, course TEXT, status TEXT, is_active INTEGER DEFAULT 1, address TEXT)",
    "CREATE TABLE staff (id INTEGER PRIMARY KEY, username TEXT UNIQUE, name TEXT, email TEXT, "
    "role TEXT, status TEXT DEFAULT 'active')",
    "CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, last_name TEXT, "
    "email TEXT, role TEXT, student_id TEXT, service_account INTEGER DEFAULT 0)",
    "CREATE TABLE messages (id INTEGER PRIMARY KEY, sender_id INTEGER, recipient_id INTEGER, "
    "subject TEXT, message TEXT, content TEXT, is_read INTEGER, sent_at TEXT)",
    "CREATE TABLE academic_misconduct_cases (id INTEGER PRIMARY KEY, case_id TEXT, student_id "
    "TEXT, status TEXT)",
    "CREATE TABLE student_finance_accounts (student_id TEXT, balance REAL)",
]
STUDENTS = ("S1", "S2", "S3", "S4")
SOON = (date.today() + timedelta(days=20)).isoformat()
DEADLINE = (date.today() + timedelta(days=10)).isoformat()


def render(student_id, year):
    return f"<html>transcript {student_id} {year}</html>"


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    for ddl in EXISTING:
        c.execute(ddl)
    for n, sid in enumerate(STUDENTS, 1):
        c.execute("INSERT INTO students VALUES (?, ?, 'Graduand', ?, 'CS', 'Active', 1, '1 Road')",
                  (sid, f"Grad{n}", f"{sid.lower()}@uni.test"))
        c.execute("INSERT INTO users (username, role, student_id) VALUES (?, 'student', ?)",
                  (sid, sid))
        c.execute("INSERT INTO ratified_student_awards (board_id, student_id, programme_code, "
                  "award_name, classification, academic_year, ratified_at, ratified_by) VALUES "
                  "(7, ?, 'CS', 'BSc (Hons) Computer Science', 'Upper Second Class', '2025/26', "
                  "'2026-06-01', 'senate')", (sid,))
    c.execute("INSERT INTO students VALUES ('S9', 'No', 'Award', NULL, 'CS', 'Active', 1, NULL)")
    for username, role in (("registrar1", "registrar"), ("door", "staff"),
                           ("lecturer", "staff")):
        c.execute("INSERT INTO staff (username, name, role) VALUES (?, ?, 'staff')",
                  (username, username.title()))
        c.execute("INSERT INTO users (username, role) VALUES (?, ?)", (username, role))
    c.execute("INSERT INTO users (username, role) VALUES ('admin', 'admin')")
    c.execute("INSERT INTO course_exit_awards (course_code, award_name, total_credits, is_final) "
              "VALUES ('CS', 'BSc (Hons)', 360, 1)")
    ga.ensure(c)
    ga.grant_role(c, who(c, "admin", "admin"), "door", "ceremony_staff")
    for sid in STUDENTS:
        ge.confirm_name(c, who(c, sid, "student"), sid, f"Grad{STUDENTS.index(sid) + 1} Graduand")
    c.commit()
    yield c
    c.close()


def who(c, username, role="staff"):
    return ga.officer(c, username, role, username if role == "student" else None)


def refused(fn, *args, **kwargs) -> str:
    with pytest.raises((ValueError, PermissionError)) as exc:
        fn(*args, **kwargs)
    return str(exc.value)


def _ceremony(c, capacity=20, guests=2):
    cid = c.execute("INSERT INTO graduation_ceremonies (ceremony_name, ceremony_date, "
                    "ceremony_time, venue, capacity, rsvp_deadline, guest_tickets_per_graduand) "
                    "VALUES ('Summer', ?, '10:00', 'Hall', ?, ?, ?)",
                    (SOON, capacity, DEADLINE, guests)).lastrowid
    return cid


def _held_today(c, cid):
    c.execute("UPDATE graduation_ceremonies SET ceremony_date = ? WHERE ceremony_id = ?",
              (date.today().isoformat(), cid))


# ── access ──────────────────────────────────────────────────────────────


def test_access(conn):
    assert who(conn, "admin", "admin").is_office
    assert who(conn, "registrar1", "registrar").is_office
    door = who(conn, "door")
    assert door.can_check_in and not door.is_office
    lecturer = who(conn, "lecturer")
    assert not lecturer.has_access
    assert refused(ga.grant_role, conn, lecturer, "lecturer", "graduation_office")
    assert refused(gc.confer, conn, door, "S1", render=render)


# ── eligibility ─────────────────────────────────────────────────────────


def test_eligibility_needs_a_released_award(conn):
    report = ge.check(conn, "S9")
    assert not report["eligible"] and "ratified" in report["blockers"][0]
    conn.execute("UPDATE students SET status = 'Graduated' WHERE student_id = 'S9'")
    assert not ge.check(conn, "S9")["eligible"]          # a status alone is not an award
    conn.execute("UPDATE ratified_student_awards SET release_authorised = 0, status = "
                 "'under_correction' WHERE student_id = 'S1'")
    assert "correction" in ge.check(conn, "S1")["blockers"][0]
    report = ge.check(conn, "S2")
    assert report["eligible"] and report["credits_required"] == 360


def test_holds_and_misconduct_block_but_money_only_warns(conn):
    office = who(conn, "admin", "admin")
    hold = ge.place_hold(conn, office, "S1", "appeal", "Appeal pending")
    assert not ge.check(conn, "S1")["eligible"]
    ge.release_hold(conn, office, hold, "Appeal dismissed")
    assert ge.check(conn, "S1")["eligible"]
    conn.execute("INSERT INTO academic_misconduct_cases (case_id, student_id, status) VALUES "
                 "('AM1', 'S1', 'Under Review')")
    assert "misconduct" in ge.check(conn, "S1")["blockers"][0]
    conn.execute("INSERT INTO student_finance_accounts VALUES ('S2', 120.0)")
    report = ge.check(conn, "S2")
    assert report["eligible"] and "not withheld" in report["warnings"][0]
    assert refused(ge.place_hold, conn, who(conn, "lecturer"), "S2", "registry", "x")


def test_certificate_name_change_needs_the_office(conn):
    student = who(conn, "S1", "student")
    ge.confirm_name(conn, student, "S1", "Gradly Renamed")
    assert not ge.check(conn, "S1")["name_confirmed"]
    assert "name" in refused(gc.confer, conn, who(conn, "admin", "admin"), "S1", render=render)
    assert refused(ge.confirm_name, conn, student, "S2", "Someone Else")
    ge.set_name(conn, who(conn, "admin", "admin"), "S1", "Gradly Renamed", "Deed poll seen")
    assert ge.check(conn, "S1")["name_confirmed"]


# ── conferral ───────────────────────────────────────────────────────────


def test_confer_in_absentia_creates_everything_once(conn):
    office = who(conn, "admin", "admin")
    result = gc.confer(conn, office, "S1", mode="in_absentia", conferral_date="2026-07-01",
                       render=render)
    row = gc.conferral(conn, result["conferral_id"])
    assert row["award_name"] == "BSc (Hons) Computer Science"
    assert row["classification"] == "Upper Second Class"
    cert = conn.execute("SELECT award_date, grade, status FROM certificates WHERE id = ?",
                        (row["certificate_id"],)).fetchone()
    assert cert == ("2026-07-01", "Upper Second Class", "active")
    assert conn.execute("SELECT status FROM students WHERE student_id = 'S1'").fetchone()[0] == \
        "Completed"
    assert conn.execute("SELECT degree_earned FROM alumni WHERE alumni_id = 'S1'").fetchone()
    assert conn.execute("SELECT delivery, address FROM certificate_print_jobs WHERE "
                        "conferral_id = ?", (row["conferral_id"],)).fetchone() == ("post",
                                                                                   "1 Road")
    assert "already" in refused(gc.confer, conn, office, "S1", render=render)
    assert result["verification_code"] not in str(row["certificate_number"])


def test_failed_conferral_writes_nothing(conn):
    office = who(conn, "admin", "admin")
    before = conn.execute("SELECT COUNT(*) FROM certificates").fetchone()[0]
    refused(gc.confer, conn, office, "S9", render=render)
    assert conn.execute("SELECT COUNT(*) FROM certificates").fetchone()[0] == before


def test_verification(conn):
    office = who(conn, "admin", "admin")
    result = gc.confer(conn, office, "S1", render=render)
    shown = gc.verify(conn, result["verification_code"])
    assert shown["valid"] and shown["name"] == "Grad1 Graduand" and "student_id" not in shown
    assert gc.verify(conn, result["certificate_number"])["valid"]
    assert not gc.verify(conn, "CERT-NOPE")["valid"]


# ── board reopening, revocation, replacement ────────────────────────────


def test_board_reopen_suspends_then_reinstates(conn):
    office = who(conn, "admin", "admin")
    result = gc.confer(conn, office, "S1", render=render)
    conn.execute("UPDATE ratified_student_awards SET release_authorised = 0, status = "
                 "'under_correction' WHERE board_id = 7")
    assert gc.suspend_for_board(conn, 7) == [result["conferral_id"]]
    assert gc.verify(conn, result["verification_code"])["status"] == "suspended"
    assert "released" in refused(gc.review_suspended, conn, office, result["conferral_id"],
                                 render=render)
    conn.execute("UPDATE ratified_student_awards SET release_authorised = 1, status = 'ratified'")
    assert gc.review_suspended(conn, office, result["conferral_id"], render=render)["reinstated"]
    assert gc.verify(conn, result["certificate_number"])["valid"]


def test_changed_award_is_reissued(conn):
    office = who(conn, "admin", "admin")
    first = gc.confer(conn, office, "S1", render=render)
    conn.execute("UPDATE ratified_student_awards SET release_authorised = 0 WHERE board_id = 7")
    gc.suspend_for_board(conn, 7)
    conn.execute("UPDATE ratified_student_awards SET release_authorised = 1, classification = "
                 "'First Class' WHERE student_id = 'S1'")
    second = gc.review_suspended(conn, office, first["conferral_id"], render=render)
    assert not second["reinstated"]
    assert gc.conferral(conn, second["conferral_id"])["classification"] == "First Class"
    assert gc.verify(conn, first["certificate_number"])["status"] == "superseded"
    years = sorted(r[0] for r in conn.execute("SELECT academic_year FROM transcript_freezes"))
    assert years[0] == "2025/26" and "superseded" in years[1]


def test_revoke_and_replace(conn):
    office = who(conn, "admin", "admin")
    result = gc.confer(conn, office, "S1", render=render)
    student = who(conn, "S1", "student")
    assert refused(gc.replace_certificate, conn, student, result["conferral_id"], "lost",
                   address="1 Road", waive_fee=True)
    replaced = gc.replace_certificate(conn, student, result["conferral_id"], "lost",
                                      address="1 Road")
    assert replaced["fee"] == gc.REPLACEMENT_FEE
    assert not gc.verify(conn, result["certificate_number"])["valid"]
    assert gc.verify(conn, replaced["certificate_number"])["valid"]
    assert refused(gc.revoke, conn, student, result["conferral_id"], "x")
    gc.revoke(conn, office, result["conferral_id"], "Misconduct finding")
    assert gc.verify(conn, replaced["certificate_number"])["status"] == "revoked"
    assert {r[0] for r in conn.execute("SELECT status FROM certificate_print_jobs")} == {
        "cancelled"}


def test_print_job_moves(conn):
    office = who(conn, "admin", "admin")
    gc.confer(conn, office, "S1", render=render)
    job = gc.print_jobs(conn)[0]["job_id"]
    assert "cannot become" in refused(gc.set_job_status, conn, office, job, "dispatched")
    for status in ("printing", "printed", "dispatched"):
        gc.set_job_status(conn, office, job, status)
    assert gc.print_jobs(conn)[0]["dispatched_at"]


# ── ceremonies ──────────────────────────────────────────────────────────


def test_cohorts_and_invitations(conn):
    office = who(conn, "admin", "admin")
    cid = _ceremony(conn)
    gcer.set_cohorts(conn, office, cid, [("programme", "MATHS")])
    assert gcer.graduands(conn, office, cid) == []
    gcer.set_cohorts(conn, office, cid, [("programme", "CS")])
    ge.place_hold(conn, office, "S4", "registry", "Name dispute")
    result = gcer.invite(conn, office, cid)
    assert sorted(result["invited"]) == ["S1", "S2", "S3"]
    assert conn.execute("SELECT COUNT(*) FROM ceremony_rsvps WHERE ceremony_id = ? AND "
                        "rsvp_status = 'pending'", (cid,)).fetchone()[0] == 3


def test_rsvp_rules(conn):
    office = who(conn, "admin", "admin")
    cid = _ceremony(conn, capacity=4, guests=2)
    s1 = who(conn, "S1", "student")
    assert refused(gcer.record_rsvp, conn, s1, cid, "S2", "going")
    assert "allowance" in refused(gcer.record_rsvp, conn, s1, cid, "S1", "going",
                                  guests=["A", "B", "C"])
    assert "access need" in refused(gcer.record_rsvp, conn, s1, cid, "S1", "going",
                                    access_needs="jetpack")
    out = gcer.record_rsvp(conn, s1, cid, "S1", "going", guests=["Mum", ("Dad", "wheelchair")],
                           access_needs="step_free", extra_tickets=1)
    assert len({ref for _n, ref in out["tickets"]}) == 2
    notes = conn.execute("SELECT accessibility_notes FROM ceremony_rsvps WHERE student_id = "
                         "'S1'").fetchone()[0]
    assert "step_free" in notes
    assert "full" in refused(gcer.record_rsvp, conn, office, cid, "S2", "going", guests=["X"],
                             override=True)
    conn.execute("UPDATE graduation_ceremonies SET rsvp_deadline = '2000-01-01'")
    assert "closed" in refused(gcer.record_rsvp, conn, who(conn, "S3", "student"), cid, "S3",
                               "going")
    gcer.record_rsvp(conn, office, cid, "S3", "not_going", override=True)
    ge.place_hold(conn, office, "S2", "appeal", "x")
    assert "Not eligible" in refused(gcer.record_rsvp, conn, office, cid, "S2", "going",
                                     override=True)


def test_extra_tickets_first_come_first_served(conn):
    office = who(conn, "admin", "admin")
    cid = _ceremony(conn, capacity=6, guests=1)
    gcer.record_rsvp(conn, who(conn, "S1", "student"), cid, "S1", "going", guests=["A"],
                     extra_tickets=2)
    gcer.record_rsvp(conn, who(conn, "S2", "student"), cid, "S2", "going", guests=["B"],
                     extra_tickets=2)
    result = gcer.allocate_extra_tickets(conn, office, cid)
    assert result["granted"] == 2
    statuses = [r["status"] for r in gcer.ticket_requests(conn, cid)]
    assert statuses == ["granted", "declined"]
    gcer.record_rsvp(conn, who(conn, "S1", "student"), cid, "S1", "going",
                     guests=["A", "C", "D"])


def test_check_in_complete_confers_attendees_only(conn):
    office = who(conn, "admin", "admin")
    cid = _ceremony(conn)
    for sid in ("S1", "S2"):
        gcer.record_rsvp(conn, who(conn, sid, "student"), cid, sid, "going")
    door = who(conn, "door")
    assert refused(gcer.check_in, conn, who(conn, "lecturer"), cid, "S1")
    gcer.check_in(conn, door, cid, "S1")
    assert "already" in refused(gcer.check_in, conn, door, cid, "S1")
    assert "not happened" in refused(gcer.complete, conn, office, cid, render=render)
    _held_today(conn, cid)
    result = gcer.complete(conn, office, cid, render=render)
    assert [r["student_id"] for r in result["conferred"]] == ["S1"]
    assert result["no_shows"] == ["S2"]
    assert gc.conferral(conn, result["conferred"][0]["conferral_id"])["mode"] == "ceremony"
    assert ge.check(conn, "S2")["conferral"] is None
    assert refused(gcer.check_in, conn, door, cid, "S2")          # completed


def test_no_show_transfers_to_a_later_ceremony(conn):
    office = who(conn, "admin", "admin")
    first, later = _ceremony(conn), _ceremony(conn)
    gcer.record_rsvp(conn, who(conn, "S2", "student"), first, "S2", "going", guests=["G"])
    gcer.transfer(conn, who(conn, "S2", "student"), first, "S2", later, "ill")
    assert gcer.guests(conn, first, "S2") == []
    assert conn.execute("SELECT rsvp_status FROM ceremony_rsvps WHERE ceremony_id = ? AND "
                        "student_id = 'S2'", (later,)).fetchone()[0] == "pending"
    assert refused(gcer.transfer, conn, office, first, "S3", later)


def test_reminders_once_every_three_days(conn):
    office = who(conn, "admin", "admin")
    cid = _ceremony(conn)
    gcer.invite(conn, office, cid, ["S1"])
    day = (date.fromisoformat(DEADLINE) - timedelta(days=2)).isoformat()
    assert gcer.send_reminders(conn, day)["reminded"] == 1
    assert gcer.send_reminders(conn, day)["reminded"] == 0


def test_gown_cancel_and_refund(conn):
    office = who(conn, "admin", "admin")
    cid = _ceremony(conn)
    oid = conn.execute("INSERT INTO ceremony_gown_orders (ceremony_id, student_id, cost, "
                       "payment_status, payment_method) VALUES (?, 'S1', 45, 'paid', 'card')",
                       (cid,)).lastrowid
    assert refused(gcer.cancel_gown_order, conn, who(conn, "S2", "student"), oid, "x")
    gcer.cancel_gown_order(conn, who(conn, "S1", "student"), oid, "changed plans")
    refund = gcer.refund_gown_order(conn, office, oid)
    assert refund["amount"] == 45.0
    assert "no refund" in refused(gcer.refund_gown_order, conn, office, oid)


# ── transcripts and HEAR ────────────────────────────────────────────────


def test_transcript_share_consent_hashing_and_expiry(conn):
    office = who(conn, "admin", "admin")
    result = gc.confer(conn, office, "S1", render=render)
    assert "consent" in refused(gt.share, conn, office, result["conferral_id"], "Acme",
                                "hr@acme.test")
    share = gt.share(conn, who(conn, "S1", "student"), result["conferral_id"], "Acme",
                     "hr@acme.test")
    stored = conn.execute("SELECT token FROM transcript_access_tokens").fetchone()[0]
    assert stored != share["token"] and len(stored) == 64
    opened = gt.open_share(conn, share["token"])
    assert opened["ok"] and "transcript S1" in opened["html"]
    conn.execute("UPDATE transcript_access_tokens SET expires_at = '2000-01-01'")
    assert "expired" in gt.open_share(conn, share["token"])["message"]
    gt.revoke_share(conn, who(conn, "S1", "student"), share["token_id"])
    assert "withdrawn" in gt.open_share(conn, share["token"])["message"]


def test_hear(conn):
    office = who(conn, "admin", "admin")
    assert refused(gt.hear, conn, office, "S1")
    gc.confer(conn, office, "S1", render=render)
    student = who(conn, "S1", "student")
    aid = gt.add_achievement(conn, student, "S1", "Volunteering", "Peer mentor")
    assert gt.hear(conn, student, "S1")["6 Additional information"] == []
    gt.verify_achievement(conn, office, aid)
    assert len(gt.hear(conn, student, "S1")["6 Additional information"]) == 1
    assert refused(gt.remove_achievement, conn, student, aid)
    assert "Higher Education Achievement Report" in gt.hear_html(conn, office, "S1")
