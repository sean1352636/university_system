"""Academic integrity rules: quotations, reference lists and template text
are not counted; a student's own work is never a match; checks are scoped
to module staff; students see only their own released reports without
other students' text; review → case → outcome → appeal with the mark
penalty applied and restored; draft checks; retention keeps case evidence;
export and erasure. Temporary databases only."""

import sqlite3
from datetime import datetime

import pytest

from education_system.systems.university.application.integrity import access
from education_system.systems.university.application.integrity import evidence
from education_system.systems.university.application.integrity import records
from education_system.systems.university.application.integrity import review
from education_system.systems.university.application.integrity import plagiarism_checks as checks
from education_system.systems.university.application.integrity import plagiarism_text as ptext

EXISTING = [
    "CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, last_name TEXT, "
    "email TEXT, role TEXT, student_id TEXT, service_account INTEGER DEFAULT 0)",
    "CREATE TABLE students (student_id TEXT PRIMARY KEY, email_address TEXT)",
    "CREATE TABLE modules (module_code TEXT PRIMARY KEY, instructor TEXT, instructor_id INTEGER)",
    "CREATE TABLE module_staff (id INTEGER PRIMARY KEY, module_code TEXT, username TEXT, "
    "role TEXT, hours REAL DEFAULT 0, academic_year TEXT DEFAULT '')",
    "CREATE TABLE assignments (id INTEGER PRIMARY KEY, module_code TEXT, title TEXT, "
    "max_marks INTEGER, is_active INTEGER DEFAULT 1)",
    "CREATE TABLE assignment_submissions (id INTEGER PRIMARY KEY, assignment_id INTEGER, "
    "student_id TEXT, submission_date TEXT, file_name TEXT, file_path TEXT, content TEXT, "
    "grade REAL, status TEXT DEFAULT 'submitted', is_final_submission INTEGER DEFAULT 1, "
    "version_number INTEGER DEFAULT 1, grade_released_at TEXT)",
    "CREATE TABLE module_grades (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT, "
    "module_code TEXT, final_score REAL, final_grade TEXT, completion_date TEXT, "
    "date_recorded TEXT, status TEXT DEFAULT 'provisional', locked INTEGER DEFAULT 0, "
    "outcome TEXT, attempt INTEGER DEFAULT 1, is_complete INTEGER DEFAULT 0)",
    "CREATE TABLE document_repository (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, "
    "content TEXT NOT NULL, content_hash TEXT NOT NULL, author_id INTEGER NOT NULL, "
    "module_code TEXT, submission_date TEXT NOT NULL, file_type TEXT, word_count INTEGER, "
    "created_at TEXT, updated_at TEXT)",
    "CREATE TABLE plagiarism_results (id INTEGER PRIMARY KEY AUTOINCREMENT, document_id INTEGER "
    "NOT NULL REFERENCES document_repository (id) ON DELETE CASCADE, matched_document_id "
    "INTEGER, similarity_score REAL NOT NULL, check_date TEXT NOT NULL, checked_by INTEGER, "
    "status TEXT NOT NULL, report TEXT, threshold_used REAL DEFAULT 0.3, created_at TEXT)",
]

ESSAY = ("The industrial revolution transformed the economic structure of Britain by moving "
         "labour from agriculture into factories and creating new urban centres with their own "
         "social problems. ") * 3


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.execute("PRAGMA foreign_keys = ON")
    for ddl in EXISTING:
        c.execute(ddl)
    for i, (name, role, sid) in enumerate((("s1", "student", "S1"), ("s2", "student", "S2"),
                                           ("s3", "student", "S3"), ("lect", "staff", None),
                                           ("other", "staff", None), ("officer", "staff", None),
                                           ("officer2", "staff", None), ("admin", "admin", None)),
                                          start=1):
        c.execute("INSERT INTO users (id, username, role, student_id, email) VALUES (?, ?, ?, ?, ?)",
                  (i, name, role, sid, f"{name}@uni.test"))
        if sid:
            c.execute("INSERT INTO students VALUES (?, ?)", (sid, f"{name}@uni.test"))
    c.execute("INSERT INTO modules VALUES ('HIS101', NULL, NULL), ('BIO101', 'other', 5)")
    c.execute("INSERT INTO module_staff (module_code, username, role) VALUES "
              "('HIS101', 'lect', 'lecturer')")
    c.execute("INSERT INTO assignments (id, module_code, title, max_marks) VALUES "
              "(1, 'HIS101', 'Essay', 100)")
    access.ensure(c)
    admin = access.person(c, "admin")
    access.grant(c, admin, "officer", "officer")
    access.grant(c, admin, "officer2", "officer")
    c.commit()
    yield c
    c.close()


def who(conn, name):
    return access.person(conn, name)


def submit(conn, sub_id, student, text, grade=70):
    conn.execute("INSERT INTO assignment_submissions (id, assignment_id, student_id, "
                 "submission_date, file_name, content, grade) VALUES (?, 1, ?, "
                 "'2026-10-17 10:00:00', 'essay.txt', ?, ?)", (sub_id, student, text, grade))
    return checks.check_submission(conn, sub_id, text)


def refused(fn, *args, **kwargs) -> str:
    with pytest.raises((ValueError, PermissionError)) as exc:
        fn(*args, **kwargs)
    return str(exc.value)


# ── text ────────────────────────────────────────────────────────────────


def test_quotes_and_references_are_left_out():
    text = ('My view. "A quoted sentence from a famous book" is cited.\n'
            + "body words " * 20 + "\nReferences\nSmith J (2001) A book title here")
    prepared = ptext.prepare(text)
    assert "quoted" not in prepared.tokens and "smith" not in prepared.tokens
    assert prepared.excluded_words >= 13


def test_code_comments_are_left_out():
    prepared = ptext.prepare("x = 1  # set the counter\n/* block comment */ y = x", "py")
    assert "counter" not in prepared.tokens and "block" not in prepared.tokens
    assert ptext.is_code("py") and not ptext.is_code("docx")


def test_compare_finds_passages_with_offsets():
    a = ptext.prepare("one two three four five six seven eight unique words here", n=6)
    b = ptext.prepare("prefix one two three four five six seven eight suffix", n=6)
    found = ptext.compare(a, b, 6)
    assert len(found["covered"]) == 8
    passage = found["passages"][0]
    assert "one two three four five six seven eight".startswith(
        "one two three four five six seven eight"[: passage["end"] - passage["start"]])


# ── checks ──────────────────────────────────────────────────────────────


def test_copied_work_is_flagged_and_held_for_review(conn):
    submit(conn, 1, "S1", ESSAY)
    rid = submit(conn, 2, "S2", "Introduction. " + ESSAY)
    row = conn.execute("SELECT similarity_score, status, review_status, released_to_student "
                       "FROM plagiarism_results WHERE id = ?", (rid,)).fetchone()
    assert row[0] > 0.9 and row[1] == "HIGH" and row[2] == "pending" and row[3] == 0


def test_own_earlier_work_and_original_work_do_not_match(conn):
    submit(conn, 1, "S1", ESSAY)
    rid = submit(conn, 2, "S1", ESSAY)  # resubmission by the same student
    assert conn.execute("SELECT similarity_score FROM plagiarism_results WHERE id = ?",
                        (rid,)).fetchone()[0] == 0
    rid = submit(conn, 3, "S3", "Coral reefs in warm seas support many species of fish.")
    assert conn.execute("SELECT status FROM plagiarism_results WHERE id = ?",
                        (rid,)).fetchone()[0] == "NO_MATCH"


def test_template_text_is_not_counted(conn):
    lect = who(conn, "lect")
    checks.add_document(conn, lect, title="Set text", content=ESSAY, module_code="HIS101",
                        kind="template", assignment_id=1)
    submit(conn, 1, "S1", ESSAY)
    rid = submit(conn, 2, "S2", ESSAY)
    assert conn.execute("SELECT similarity_score FROM plagiarism_results WHERE id = ?",
                        (rid,)).fetchone()[0] == 0


def test_checks_can_be_turned_off_for_a_module(conn):
    access.set_module_settings(conn, who(conn, "lect"), "HIS101", enabled=False, threshold=0.3)
    assert submit(conn, 1, "S1", ESSAY) is None
    assert refused(access.set_module_settings, conn, who(conn, "other"), "HIS101",
                   enabled=True, threshold=0.3)


def test_only_module_staff_run_checks_and_see_documents(conn):
    submit(conn, 1, "S1", ESSAY)
    doc_id = conn.execute("SELECT id FROM document_repository").fetchone()[0]
    assert refused(checks.run_check, conn, doc_id, who=who(conn, "other"))
    assert refused(checks.run_check, conn, doc_id, who=who(conn, "s2"))
    checks.run_check(conn, doc_id, who=who(conn, "lect"))
    assert checks.documents(conn, who(conn, "other")) == []
    assert len(checks.documents(conn, who(conn, "lect"))) == 1
    assert [d["id"] for d in checks.documents(conn, who(conn, "s1"))] == [doc_id]
    assert checks.documents(conn, who(conn, "s2")) == []
    assert refused(checks.document, conn, who(conn, "s2"), doc_id)


# ── reports ─────────────────────────────────────────────────────────────


def test_students_see_own_released_reports_without_other_students_text(conn):
    submit(conn, 1, "S1", ESSAY)
    rid = submit(conn, 2, "S2", "Introduction. " + ESSAY)
    s2 = who(conn, "s2")
    assert "not been released" in refused(review.result_detail, conn, s2, rid)
    assert review.results(conn, s2) == []
    staff_view = review.result_detail(conn, who(conn, "lect"), rid)
    assert staff_view["matches"][0]["passages"][0]["source_text"]
    review.review(conn, who(conn, "lect"), rid, "no_concern", "Properly cited group text")
    mine = review.result_detail(conn, s2, rid)
    passage = mine["matches"][0]["passages"][0]
    assert "source_text" not in passage and "another student's" in mine["matches"][0]["source"]
    assert refused(review.result_detail, conn, who(conn, "s1"), rid)


# ── review, case, outcome, appeal ───────────────────────────────────────


def test_referral_decision_penalty_and_appeal(conn):
    submit(conn, 1, "S1", ESSAY)
    rid = submit(conn, 2, "S2", ESSAY, grade=72)
    lect, officer, officer2 = who(conn, "lect"), who(conn, "officer"), who(conn, "officer2")
    assert refused(review.review, conn, lect, rid, "refer", "")
    out = review.review(conn, lect, rid, "refer", "Unattributed overlap")
    case_id = out["case_id"]
    assert out["emails"][0][0] == "s2@uni.test"
    assert refused(review.review, conn, lect, rid, "no_concern", "again")
    assert refused(review.decide, conn, lect, case_id, "mark_zero", "x")
    review.advance(conn, officer, case_id, "investigating", "Reading drafts")
    assert review.advance(conn, officer, case_id, "meeting", "Thursday 10am")
    assert refused(review.advance, conn, officer, case_id, "investigating", "back")
    assert "has until" in refused(review.decide, conn, officer, case_id, "mark_capped", "Copied")
    s2 = who(conn, "s2")
    evidence.submit_statement(conn, s2, case_id, "We were told to work on this essay as a group.")
    review.decide(conn, officer, case_id, "mark_capped", "Copied passages")
    assert conn.execute("SELECT grade FROM assignment_submissions WHERE id = 2").fetchone() == (40.0,)
    assert refused(review.lodge_appeal, conn, who(conn, "s1"), case_id, "x" * 30)
    assert refused(review.lodge_appeal, conn, s2, case_id, "too short")
    review.lodge_appeal(conn, s2, case_id, "Group work was allowed on this assessment.")
    appeal = conn.execute("SELECT appeal_id FROM integrity_appeals").fetchone()[0]
    assert refused(review.close, conn, officer, case_id)
    assert "someone other" in refused(review.decide_appeal, conn, officer, appeal, True, "ok")
    review.decide_appeal(conn, officer2, appeal, True, "Permitted collaboration")
    assert conn.execute("SELECT grade FROM assignment_submissions WHERE id = 2").fetchone() == (72.0,)
    assert review.case(conn, s2, case_id)["status"] == "dismissed"
    review.close(conn, officer, case_id)
    assert [c["id"] for c in review.cases(conn, s2)] == [case_id]
    assert review.cases(conn, who(conn, "s1")) == []


def test_mark_zero_and_no_case(conn):
    submit(conn, 1, "S1", ESSAY)
    rid = submit(conn, 2, "S2", ESSAY)
    case_id = review.review(conn, who(conn, "lect"), rid, "refer", "Overlap")["case_id"]
    officer = who(conn, "officer")
    evidence.set_response_due(conn, officer, case_id, "2020-01-01", "Student will not respond")
    assert "recommended outcomes" in refused(review.decide, conn, officer, case_id, "mark_zero",
                                             "Whole essay copied")
    review.decide(conn, officer, case_id, "mark_zero", "Whole essay copied",
                  departure_reason="The whole essay was copied")
    assert conn.execute("SELECT grade FROM assignment_submissions WHERE id = 2").fetchone() == (0.0,)
    assert refused(review.decide, conn, who(conn, "officer"), case_id, "no_case", "again")


# ── drafts, settings, roles ─────────────────────────────────────────────


def test_draft_check_shows_own_passages_and_is_limited(conn):
    submit(conn, 1, "S1", ESSAY)
    s2 = who(conn, "s2")
    found = checks.self_check(conn, s2, text=ESSAY, module_code="HIS101", assignment_id=1)
    assert found["score"] > 0.9 and found["passages"][0]["text"]
    assert conn.execute("SELECT COUNT(*) FROM document_repository").fetchone()[0] == 1
    for _ in range(checks.SELF_CHECKS_PER_DAY - 1):
        checks.self_check(conn, s2, text="x y z", module_code="HIS101")
    assert "a day" in refused(checks.self_check, conn, s2, text="x", module_code="HIS101")
    assert refused(checks.self_check, conn, who(conn, "lect"), text="x")


def test_settings_roles_and_notice(conn):
    officer, lect = who(conn, "officer"), who(conn, "lect")
    assert refused(access.set_setting, conn, lect, "review_threshold", "0.4")
    assert refused(access.set_setting, conn, officer, "review_threshold", "2")
    assert refused(access.set_setting, conn, officer, "shingle_words", "40")
    access.set_setting(conn, officer, "review_threshold", "0.4")
    assert access.module_threshold(conn, "HIS101") == 0.4
    assert refused(access.grant, conn, officer, "lect", "reviewer")
    assert refused(access.grant, conn, who(conn, "admin"), "s1", "reviewer")
    access.grant(conn, who(conn, "admin"), "other", "reviewer")
    assert access.taught_modules(conn, who(conn, "other")) is None
    s1 = who(conn, "s1")
    assert not access.has_acknowledged(conn, s1)
    access.acknowledge(conn, s1)
    assert access.has_acknowledged(conn, s1)
    assert refused(access.recent_audit, conn, lect)


# ── retention and subject access ────────────────────────────────────────


def test_retention_keeps_evidence_in_live_cases(conn):
    submit(conn, 1, "S1", ESSAY)
    rid = submit(conn, 2, "S2", ESSAY)
    review.review(conn, who(conn, "lect"), rid, "refer", "Overlap")
    submit(conn, 3, "S3", "Coral reefs support many species of fish in warm seas.")
    assert records.purge(conn) == 0
    assert records.purge(conn, as_of=datetime(2040, 1, 1)) == 1  # only S3; S1/S2 are evidence
    assert conn.execute("SELECT content FROM document_repository WHERE student_id = 'S3'"
                        ).fetchone()[0] == records.PURGED_TEXT
    doc = conn.execute("SELECT id FROM document_repository WHERE student_id = 'S3'").fetchone()[0]
    assert "retention" in refused(checks.run_check, conn, doc, who=who(conn, "lect"))


def test_export_and_erase(conn):
    submit(conn, 1, "S1", ESSAY)
    rid = submit(conn, 2, "S2", ESSAY)
    review.review(conn, who(conn, "lect"), rid, "refer", "Overlap")
    submit(conn, 3, "S2", "A later and entirely different piece of work about rivers.")
    assert refused(records.export, conn, who(conn, "s1"), "S2")
    data = records.export(conn, who(conn, "s2"), "S2")
    assert len(data["documents"]) == 2 and len(data["cases"]) == 1
    assert refused(records.erase, conn, who(conn, "officer"), "S2")
    done = records.erase(conn, who(conn, "admin"), "S2")
    assert done["removed"] == 1 and len(done["kept_as_evidence"]) == 1
