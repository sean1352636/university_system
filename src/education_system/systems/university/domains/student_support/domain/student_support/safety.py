"""Crisis language on a support ticket.

The words the university chatbot treats as a crisis (``application/
chatbot_care.is_crisis`` — suicide, self-harm, being in danger) are checked
in every new ticket and in every reply from the person who raised it. On a
hit the service:

* makes the ticket a safeguarding-tier ticket (``crisis_flag`` 1, priority
  critical, team wellbeing; its text sealed) inside the same transaction;
* hands the caller :func:`crisis_support` — the same immediate reply the
  chatbot gives, with real UK contacts (999, Samaritans, Shout, NHS 111) and
  the university's own contacts from the chatbot settings — so the screen
  shows them at once, before anyone has read the ticket;
* after the commit, raises one CRITICAL safeguarding concern for the ticket
  (:func:`raise_concern`, through ``services/bus/support_referrals_bus``) and
  records its reference on the ticket as a safeguarding referral
  (``support_ticket_referrals``) with an internal note. A ticket raises one
  concern; later crisis replies are noted on the ticket against it.
"""

from __future__ import annotations

import logging
from typing import Optional

from education_system.systems.university.domains.student_support.domain.student_support import (
    store,
)

logger = logging.getLogger(__name__)

TEAM = 'wellbeing'
PRIORITY = {'support': 'Critical', 'helpdesk': 'critical'}


def detect(*texts) -> bool:
    """Is there crisis language in any of ``texts``?"""
    from education_system.systems.university.application.chatbot import care as chatbot_care
    return chatbot_care.is_crisis("\n".join(str(t or '') for t in texts))


def crisis_support(conn) -> dict:
    """What to show the person straight away: ``{'message', 'lines',
    'safeguarding_reference'}`` (the reference is filled in after the commit)."""
    from education_system.systems.university.application.chatbot import care as chatbot_care
    message = chatbot_care.crisis_reply(conn)
    return {'message': message, 'lines': [line for line in message.splitlines() if line],
            'safeguarding_reference': None}


def _subject(conn, ticket) -> dict:
    ref = ticket['requester_username'] or ticket['student_id']
    row = conn.execute(
        "SELECT username, TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, '')), "
        "role FROM users WHERE username = ? OR student_id = ? ORDER BY id LIMIT 1",
        (ref, ref)).fetchone()
    if row is None:
        return {'username': str(ref or ''), 'full_name': str(ref or ''), 'role': 'student'}
    return {'username': row[0], 'full_name': row[1] or row[0], 'role': row[2] or 'student'}


def raise_concern(ticket_id, text, *, where, actor_username) -> Optional[str]:
    """After the commit: raise the ticket's safeguarding concern (once) and
    record it on the ticket. Returns the concern's reference, or None when it
    could not be raised (then an internal note tells the team to raise it by
    hand). Never raises."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        referrals,
    )
    try:
        with store.writing() as conn:
            existing = referrals.safeguarding_reference(conn, ticket_id)
            if existing:
                referrals.note(conn, ticket_id, f"Further crisis language ({where}); safeguarding "
                               f"concern {existing} was already raised for this ticket.")
                return existing
            ticket = conn.execute("SELECT * FROM support_tickets WHERE ticket_id = ?",
                                  (ticket_id,)).fetchone()
            subject = _subject(conn, ticket)
            referral_id = referrals.start(conn, ticket_id, 'safeguarding', actor_username,
                                          'duty_of_care')
    except Exception:
        logger.exception("Could not record the safeguarding referral for ticket %s", ticket_id)
        return None
    from education_system.systems.university.services.bus import support_referrals_bus
    content = (f"Raised automatically by Student Support: crisis language in support ticket "
               f"#{ticket_id} ({where}).\n\nText:\n{text}")
    try:
        sid = support_referrals_bus.raise_safeguarding_concern(
            subject, content, snippet=str(text or ''), reporter_username=actor_username)
    except Exception as exc:
        logger.exception("Safeguarding concern for ticket %s could not be raised", ticket_id)
        referrals.finish(referral_id, error=str(exc))
        return None
    reference = str(sid)
    referrals.finish(referral_id, target_ref=reference)
    return reference


__all__ = ['TEAM', 'PRIORITY', 'detect', 'crisis_support', 'raise_concern']
