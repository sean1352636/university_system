"""Working a ticket together: links between tickets, time spent, followers.

All three are for the support staff working the ticket (``auth.can_work_ticket``);
a student never sees them.

* **Links** (``ticket_links``) — related, duplicate, blocks, parent/child.
  Stored both ways (:data:`LINK_TYPES` names each type's reverse), so either
  ticket shows the link. Linking needs the right to work *both* tickets; a
  listed link to a ticket the viewer may not see shows its number only.
* **Time** (``ticket_time_tracking``) — minutes spent, with a note;
  ``support_tickets.actual_hours`` is kept as the total. Staff remove their
  own entries; an administrator any.
* **Followers** (``support_ticket_followers``) — staff told (in-app) about a
  ticket's replies, internal notes, status changes and escalation. Following
  never widens access: a follower must be able to see the ticket when added,
  and each notice is checked again (someone who has since lost access, or a
  follower who cannot see internal notes, is not told). The requester is
  never a follower — they are told anyway.

Each change is one transaction with its audit entry and an internal note on
the ticket.
"""

from __future__ import annotations

import datetime
import logging
from typing import Iterable, Optional

from education_system.systems.university.domains.student_support.domain.student_support import (
    auth as _auth,
    confidentiality as _tiers,
    notify,
    store,
)
from education_system.systems.university.domains.student_support.domain.student_support.utils.audit import (
    log_audit,
)

logger = logging.getLogger(__name__)

#: Each link type and the type stored on the other ticket.
LINK_TYPES = {
    'related_to': 'related_to',
    'duplicate_of': 'duplicated_by',
    'duplicated_by': 'duplicate_of',
    'blocks': 'blocked_by',
    'blocked_by': 'blocks',
    'parent_of': 'child_of',
    'child_of': 'parent_of',
}
LINK_LABELS = {
    'related_to': 'Related to',
    'duplicate_of': 'Duplicate of',
    'duplicated_by': 'Duplicated by',
    'blocks': 'Blocks',
    'blocked_by': 'Blocked by',
    'parent_of': 'Parent of',
    'child_of': 'Child of',
}
MAX_MINUTES = 24 * 60


def _now() -> str:
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _ticket(conn, ticket_id):
    try:
        tid = int(ticket_id)
    except (TypeError, ValueError):
        raise ValueError(f"'{ticket_id}' is not a ticket number") from None
    row = conn.execute("SELECT * FROM support_tickets WHERE ticket_id = ?", (tid,)).fetchone()
    if row is None:
        raise ValueError(f"Ticket #{tid} was not found")
    return row


def _worked(conn, user, ticket_id, what):
    """The ticket, if ``user`` works it as staff (else PermissionError)."""
    row = _ticket(conn, ticket_id)
    if not _auth.is_case_worker(user) or not _auth.can_work_ticket(user, row, conn):
        raise PermissionError(f"Only support staff working ticket #{row['ticket_id']} can {what}")
    return row


def _note(conn, ticket_id, text, me) -> None:
    from education_system.systems.university.domains.student_support.domain.student_support import (
        service,
    )
    service._add_auto_note(conn, ticket_id, text, internal=True, who=me)


def _touch(conn, ticket_id) -> None:
    now = _now()
    conn.execute("UPDATE support_tickets SET updated_at = ?, last_activity_at = ? "
                 "WHERE ticket_id = ?", (now, now, ticket_id))


def _account(conn, username) -> Optional[dict]:
    row = conn.execute("SELECT id, username, role FROM users WHERE username = ?",
                       (str(username or '').strip(),)).fetchone()
    return None if row is None else {'id': row['id'], 'username': row['username'],
                                     'role': row['role']}


# ── links ────────────────────────────────────────────────────────────────


def link_type(value) -> str:
    """The stored link type for a type or its label ('Duplicate of' -> 'duplicate_of')."""
    text = str(value or '').strip().lower().replace(' ', '_')
    if text in LINK_TYPES:
        return text
    for key, label in LINK_LABELS.items():
        if label.lower() == str(value or '').strip().lower():
            return key
    raise ValueError("Choose a link type: " + ", ".join(LINK_LABELS.values()))


def link_tickets(actor, ticket_id, other_id, kind='related_to') -> dict:
    """Link two tickets (both ways). Returns ``{'ticket_id', 'other_id',
    'link_type', 'created'}`` — ``created`` False when the link was there."""
    user = _auth.require_auth(actor)
    kind = link_type(kind)
    with store.writing() as conn:
        first = _worked(conn, user, ticket_id, "link tickets")
        second = _worked(conn, user, other_id, "link tickets")
        a, b = first['ticket_id'], second['ticket_id']
        if a == b:
            raise ValueError("A ticket cannot be linked to itself")
        exists = conn.execute("SELECT 1 FROM ticket_links WHERE ticket_id = ? AND "
                              "linked_ticket_id = ? AND link_type = ?", (a, b, kind)).fetchone()
        result = {'ticket_id': a, 'other_id': b, 'link_type': kind, 'created': not exists}
        if exists:
            return result
        me = _auth.current_requester(user, conn)
        now = _now()
        for frm, to, typ in ((a, b, kind), (b, a, LINK_TYPES[kind])):
            if not conn.execute("SELECT 1 FROM ticket_links WHERE ticket_id = ? AND "
                                "linked_ticket_id = ? AND link_type = ?",
                                (frm, to, typ)).fetchone():
                conn.execute("INSERT INTO ticket_links (ticket_id, linked_ticket_id, link_type, "
                             "created_by, created_at) VALUES (?, ?, ?, ?, ?)",
                             (frm, to, typ, me.users_id, now))
            _note(conn, frm, f"Linked: {LINK_LABELS[typ].lower()} ticket #{to}", me)
            _touch(conn, frm)
        log_audit('link_tickets', resource_id=a, actor=user, conn=conn,
                  details={'linked_to': b, 'link_type': kind})
    return result


def unlink_tickets(actor, ticket_id, other_id) -> int:
    """Remove every link between two tickets; returns how many rows went."""
    user = _auth.require_auth(actor)
    with store.writing() as conn:
        row = _worked(conn, user, ticket_id, "unlink tickets")
        a = row['ticket_id']
        try:
            b = int(other_id)
        except (TypeError, ValueError):
            raise ValueError(f"'{other_id}' is not a ticket number") from None
        cur = conn.execute("DELETE FROM ticket_links WHERE (ticket_id = ? AND linked_ticket_id = ?) "
                           "OR (ticket_id = ? AND linked_ticket_id = ?)", (a, b, b, a))
        if cur.rowcount:
            me = _auth.current_requester(user, conn)
            _note(conn, a, f"Link to ticket #{b} removed", me)
            if conn.execute("SELECT 1 FROM support_tickets WHERE ticket_id = ?", (b,)).fetchone():
                _note(conn, b, f"Link to ticket #{a} removed", me)
            log_audit('unlink_tickets', resource_id=a, actor=user, conn=conn,
                      details={'unlinked': b, 'rows': cur.rowcount})
        return cur.rowcount


def list_links(actor, ticket_id) -> list:
    """The ticket's links: ``{'ticket_id', 'link_type', 'label', 'visible',
    'subject', 'status'}`` — subject and status only for tickets ``actor``
    may see."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        schema,
    )
    user = _auth.require_auth(actor)
    out = []
    with store.reading() as conn:
        row = _worked(conn, user, ticket_id, "see a ticket's links")
        for link in conn.execute(
                "SELECT l.linked_ticket_id, l.link_type, l.created_at, t.subject, t.status, "
                "t.ticket_id AS tid, t.requester_username, t.student_id, t.user_id, t.team, "
                "t.category, t.subcategory, t.confidentiality, t.crisis_flag "
                "FROM ticket_links l LEFT JOIN support_tickets t "
                "ON t.ticket_id = l.linked_ticket_id WHERE l.ticket_id = ? "
                "ORDER BY l.created_at, l.link_id", (row['ticket_id'],)).fetchall():
            visible = link['tid'] is not None and _auth.can_view_ticket(
                user, {**dict(link), 'ticket_id': link['tid']}, conn)
            kind = link['link_type'] or 'related_to'
            out.append({'ticket_id': link['linked_ticket_id'], 'link_type': kind,
                        'label': LINK_LABELS.get(kind, kind), 'visible': visible,
                        'subject': link['subject'] if visible else None,
                        'status': schema.status_label(link['status']) if visible else None,
                        'created_at': link['created_at']})
    return out


# ── time ─────────────────────────────────────────────────────────────────


def _total_minutes(conn, ticket_id) -> int:
    return int(conn.execute("SELECT COALESCE(SUM(duration_minutes), 0) FROM ticket_time_tracking "
                            "WHERE ticket_id = ?", (ticket_id,)).fetchone()[0])


def _sync_hours(conn, ticket_id) -> int:
    total = _total_minutes(conn, ticket_id)
    conn.execute("UPDATE support_tickets SET actual_hours = ? WHERE ticket_id = ?",
                 (round(total / 60, 2), ticket_id))
    return total


def log_time(actor, ticket_id, minutes, description='', *, billable=False) -> dict:
    """Record time spent on a ticket. Returns ``{'time_id', 'total_minutes'}``."""
    user = _auth.require_auth(actor)
    try:
        minutes = int(round(float(minutes)))
    except (TypeError, ValueError):
        raise ValueError("Give the time spent in minutes") from None
    if not 1 <= minutes <= MAX_MINUTES:
        raise ValueError(f"Time spent must be between 1 and {MAX_MINUTES} minutes")
    description = str(description or '').strip()[:500]
    with store.writing() as conn:
        row = _worked(conn, user, ticket_id, "log time")
        tid = row['ticket_id']
        me = _auth.current_requester(user, conn)
        end = datetime.datetime.now()
        start = end - datetime.timedelta(minutes=minutes)
        fmt = '%Y-%m-%d %H:%M:%S'
        cur = conn.execute(
            "INSERT INTO ticket_time_tracking (ticket_id, user_id, username, start_time, end_time, "
            "duration_minutes, description, billable, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (tid, me.users_id, me.username, start.strftime(fmt), end.strftime(fmt), minutes,
             description or None, 1 if billable else 0, end.strftime(fmt)))
        total = _sync_hours(conn, tid)
        log_audit('log_time', resource_id=tid, actor=user, conn=conn,
                  details={'minutes': minutes, 'billable': bool(billable)})
        return {'time_id': cur.lastrowid, 'total_minutes': total}


def time_entries(actor, ticket_id) -> dict:
    """``{'entries', 'total_minutes'}`` for a ticket (staff working it)."""
    user = _auth.require_auth(actor)
    with store.reading() as conn:
        row = _worked(conn, user, ticket_id, "see the time logged")
        entries = [dict(r) for r in conn.execute(
            "SELECT tt.time_id, tt.duration_minutes, tt.description, tt.billable, tt.created_at, "
            "COALESCE(tt.username, u.username) AS username FROM ticket_time_tracking tt "
            "LEFT JOIN users u ON u.id = tt.user_id WHERE tt.ticket_id = ? "
            "ORDER BY tt.created_at, tt.time_id", (row['ticket_id'],)).fetchall()]
        return {'entries': entries, 'total_minutes': sum(e['duration_minutes'] or 0
                                                         for e in entries)}


def delete_time_entry(actor, time_id) -> int:
    """Remove a time entry (your own, or any as an administrator); returns
    the ticket's new total in minutes."""
    user = _auth.require_auth(actor)
    with store.writing() as conn:
        entry = conn.execute("SELECT tt.*, u.username AS by_user FROM ticket_time_tracking tt "
                             "LEFT JOIN users u ON u.id = tt.user_id WHERE tt.time_id = ?",
                             (int(time_id),)).fetchone()
        if entry is None:
            raise ValueError(f"Time entry {time_id} was not found")
        _worked(conn, user, entry['ticket_id'], "remove logged time")
        owner = entry['username'] or entry['by_user']
        if owner != user['username'] and not _auth.is_admin(user):
            raise PermissionError("You can only remove time you logged yourself")
        conn.execute("DELETE FROM ticket_time_tracking WHERE time_id = ?", (entry['time_id'],))
        total = _sync_hours(conn, entry['ticket_id'])
        log_audit('delete_time', resource_id=entry['ticket_id'], actor=user, conn=conn,
                  details={'time_id': entry['time_id'], 'minutes': entry['duration_minutes'],
                           'owner': owner})
        return total


# ── followers ────────────────────────────────────────────────────────────


def add_follower(actor, ticket_id, username) -> bool:
    """Make a member of staff a follower (True when newly added). Staff
    working the ticket add anyone who may see it; staff who may see it add
    themselves."""
    user = _auth.require_auth(actor)
    with store.writing() as conn:
        row = _ticket(conn, ticket_id)
        tid = row['ticket_id']
        target = _account(conn, username)
        if target is None:
            raise ValueError(f"No user '{username}' was found")
        self_follow = target['username'] == user['username']
        if self_follow:
            if not _auth.is_case_worker(user) or not _auth.can_view_ticket(user, row, conn):
                raise PermissionError(f"You cannot follow ticket #{tid}")
        elif not _auth.is_case_worker(user) or not _auth.can_work_ticket(user, row, conn):
            raise PermissionError(f"Only support staff working ticket #{tid} can add followers")
        me = _auth.current_requester(user, conn)
        if _auth.owns_ticket(_auth.current_requester(target, conn), row):
            raise ValueError("The person who raised the ticket is told about it already")
        if not _auth.is_case_worker(target) or not _auth.can_view_ticket(target, row, conn):
            raise ValueError(f"{target['username']} cannot see ticket #{tid} (its team or "
                             "confidentiality), so they cannot follow it. Refer or move the "
                             "ticket instead.")
        if conn.execute("SELECT 1 FROM support_ticket_followers WHERE ticket_id = ? AND "
                        "username = ?", (tid, target['username'])).fetchone():
            return False
        conn.execute("INSERT INTO support_ticket_followers (ticket_id, username, added_by, "
                     "added_at) VALUES (?, ?, ?, ?)", (tid, target['username'], me.username, _now()))
        _note(conn, tid, f"{target['username']} is now following this ticket"
              + ("" if self_follow else f" (added by {me.username})"), me)
        log_audit('add_follower', resource_id=tid, actor=user, conn=conn,
                  details={'follower': target['username']})
        notices = [] if self_follow else [notify.Notice(
            target['username'], f"You are following ticket #{tid}",
            f"{me.username} added you as a follower of support ticket #{tid} \"{row['subject']}\". "
            "You will be told about its replies and changes.", 'follow', tid)]
        notify.deliver_in_app(conn, notices, sender_username=me.username)
    notify.after_commit(notices)
    return True


def remove_follower(actor, ticket_id, username) -> bool:
    """Stop someone following (yourself, or anyone if you work the ticket)."""
    user = _auth.require_auth(actor)
    with store.writing() as conn:
        row = _ticket(conn, ticket_id)
        tid = row['ticket_id']
        name = str(username or '').strip()
        if name != user['username'] and not (_auth.is_case_worker(user)
                                             and _auth.can_work_ticket(user, row, conn)):
            raise PermissionError(f"Only support staff working ticket #{tid} can remove followers")
        cur = conn.execute("DELETE FROM support_ticket_followers WHERE ticket_id = ? AND "
                           "username = ?", (tid, name))
        if cur.rowcount:
            me = _auth.current_requester(user, conn)
            _note(conn, tid, f"{name} stopped following this ticket", me)
            log_audit('remove_follower', resource_id=tid, actor=user, conn=conn,
                      details={'follower': name})
        return bool(cur.rowcount)


def list_followers(actor, ticket_id) -> list:
    """``[{'username', 'added_by', 'added_at'}]`` (staff who may see the ticket)."""
    user = _auth.require_auth(actor)
    with store.reading() as conn:
        row = _ticket(conn, ticket_id)
        if not _auth.is_case_worker(user) or not _auth.can_view_ticket(user, row, conn):
            raise PermissionError(f"You do not have access to ticket #{row['ticket_id']}")
        return [dict(r) for r in conn.execute(
            "SELECT username, added_by, added_at FROM support_ticket_followers "
            "WHERE ticket_id = ? ORDER BY added_at, username", (row['ticket_id'],)).fetchall()]


def followed_tickets(actor) -> list:
    """The tickets the signed-in person follows and can still see."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        schema,
    )
    user = _auth.require_auth(actor)
    out = []
    with store.reading() as conn:
        for row in conn.execute(
                "SELECT t.* FROM support_ticket_followers f JOIN support_tickets t "
                "ON t.ticket_id = f.ticket_id WHERE f.username = ? ORDER BY t.ticket_id DESC",
                (user['username'],)).fetchall():
            if _auth.can_view_ticket(user, row, conn):
                out.append({'ticket_id': row['ticket_id'], 'subject': row['subject'],
                            'status': schema.status_label(row['status']),
                            'priority': row['priority'], 'assigned_to': row['assigned_to'],
                            'updated_at': row['updated_at']})
    return out


def follower_notices(conn, ticket, subject: str, body: str, *, internal=False,
                     exclude: Iterable[Optional[str]] = ()) -> list:
    """Notices for a ticket's followers about one change (on ``conn``, read
    only). Each follower is checked again: one who can no longer see the
    ticket — or, for an internal note, cannot see internal notes — is left
    out, as is anyone in ``exclude`` (the person acting, people already told)."""
    tid = ticket['ticket_id']
    try:
        names = [r[0] for r in conn.execute("SELECT username FROM support_ticket_followers "
                                            "WHERE ticket_id = ?", (tid,)).fetchall()]
    except Exception:
        logger.debug("No followers table yet", exc_info=True)
        return []
    skip = {str(x) for x in exclude if x}
    out = []
    for name in names:
        if name in skip:
            continue
        who = _account(conn, name)
        if who is None:
            continue
        allowed = (_auth.can_work_ticket(who, ticket, conn) if internal
                   else _auth.can_view_ticket(who, ticket, conn))
        if allowed:
            out.append(notify.Notice(name, subject, body, 'follow', tid))
    return out


__all__ = [
    'LINK_TYPES', 'LINK_LABELS', 'link_type', 'link_tickets', 'unlink_tickets', 'list_links',
    'log_time', 'time_entries', 'delete_time_entry', 'add_follower', 'remove_follower',
    'list_followers', 'followed_tickets', 'follower_notices',
]
