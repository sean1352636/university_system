"""The chatbot's link to the care, knowledge and logging rules in
``university/application/chatbot/care`` and ``chatbot_knowledge``.

Each call opens its own short transaction on the chatbot's database and
commits, then does any post-commit work (safeguarding alert, e-mails).
Failures never break the conversation, except where safety depends on
them (a crisis reply is always returned).
"""

from __future__ import annotations

import logging

from education_system import paths

logger = logging.getLogger(__name__)


def _rules():
    from education_system.systems.university.application.chatbot import (
        care as chatbot_care,
        knowledge as chatbot_knowledge,
    )
    return chatbot_care, chatbot_knowledge


def _run(chatbot, fn, *args, **kwargs):
    from education_system.systems.university.infrastructure.database.db import get_connection
    conn = get_connection(getattr(chatbot, "db_path", None), row_factory=False)
    try:
        result = fn(conn, *args, **kwargs)
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _send(emails):
    if emails:
        from education_system.systems.university.infrastructure.ui.record_screens import (
            send_emails,
        )
        send_emails(emails)


# ── safety ──────────────────────────────────────────────────────────────


def crisis_check(chatbot, message, username, session_id=None) -> str | None:
    """The crisis reply when ``message`` suggests someone is at risk."""
    care, knowledge = _rules()
    if not care.is_crisis(message):
        return None
    try:
        reply = _run(chatbot, lambda conn: care.crisis_reply(conn))
    except Exception:
        logger.exception("crisis reply settings unavailable")
        reply = ("If you are in immediate danger call 999. Samaritans: 116 123 (free, any time). "
                 "Shout: text SHOUT to 85258.")
    try:
        result = _run(chatbot, care.raise_crisis, username or "anonymous", message)
        _run(chatbot, knowledge.log_turn, username, message, reply, intent="crisis",
             session_id=session_id, crisis=True, case_id=result["case_id"])
        care.send_safeguarding_alert(result)
    except Exception:
        logger.exception("crisis case could not be recorded")
    return reply


def personal(chatbot, context, typed_id=None) -> tuple[str | None, str | None]:
    """``(student_id, refusal)`` for the person in ``context``."""
    care, _knowledge = _rules()
    try:
        return _run(chatbot, care.personal_access, context.user_id, typed_id)
    except Exception:
        logger.exception("personal access check failed")
        return None, "I can't check your records right now."


def escalate(chatbot, message, username) -> str:
    care, _knowledge = _rules()
    try:
        result = _run(chatbot, care.open_case, username, message)
    except Exception:
        logger.exception("could not open a support case")
        return ("I couldn't pass this to a member of staff just now. Please contact student "
                "services directly.")
    _send(result.get("emails"))
    return result["reply"]


def wellbeing_text(chatbot) -> str:
    care, _knowledge = _rules()
    try:
        contacts = _run(chatbot, care.university_contacts)
    except Exception:
        contacts = []
    lines = ["Support for your wellbeing:", ""]
    lines += [f"  {label}: {value}" for label, value in contacts]
    lines += ["  Samaritans: 116 123 (free, any time)", "  Shout: text SHOUT to 85258 (24/7)",
              "  NHS 111 (in England choose the mental health option)",
              "  In an emergency call 999.", "",
              "If you'd like a member of staff to get in touch, say 'speak to a person'."]
    return "\n".join(lines)


# ── knowledge ───────────────────────────────────────────────────────────


def import_faqs(chatbot) -> int:
    _care, knowledge = _rules()
    try:
        return _run(chatbot, knowledge.import_json,
                    str(paths.UNIVERSITY_CHATBOT_DATA_DIR / "faq_database.json"))
    except Exception:
        logger.exception("FAQ import failed")
        return 0


def faq(chatbot, query) -> str | None:
    _care, knowledge = _rules()
    try:
        faq_id, answer = _run(chatbot, knowledge.find_answer, query)
    except Exception:
        logger.exception("FAQ lookup failed")
        return None
    chatbot._last_faq_id = faq_id
    return answer


def unanswered(chatbot, question) -> None:
    _care, knowledge = _rules()
    chatbot._last_unanswered = True
    try:
        _run(chatbot, knowledge.record_unanswered, question)
    except Exception:
        logger.exception("could not record an unanswered question")


def log_turn(chatbot, username, message, response, *, intent=None, confidence=None,
             session_id=None) -> int | None:
    _care, knowledge = _rules()
    faq_id = getattr(chatbot, "_last_faq_id", None)
    answered = not getattr(chatbot, "_last_unanswered", False)
    chatbot._last_faq_id, chatbot._last_unanswered = None, False
    try:
        row_id = _run(chatbot, knowledge.log_turn, username, message, response, intent=intent,
                      confidence=confidence, session_id=session_id, faq_id=faq_id,
                      answered=answered)
    except Exception:
        logger.exception("could not log the conversation")
        return None
    chatbot.last_turn_id = row_id
    return row_id


def purge_daily(chatbot) -> int:
    _care, knowledge = _rules()
    try:
        return _run(chatbot, knowledge.purge)
    except Exception:
        logger.exception("chatbot retention purge failed")
        return 0
