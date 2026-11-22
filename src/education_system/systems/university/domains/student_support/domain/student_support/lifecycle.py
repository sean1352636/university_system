"""Closing resolved tickets that nobody came back to.

A resolved ticket stays open to the requester: their reply brings it back
into work (``service.post_response``). Once it has been resolved for
``auto_close_days`` (setting, default 7; 0 turns this off) with no activity
since, :func:`close_stale_resolved` closes it — the same status change staff
make (``service._change_status``: closed_at, an entry on the ticket, the
audit row, the requester told, the satisfaction survey if they have not
rated it yet). After that the requester opens a new ticket instead of
replying.

Run by the support jobs worker every hour; safe to run again (a closed
ticket is never picked up twice).
"""

from __future__ import annotations

import datetime
import logging

from education_system.systems.university.domains.student_support.domain.student_support import (
    auth as _auth,
    notify,
    settings,
    store,
)

logger = logging.getLogger(__name__)

SYSTEM_USER = {'username': 'system', 'role': 'system'}
BATCH = 200


def _system_requester():
    return _auth.Requester(username='system', role='system', users_id=None, student_id=None)


def _cutoff(days: int, now: datetime.datetime) -> str:
    return (now - datetime.timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')


def due_for_close(conn, days: int, now=None) -> list:
    """Resolved tickets with no activity for ``days`` days (oldest first)."""
    now = now or datetime.datetime.now()
    cutoff = _cutoff(days, now)
    return conn.execute(
        "SELECT * FROM support_tickets WHERE status = 'resolved' "
        "AND COALESCE(resolved_at, updated_at, created_at) <= ? "
        "AND COALESCE(last_activity_at, updated_at, resolved_at, created_at) <= ? "
        "AND data_purged_at IS NULL ORDER BY resolved_at, ticket_id LIMIT ?",
        (cutoff, cutoff, BATCH)).fetchall()


def close_stale_resolved(now=None, days=None) -> int:
    """Close every resolved ticket left alone for the auto-close period;
    returns how many were closed."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        service,
    )
    now = now or datetime.datetime.now()
    with store.reading() as conn:
        days = settings.get('auto_close_days', conn) if days is None else int(days)
    if days <= 0:
        return 0
    closed, notices = 0, []
    me = _system_requester()
    note = (f"Closed automatically: resolved {days} day{'s' if days != 1 else ''} ago with no "
            "reply. If you still need help, please open a new ticket.")
    with store.writing() as conn:
        for ticket in due_for_close(conn, days, now):
            result, ticket_notices = service._change_status(conn, SYSTEM_USER, me, ticket,
                                                            'closed')
            if not result['changed']:
                continue
            service._add_auto_note(conn, ticket['ticket_id'], note)
            notices += ticket_notices
            closed += 1
        notify.deliver_in_app(conn, notices)
    notify.after_commit(notices)
    if closed:
        logger.info("Auto-closed %s resolved support ticket(s) after %s days", closed, days)
    return closed


__all__ = ['close_stale_resolved', 'due_for_close']
