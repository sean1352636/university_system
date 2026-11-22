"""University chatbot care and knowledge rules: personal data only for
the asker, crisis detection / reply / one alert a day, human-help cases
answered into the inbox, staff roles, settings without placeholders, the
managed FAQ (import, drafts for placeholders, matching), unanswered
questions, feedback on own answers, the conversation log with export,
erasure and retention. Temporary databases only."""

import json
import sqlite3
from datetime import datetime, timedelta

import pytest

from education_system.systems.university.application.chatbot import care
from education_system.systems.university.application.chatbot import knowledge as know

#: The existing chatbot tables, before migration a8c0e2f4b6d9.
EXISTING = [
'CREATE TABLE faqs ( faq_id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT NOT NULL, answer TEXT NOT NULL, category TEXT NOT NULL, created_by TEXT NOT NULL, created_datetime TEXT NOT NULL, updated_datetime TEXT, view_count INTEGER DEFAULT 0, helpful_votes INTEGER DEFAULT 0, tags TEXT, is_featured BOOLEAN DEFAULT 0 )',
'CREATE TABLE "chatbot_conversations" ( id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT NOT NULL, message TEXT NOT NULL, response TEXT NOT NULL, intent TEXT, confidence REAL, timestamp TEXT NOT NULL, session_id TEXT)',
    "CREATE TABLE students (student_id TEXT PRIMARY KEY, first_name TEXT, last_name TEXT, "
    "email_address TEXT, status TEXT)",
    "CREATE TABLE staff (id INTEGER PRIMARY KEY, username TEXT UNIQUE, name TEXT, email TEXT, "
    "role TEXT, status TEXT DEFAULT 'active')",
    "CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, last_name TEXT, "
    "email TEXT, role TEXT, student_id TEXT, service_account INTEGER DEFAULT 0)",
    "CREATE TABLE messages (id INTEGER PRIMARY KEY, sender_id INTEGER, recipient_id INTEGER, "
    "subject TEXT, message TEXT, content TEXT, is_read INTEGER, sent_at TEXT)",
]


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    for ddl in EXISTING:
        c.execute(ddl)
    for sid in ("S1", "S2"):
        c.execute("INSERT INTO students VALUES (?, 'Sam', 'Student', ?, 'Active')",
                  (sid, f"{sid.lower()}@uni.test"))
        c.execute("INSERT INTO users (username, role, student_id) VALUES (?, 'student', ?)",
                  (sid, sid))
    for username in ("agent1", "editor1", "plain"):
        c.execute("INSERT INTO staff (username, name, role) VALUES (?, ?, 'staff')",
                  (username, username))
        c.execute("INSERT INTO users (username, role) VALUES (?, 'staff')", (username,))
    c.execute("INSERT INTO users (username, role) VALUES ('admin', 'admin')")
    care.ensure(c)
    care.grant(c, "admin", "admin", "agent1", "agent")
    care.grant(c, "admin", "admin", "editor1", "editor")
    c.commit()
    yield c
    c.close()


def refused(fn, *args, **kwargs) -> str:
    with pytest.raises((ValueError, PermissionError)) as exc:
        fn(*args, **kwargs)
    return str(exc.value)


# ── whose data ──────────────────────────────────────────────────────────


def test_personal_data_is_only_the_askers_own(conn):
    assert care.personal_access(conn, "S1") == ("S1", None)
    sid, refusal = care.personal_access(conn, "S1", "S2")
    assert sid is None and "only show your own" in refusal
    assert care.personal_access(conn, "S1", "S1") == ("S1", None)
    assert care.personal_access(conn, "anonymous")[0] is None
    sid, refusal = care.personal_access(conn, "plain", "S2")
    assert sid is None and refusal


# ── crisis ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize("text", ["I want to kill myself", "thinking about suicide",
                                  "I've been self-harming", "I don't want to live anymore",
                                  "I am not safe at home"])
def test_crisis_detected(text):
    assert care.is_crisis(text)


@pytest.mark.parametrize("text", ["the deadline is killing me", "how do I end my lease",
                                  "my balance please"])
def test_not_crisis(text):
    assert not care.is_crisis(text)


def test_crisis_reply_has_real_contacts_and_the_universitys_own(conn):
    reply = care.crisis_reply(conn)
    assert "999" in reply and "116 123" in reply and "85258" in reply
    assert "XXX" not in reply
    care.set_setting(conn, "admin", "admin", "counselling_contact", "01234 567890")
    assert "01234 567890" in care.crisis_reply(conn)


def test_one_alert_per_person_per_day(conn):
    first = care.raise_crisis(conn, "S1", "I want to die")
    assert first["alert"]["username"] == "S1"
    second = care.raise_crisis(conn, "S1", "still feel the same")
    assert second["case_id"] == first["case_id"] and second["alert"] is None
    conn.execute("UPDATE chatbot_cases SET created_at = ?",
                 ((datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"),))
    assert care.raise_crisis(conn, "S1", "again")["alert"] is not None


def test_safeguarding_alert_uses_the_safeguarding_service(conn, monkeypatch):
    seen = {}

    class Fake:
        @staticmethod
        def save_submission(user, content, severity, categories, **kw):
            seen.update(user=user, severity=severity, categories=categories)
            return 77

    import education_system.systems.university.domains.safeguarding.application.services as svc
    monkeypatch.setattr(svc, "submissions", Fake, raising=False)
    monkeypatch.setitem(__import__("sys").modules,
                        "education_system.systems.university.domains.safeguarding.application."
                        "services.submissions", Fake)
    result = care.raise_crisis(conn, "S1", "I want to die")
    conn.commit()
    from education_system.systems.university.infrastructure.database import db as dbmod
    monkeypatch.setattr(dbmod, "transaction", lambda: _Ctx(conn))
    assert care.send_safeguarding_alert(result) == 77
    assert seen["severity"] == "CRITICAL"
    assert any("Self-harm" in k for k in seen["categories"])
    assert conn.execute("SELECT safeguarding_case_id FROM chatbot_cases").fetchone()[0] == 77


class _Ctx:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, *exc):
        return False


# ── human help ──────────────────────────────────────────────────────────


def test_cases_are_answered_into_the_inbox(conn):
    result = care.open_case(conn, "S1", "I need help with my visa")
    assert result["case_id"] and "two working days" in result["reply"]
    assert care.open_case(conn, "anonymous", "help")["case_id"] is None
    assert refused(care.cases, conn, "plain", "staff")
    [case] = care.cases(conn, "agent1", "staff")
    care.answer(conn, "agent1", "staff", case["case_id"], "Book with the visa team")
    assert care.my_cases(conn, "S1")[0]["status"] == "answered"
    assert conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0] >= 1
    assert "already" in refused(care.answer, conn, "agent1", "staff", case["case_id"], "x")


def test_crisis_cases_are_for_administrators_only(conn):
    care.raise_crisis(conn, "S1", "I want to die")
    assert care.cases(conn, "agent1", "staff") == []
    assert [c["kind"] for c in care.cases(conn, "admin", "admin")] == ["crisis"]


def test_settings_refuse_placeholders(conn):
    assert "placeholder" in refused(care.set_setting, conn, "admin", "admin",
                                    "out_of_hours_number", "0800-XXX-XXXX")
    assert refused(care.set_setting, conn, "agent1", "staff", "reply_promise", "x")
    assert refused(care.set_setting, conn, "admin", "admin", "retention_days", "2")


# ── knowledge ───────────────────────────────────────────────────────────


def test_faq_import_and_matching(conn, tmp_path):
    path = tmp_path / "faq.json"
    path.write_text(json.dumps({"technical": {
        "How do I reset my password?": "Use the Forgot Password link.",
        "How do I apply for financial aid?": "Submit the FAFSA form."}}))
    assert know.import_json(conn, path) == 2
    assert know.import_json(conn, path) == 0
    statuses = {f["question"]: f["status"] for f in know.faqs(conn)}
    assert statuses["How do I apply for financial aid?"] == "draft"
    faq_id, answer = know.find_answer(conn, "how can I reset my password")
    assert answer == "Use the Forgot Password link."
    assert know.find_answer(conn, "apply for financial aid") == (None, None)


def test_only_editors_change_answers_and_placeholders_stay_drafts(conn):
    assert refused(know.save_faq, conn, "agent1", "staff", "Q", "A", "general")
    assert "placeholder" in refused(know.save_faq, conn, "editor1", "staff", "Crisis line?",
                                    "Call 0800-XXX-XXXX", "wellbeing")
    know.save_faq(conn, "editor1", "staff", "Crisis line?", "Call 0800-XXX-XXXX", "wellbeing",
                  status="draft")


def test_unanswered_questions_are_counted_and_answered(conn):
    know.record_unanswered(conn, "Where is the chess club?")
    know.record_unanswered(conn, "where is the chess club")
    [q] = know.unanswered(conn)
    assert q["times_asked"] == 2
    faq_id = know.resolve_unanswered(conn, "editor1", "staff", q["question_id"],
                                     answer="In the Union building.", category="campus")
    assert faq_id and know.unanswered(conn) == []
    assert know.find_answer(conn, "where is the chess club")[1] == "In the Union building."


# ── the log ─────────────────────────────────────────────────────────────


def test_feedback_only_on_own_answers(conn):
    faq_id = know.save_faq(conn, "editor1", "staff", "Q?", "A.", "general")
    row = know.log_turn(conn, "S1", "Q?", "A.", faq_id=faq_id)
    assert refused(know.give_feedback, conn, "S2", row, True)
    know.give_feedback(conn, "S1", row, False, "no")
    assert know.faqs(conn)[0]["not_helpful_votes"] == 1


def test_export_erase_and_retention(conn):
    know.log_turn(conn, "S1", "hello", "hi")
    know.log_turn(conn, "S1", "I want to die", "help", crisis=True)
    assert len(know.export(conn, "S1")["conversations"]) == 2
    assert refused(know.erase, conn, "S2", "student", "S1")
    assert know.erase(conn, "S1", "student", "S1")["conversations"] == 1     # crisis kept
    know.log_turn(conn, "S2", "old", "old")
    conn.execute("UPDATE chatbot_conversations SET timestamp = '2000-01-01 00:00:00' WHERE "
                 "username = 'S2'")
    assert know.purge(conn) == 1
    assert "180 days" in know.privacy_notice(conn)
