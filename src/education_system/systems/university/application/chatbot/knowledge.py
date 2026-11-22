"""The chatbot's knowledge and memory: FAQ answers staff can manage,
questions it could not answer, feedback on answers, and the conversation
log — kept in the database for a set number of days, included in subject
access requests and erased on request.

* **FAQs** live in ``faqs``. The old ``faq_database.json`` is imported once;
  answers that look like placeholders or don't fit a UK university (``XXX``,
  ``FAFSA``) come in as drafts for an editor to fix. Only published answers
  are used.
* **Unanswered questions** are counted (by their normalised text) so editors
  can see what people ask that has no answer, and answer it with an FAQ.
* **Feedback**: a person can mark their own answers helpful or not; the
  FAQ's helpful / not-helpful counts follow.
* **The log**: every turn goes into ``chatbot_conversations`` (no more JSON
  files). :func:`purge` deletes turns older than the retention setting,
  except those tied to an open case.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta

from education_system.systems.university.application.chatbot import care
from education_system.systems.university.application.research import access as rows

PLACEHOLDER_MARKERS = ("XXX", "FAFSA", "lorem ipsum")
MATCH_THRESHOLD = 0.5
_STOP = {"a", "an", "the", "i", "my", "me", "do", "does", "how", "what", "when", "where", "is",
         "are", "can", "to", "for", "of", "in", "on", "and", "or", "you", "your", "please", "it"}

dicts, one, now = rows.dicts, rows.one, rows.now


def _words(text) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9']+", str(text or "").lower()) if w not in _STOP}


def normalise(text) -> str:
    return " ".join(sorted(_words(text)))


# ── FAQs ────────────────────────────────────────────────────────────────


def import_json(conn, path) -> int:
    """Import the old JSON FAQ file once (by question text). Returns how many."""
    care.ensure(conn)
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return 0
    added = 0
    for category, faqs in (data or {}).items():
        for question, answer in (faqs or {}).items():
            if conn.execute("SELECT 1 FROM faqs WHERE question = ?", (question,)).fetchone():
                continue
            draft = any(m.lower() in str(answer).lower() for m in PLACEHOLDER_MARKERS)
            conn.execute("INSERT INTO faqs (question, answer, category, created_by, "
                         "created_datetime, status, source) VALUES (?, ?, ?, 'import', ?, ?, "
                         "'faq_database.json')",
                         (question, answer, category, now(), "draft" if draft else "published"))
            added += 1
    return added


def faqs(conn, status=None, search=None) -> list[dict]:
    care.ensure(conn)
    where, params = [], []
    if status:
        where.append("COALESCE(status, 'published') = ?")
        params.append(status)
    if search:
        like = f"%{str(search).lower()}%"
        where.append("(LOWER(question) LIKE ? OR LOWER(answer) LIKE ?)")
        params += [like, like]
    return dicts(conn.execute("SELECT * FROM faqs" + (" WHERE " + " AND ".join(where) if where
                                                       else "") + " ORDER BY category, question",
                              params))


def save_faq(conn, username, role, question, answer, category, status="published",
             faq_id=None) -> int:
    care.ensure(conn)
    if not care.holds(conn, username, "editor", role):
        raise PermissionError("Only chatbot editors can change answers")
    question = rows.text(question, "Question", True)
    answer = rows.text(answer, "Answer", True)
    if status not in ("published", "draft", "retired"):
        raise ValueError("Status must be published, draft or retired")
    if status == "published" and any(m.lower() in answer.lower() for m in PLACEHOLDER_MARKERS):
        raise ValueError("The answer still contains a placeholder; fix it before publishing")
    if faq_id:
        if not conn.execute("UPDATE faqs SET question = ?, answer = ?, category = ?, status = ?, "
                            "updated_by = ?, updated_datetime = ? WHERE faq_id = ?",
                            (question, answer, category or "general", status, username, now(),
                             faq_id)).rowcount:
            raise ValueError("No such answer")
    else:
        faq_id = conn.execute("INSERT INTO faqs (question, answer, category, created_by, "
                              "created_datetime, status, source) VALUES (?, ?, ?, ?, ?, ?, "
                              "'editor')", (question, answer, category or "general", username,
                                            now(), status)).lastrowid
    care.audit(conn, username, "faq", faq_id, "saved", {"status": status})
    return int(faq_id)


def find_answer(conn, query) -> tuple[int | None, str | None]:
    """The best published answer for ``query`` (word overlap), if good enough."""
    care.ensure(conn)
    asked = _words(query)
    if not asked:
        return None, None
    best, score = None, 0.0
    for f in dicts(conn.execute("SELECT faq_id, question, answer FROM faqs WHERE COALESCE("
                                "status, 'published') = 'published'")):
        words = _words(f["question"])
        if not words:
            continue
        s = len(asked & words) / len(asked | words)
        if s > score:
            best, score = f, s
    if best is None or score < MATCH_THRESHOLD:
        return None, None
    conn.execute("UPDATE faqs SET view_count = COALESCE(view_count, 0) + 1 WHERE faq_id = ?",
                 (best["faq_id"],))
    return int(best["faq_id"]), best["answer"]


# ── unanswered questions ────────────────────────────────────────────────


def record_unanswered(conn, question) -> None:
    care.ensure(conn)
    key = normalise(question)
    if not key:
        return
    conn.execute("INSERT INTO chatbot_unanswered (question, normalised) VALUES (?, ?) ON CONFLICT "
                 "(normalised) DO UPDATE SET times_asked = times_asked + 1, last_asked_at = "
                 "datetime('now'), status = CASE WHEN status = 'dismissed' THEN 'dismissed' ELSE "
                 "'open' END", (str(question)[:500], key))


def unanswered(conn, status="open") -> list[dict]:
    care.ensure(conn)
    return dicts(conn.execute("SELECT * FROM chatbot_unanswered WHERE status = ? ORDER BY "
                              "times_asked DESC, last_asked_at DESC", (status,)))


def resolve_unanswered(conn, username, role, question_id, *, answer=None, category="general",
                       dismiss=False) -> int | None:
    care.ensure(conn)
    row = one(conn, "SELECT * FROM chatbot_unanswered WHERE question_id = ?", (question_id,))
    if not row:
        raise ValueError("No such question")
    if dismiss:
        if not care.holds(conn, username, "editor", role):
            raise PermissionError("Only chatbot editors can do this")
        conn.execute("UPDATE chatbot_unanswered SET status = 'dismissed', handled_by = ? WHERE "
                     "question_id = ?", (username, question_id))
        return None
    faq_id = save_faq(conn, username, role, row["question"], answer, category)
    conn.execute("UPDATE chatbot_unanswered SET status = 'answered', faq_id = ?, handled_by = ? "
                 "WHERE question_id = ?", (faq_id, username, question_id))
    return faq_id


# ── the conversation log ────────────────────────────────────────────────


def _user_row_id(conn, username):
    row = conn.execute("SELECT id FROM users WHERE username = ? OR student_id = ? LIMIT 1",
                       (username, username)).fetchone()
    return row[0] if row else None


def log_turn(conn, username, message, response, *, intent=None, confidence=None,
             session_id=None, crisis=False, case_id=None, faq_id=None, answered=True) -> int:
    care.ensure(conn)
    rid = conn.execute(
        "INSERT INTO chatbot_conversations (user_id, username, message, response, intent, "
        "confidence, timestamp, session_id, crisis, case_id, faq_id, answered) VALUES (?, ?, ?, "
        "?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (_user_row_id(conn, username), username or "anonymous", message, response, intent,
         confidence, now(), session_id, int(bool(crisis)), case_id, faq_id,
         int(bool(answered)))).lastrowid
    return int(rid)


def give_feedback(conn, username, row_id, helpful, comment="") -> None:
    care.ensure(conn)
    turn = one(conn, "SELECT * FROM chatbot_conversations WHERE id = ?", (row_id,))
    if not turn or turn["username"] != username:
        raise PermissionError("You can only rate your own answers")
    conn.execute("INSERT INTO chatbot_feedback (conversation_row_id, username, helpful, comment) "
                 "VALUES (?, ?, ?, ?) ON CONFLICT (conversation_row_id, username) DO UPDATE SET "
                 "helpful = excluded.helpful, comment = excluded.comment, given_at = "
                 "datetime('now')", (row_id, username, int(bool(helpful)), comment or None))
    if turn.get("faq_id"):
        column = "helpful_votes" if helpful else "not_helpful_votes"
        conn.execute(f"UPDATE faqs SET {column} = COALESCE({column}, 0) + 1 WHERE faq_id = ?",
                     (turn["faq_id"],))


def history(conn, username, limit=50) -> list[dict]:
    care.ensure(conn)
    return dicts(conn.execute("SELECT id, message, response, timestamp FROM "
                              "chatbot_conversations WHERE username = ? ORDER BY id DESC LIMIT ?",
                              (username, int(limit))))


def export(conn, username) -> dict:
    """Everything the chatbot holds about a person (subject access)."""
    care.ensure(conn)
    return {"conversations": dicts(conn.execute(
                "SELECT id, message, response, timestamp, crisis, case_id FROM "
                "chatbot_conversations WHERE username = ? ORDER BY id", (username,))),
            "feedback": dicts(conn.execute("SELECT * FROM chatbot_feedback WHERE username = ?",
                                           (username,))),
            "cases": dicts(conn.execute("SELECT case_id, kind, message, status, answer, "
                                        "created_at FROM chatbot_cases WHERE username = ?",
                                        (username,)))}


def erase(conn, actor, actor_role, username) -> dict:
    """Delete a person's chatbot conversations and feedback (cases that a
    safeguarding concern rests on are kept)."""
    care.ensure(conn)
    if str(actor_role).lower() not in care.ADMIN_ROLES and actor != username:
        raise PermissionError("Only the person or an administrator can erase this")
    conv = conn.execute("DELETE FROM chatbot_conversations WHERE username = ? AND COALESCE("
                        "crisis, 0) = 0", (username,)).rowcount
    fb = conn.execute("DELETE FROM chatbot_feedback WHERE username = ?", (username,)).rowcount
    care.audit(conn, actor, "erasure", username, "erased", {"conversations": conv,
                                                            "feedback": fb})
    return {"conversations": conv, "feedback": fb}


def purge(conn, as_of=None) -> int:
    """Delete turns older than the retention period (not those tied to an
    open case). Returns how many."""
    care.ensure(conn)
    days = int(care.settings(conn)["retention_days"])
    when = as_of or datetime.now()
    cutoff = (when - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    gone = conn.execute(
        "DELETE FROM chatbot_conversations WHERE timestamp < ? AND (case_id IS NULL OR case_id "
        "NOT IN (SELECT case_id FROM chatbot_cases WHERE status <> 'closed'))",
        (cutoff,)).rowcount
    if gone:
        care.audit(conn, "retention", "conversations", "purge", "deleted", {"rows": gone,
                                                                            "before": cutoff})
    return gone


def privacy_notice(conn) -> str:
    days = care.settings(conn)["retention_days"]
    return (f"We keep your chatbot conversations for {days} days to help you and improve "
            "answers, then delete them. You can download or delete them from the chatbot's "
            "support and privacy options. Messages suggesting someone may be at risk are passed "
            "to the safeguarding team.")


def stats(conn) -> dict:
    care.ensure(conn)
    total, answered = conn.execute("SELECT COUNT(*), COALESCE(SUM(answered), 0) FROM "
                                   "chatbot_conversations").fetchone()
    helpful = conn.execute("SELECT COUNT(*), COALESCE(SUM(helpful), 0) FROM "
                           "chatbot_feedback").fetchone()
    return {"turns": total, "answered_pct": round(100 * answered / total, 1) if total else None,
            "ratings": helpful[0],
            "helpful_pct": round(100 * helpful[1] / helpful[0], 1) if helpful[0] else None,
            "open_cases": conn.execute("SELECT COUNT(*) FROM chatbot_cases WHERE status IN "
                                       "('open', 'assigned')").fetchone()[0],
            "open_unanswered": conn.execute("SELECT COUNT(*) FROM chatbot_unanswered WHERE "
                                            "status = 'open'").fetchone()[0]}
