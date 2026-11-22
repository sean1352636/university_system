"""The requester's consent to their ticket being shared.

``support_tickets.share_consent`` is NULL (not asked), ``'granted'`` or
``'declined'``, with ``share_consent_at``. Only the person who raised the
ticket — the data subject — records it, on their own ticket, and may change
their mind (a later answer replaces the earlier one; each is audited and noted
on the ticket).

It gates referrals (``referrals.consent_basis``): a restricted or safeguarding
ticket is referred to another service only with consent granted, except a
safeguarding referral and an Early Warning referral of a crisis ticket (duty
of care); a declined ticket is never referred except to safeguarding.

:func:`consent_state` tells the screen when to ask: the requester looking at
their own confidential ticket that has no answer yet.
"""

from __future__ import annotations

import datetime

from education_system.systems.university.domains.student_support.domain.student_support import (
    auth as _auth,
    confidentiality as _tiers,
    store,
)
from education_system.systems.university.domains.student_support.domain.student_support.utils.audit import (
    log_audit,
)

QUESTION = ("Your request is confidential. May the support team share it with other "
            "university services (for example wellbeing, disability, finance or your school) "
            "when that would help you? You can change your answer at any time. If you are at "
            "risk of serious harm we may still share it to keep you safe.")


def _now() -> str:
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _own_ticket(conn, user, ticket_id):
    row = conn.execute("SELECT * FROM support_tickets WHERE ticket_id = ?",
                       (int(ticket_id),)).fetchone()
    if row is None:
        raise ValueError(f"Ticket #{ticket_id} was not found")
    if _tiers.access_basis(user, row, conn) != 'owner':
        raise PermissionError("Only the person who raised the ticket can answer this")
    return row


def needs_prompt(ticket) -> bool:
    """Should the requester be asked? (A confidential ticket, no answer yet.)"""
    return _tiers.is_sealed_tier(_tiers.tier_of(ticket)) and not ticket['share_consent']


def consent_state(actor, ticket_id) -> dict:
    """``{'share_consent', 'share_consent_at', 'prompt', 'question', 'tier'}``
    for the requester's own ticket (``prompt`` True: ask them now)."""
    user = _auth.require_auth(actor)
    with store.reading() as conn:
        row = _own_ticket(conn, user, ticket_id)
    return {'ticket_id': row['ticket_id'], 'share_consent': row['share_consent'],
            'share_consent_at': row['share_consent_at'], 'prompt': needs_prompt(row),
            'question': QUESTION, 'tier': _tiers.tier_of(row)}


def record_share_consent(actor, ticket_id, granted: bool) -> dict:
    """The requester grants (``True``) or declines (``False``) sharing of
    their ticket. Returns ``{'old', 'new', 'at'}``."""
    user = _auth.require_auth(actor)
    new = 'granted' if granted else 'declined'
    with store.writing() as conn:
        row = _own_ticket(conn, user, ticket_id)
        old = row['share_consent']
        at = _now()
        conn.execute("UPDATE support_tickets SET share_consent = ?, share_consent_at = ?, "
                     "updated_at = ? WHERE ticket_id = ?", (new, at, at, row['ticket_id']))
        me = _auth.current_requester(user, conn)
        text = ("You agreed to this ticket being shared with other university services."
                if granted else
                "You asked for this ticket not to be shared with other university services.")
        conn.execute('''
        INSERT INTO ticket_responses (ticket_id, responder_id, responder_username, responder_role,
                                      response_text, response_datetime, is_internal,
                                      is_auto_generated)
        VALUES (?, ?, ?, ?, ?, ?, 0, 1)''', (row['ticket_id'], str(me.users_id or me.username),
                                            me.username, me.role, text, at))
        log_audit('share_consent', resource_id=row['ticket_id'], actor=user, conn=conn,
                  old_values={'share_consent': old}, new_values={'share_consent': new})
    return {'old': old, 'new': new, 'at': at}


__all__ = ['QUESTION', 'needs_prompt', 'consent_state', 'record_share_consent']
