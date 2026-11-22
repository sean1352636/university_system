"""The e-mail telling a student how the checks on their submission went: what it
says, what is held back for staff review, and who gets it. Temporary databases."""

import json
import sqlite3
from types import SimpleNamespace

import pytest

from education_system.systems.university.application.integrity import access, submission_results
from education_system.systems.university.application.integrity import ai as integrity_ai

SCHEMA = """
CREATE TABLE students (student_id TEXT PRIMARY KEY, first_name TEXT, email_address TEXT);
CREATE TABLE assignments (id INTEGER PRIMARY KEY, module_code TEXT, title TEXT);
CREATE TABLE assignment_submissions (id INTEGER PRIMARY KEY, assignment_id INTEGER,
    student_id TEXT, group_id INTEGER);
CREATE TABLE plagiarism_results (id INTEGER PRIMARY KEY, similarity_score REAL, submission_id INTEGER,
    words_checked INTEGER, words_excluded INTEGER, paraphrase_score REAL, released_to_student INTEGER);
CREATE TABLE plagiarism_matches (id INTEGER PRIMARY KEY, result_id INTEGER, counted INTEGER,
    matched_document_id INTEGER);
INSERT INTO students VALUES ('S1', 'Asha', 's1@uni.test'), ('S2', 'Ben', 's2@uni.test'),
                            ('S3', 'Cai', NULL);
INSERT INTO assignments VALUES (1, 'CS-101', 'Essay One');
INSERT INTO assignment_submissions VALUES (1, 1, 'S1', NULL), (2, 1, 'S1', 7), (3, 1, 'S2', 7),
                                          (4, 1, 'S3', NULL);
"""


@pytest.fixture
def conn(monkeypatch):
    c = sqlite3.connect(":memory:")
    c.executescript(SCHEMA)
    monkeypatch.setattr(access, "ensure", lambda _c: None)
    monkeypatch.setattr(access, "setting", lambda _c, key: {"release_after_review": "1"}[key])
    monkeypatch.setattr(access, "number", lambda _c, key: 0.6)
    monkeypatch.setattr(integrity_ai, "latest_for_submission", lambda _c, _s: None)
    yield c
    c.close()


def _similarity(conn, submission_id=1, score=0.12, released=1, sources=1):
    rid = conn.execute("INSERT INTO plagiarism_results (similarity_score, submission_id, "
                       "words_checked, words_excluded, paraphrase_score, released_to_student) "
                       "VALUES (?, ?, 500, 20, 0, ?)", (score, submission_id, released)).lastrowid
    for _ in range(sources):
        conn.execute("INSERT INTO plagiarism_matches (result_id, counted, matched_document_id) "
                     "VALUES (?, 1, 99)", (rid,))
    return rid


def _reading(monkeypatch, score=0.1, level="low", strength=0.1, decision=None, note=None):
    detail = {"strength": strength, "indicators": [{"label": "Stock phrasing", "shown": "2 found"}]}
    if note:
        detail["note"] = note
    row = {"ai_score": score, "level": level, "decision": decision,
           "detailed_results": json.dumps(detail), "assignment_submission_id": 1}
    monkeypatch.setattr(integrity_ai, "latest_for_submission", lambda _c, _s: row)
    return row


def test_no_email_when_neither_check_ran(conn):
    assert submission_results.results_emails(conn, 1) == []


def test_released_results_are_in_the_email(conn, monkeypatch):
    _similarity(conn)
    _reading(monkeypatch)
    (address, subject, body), = submission_results.results_emails(conn, 1)
    assert address == "s1@uni.test" and "Essay One" in subject
    assert "Dear Asha" in body and "CS-101" in body
    assert "12% of the 500 words checked also appear in 1 other source(s)" in body
    assert "Reading: low (10%)" in body and "Stock phrasing: 2 found" in body
    assert "indicators, not evidence" in body


def test_no_match_says_so(conn):
    _similarity(conn, score=0, sources=0)
    body = submission_results.results_emails(conn, 1)[0][2]
    assert "No matching text was found in the 500 words checked" in body


def test_held_results_show_no_figures(conn, monkeypatch):
    _similarity(conn, score=0.73, released=0)
    _reading(monkeypatch, score=0.9, level="high", strength=0.9)
    body = submission_results.results_emails(conn, 1)[0][2]
    assert body.count("reviewing this result first") == 2
    assert "73%" not in body and "90%" not in body


def test_one_check_can_be_held_while_the_other_is_shown(conn, monkeypatch):
    _similarity(conn, score=0.73, released=0)
    _reading(monkeypatch)
    body = submission_results.results_emails(conn, 1)[0][2]
    assert body.count("reviewing this result first") == 1 and "Reading: low" in body


def test_too_short_for_a_reading_says_why(conn, monkeypatch):
    _similarity(conn)
    _reading(monkeypatch, level="not enough text", strength=None, score=0,
             note="Fewer than 250 words of the student's own prose; no reading.")
    assert "Fewer than 250 words" in submission_results.results_emails(conn, 1)[0][2]


def test_check_turned_off_for_the_module_is_explained(conn):
    _similarity(conn)
    assert submission_results.NOT_RUN in submission_results.results_emails(conn, 1)[0][2]


def test_every_group_member_is_told(conn):
    _similarity(conn, submission_id=2)
    emails = submission_results.results_emails(conn, 2)
    assert sorted(e[0] for e in emails) == ["s1@uni.test", "s2@uni.test"]
    assert any("Dear Ben" in e[2] for e in emails)


def test_a_student_with_no_address_is_skipped(conn):
    _similarity(conn, submission_id=4)
    conn.execute("CREATE TABLE users (email TEXT, student_id TEXT, username TEXT)")
    assert submission_results.results_emails(conn, 4) == []


def test_review_finished_gives_the_figures(conn):
    rid = _similarity(conn, score=0.73, released=0)
    (_address, subject, body), = submission_results.similarity_review_finished(conn, rid)
    assert "Review finished" in subject and "73%" in body and "similarity check" in body


def test_reading_review_finished_gives_the_figures(conn, monkeypatch):
    row = _reading(monkeypatch, score=0.9, level="high", strength=0.9)
    body = submission_results.reading_review_finished(conn, row)[0][2]
    assert "AI-writing reading" in body and "Reading: high (90%)" in body


def test_hook_emails_after_a_successful_check_and_not_after_a_failed_one(monkeypatch):
    from education_system.systems.university.infrastructure.integrity import submission_hook as hook
    emailed = []
    monkeypatch.setattr(hook, "_email_results", lambda sid, _db: emailed.append(sid))
    monkeypatch.setattr(hook, "check_now", lambda *a, **k: 1)
    assert hook._safe(5, "text", None, None) and emailed == [5]

    def boom(*_a, **_k):
        raise RuntimeError("no text")
    monkeypatch.setattr(hook, "check_now", boom)
    monkeypatch.setattr(hook, "_record_failure", lambda *a: None)
    assert not hook._safe(6, "text", None, None) and emailed == [5]


def test_a_mail_failure_does_not_count_as_a_failed_check(monkeypatch):
    from education_system.systems.university.infrastructure.integrity import submission_hook as hook
    monkeypatch.setattr(hook, "check_now", lambda *a, **k: 1)
    monkeypatch.setattr(hook, "_checks_on", lambda *_a: True)
    monkeypatch.setattr(hook, "_connect", lambda _db: SimpleNamespace(
        close=lambda: None, commit=lambda: None))
    monkeypatch.setattr(hook.submission_results, "results_emails",
                        lambda *_a: (_ for _ in ()).throw(RuntimeError("mail")))
    assert hook._safe(7, "text", None, None) is True
