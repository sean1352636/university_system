"""Adviser caseloads, team queues, handovers and capacity.

* :func:`my_caseload` — the signed-in adviser's active tickets, most urgent
  SLA first (breached, then soonest due);
* :func:`team_queue` — active tickets of the adviser's teams that nobody
  has yet (admins: any team);
* :func:`take` / :func:`reassign` — pick a ticket up, or hand it to someone
  else with a reason (an internal note and an audit entry; both people are
  told);
* :func:`capacity` / :func:`set_capacity` — open tickets against each
  adviser's ``max_concurrent_tickets``; leads and admins change it.

Every ticket shown passes ``auth.can_view_ticket`` for the person asking.
"""

from __future__ import annotations

import datetime
import logging
from typing import Optional

from education_system.systems.university.domains.student_support.domain.student_support import (
    auth as _auth,
    notify,
    routing,
    schema,
    sla,
    store,
)
from education_system.systems.university.domains.student_support.domain.student_support.utils.audit import (
    log_audit,
)

logger = logging.getLogger(__name__)

MAX_REASON = 1000


def _now() -> str:
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _require_staff(actor) -> dict:
    user = _auth.require_auth(actor)
    if not _auth.is_support_staff(user):
        raise PermissionError("Only support staff have a caseload")
    return user


def _summary(conn, ticket, clock, now) -> dict:
    state = sla.ticket_sla(conn, ticket, now, clock)
    return {
        'ticket_id': ticket['ticket_id'], 'subject': ticket['subject'],
        'category': routing.category_label(ticket['category']),
        'team': ticket['team'], 'team_label': routing.team_label(ticket['team']),
        'priority': ticket['priority'], 'status': ticket['status'],
        'status_label': schema.status_label(ticket['status']),
        'assigned_to': ticket['assigned_to'], 'created_at': ticket['created_at'],
        'confidentiality': ticket['confidentiality'],
        'next_due': state['next_due'], 'hours_left': state['hours_left'],
        'breached': state['first_response_breached'] or state['resolution_breached'],
        'first_response_due': state['first_response_due'],
        'resolution_due': state['resolution_due'],
    }


def _urgency(item) -> tuple:
    hours = item['hours_left']
    return (0 if item['breached'] else 1, hours if hours is not None else float('inf'),
            item['ticket_id'])


def _visible(conn, actor, rows, now=None) -> list:
    now = sla.parse(now) or datetime.datetime.now()
    clock = sla.Clock(conn)
    return [_summary(conn, r, clock, now) for r in rows if _auth.can_view_ticket(actor, r, conn)]


def my_caseload(actor, include_waiting: bool = True, now=None) -> list:
    """The signed-in adviser's active tickets, most urgent first."""
    user = _require_staff(actor)
    statuses = list(schema.ACTIVE_STATUSES)
    if not include_waiting:
        statuses.remove('waiting_on_student')
    marks = ", ".join("?" * len(statuses))
    with store.reading() as conn:
        rows = conn.execute(f"SELECT * FROM support_tickets WHERE assigned_to = ? "  # nosec B608
                            f"AND status IN ({marks})", [user['username']] + statuses).fetchall()
        return sorted(_visible(conn, user, rows, now), key=_urgency)


def team_queue(actor, team=None, now=None) -> list:
    """Unassigned active tickets of ``team`` (default: every team the adviser
    is in; admins see every team's queue)."""
    user = _require_staff(actor)
    marks = ", ".join("?" * len(schema.ACTIVE_STATUSES))
    with store.reading() as conn:
        if team:
            key = routing.team_key(team)
            if not key:
                raise ValueError(f"Unknown team '{team}'")
            if not _auth.is_admin(user) and key not in routing.user_teams(user['username'], conn):
                raise PermissionError(f"You are not a member of {routing.team_label(key)}")
            teams = {key}
        elif _auth.is_admin(user):
            teams = None
        else:
            teams = routing.user_teams(user['username'], conn)
            if not teams:
                return []
        rows = conn.execute(
            f"SELECT * FROM support_tickets WHERE status IN ({marks}) "  # nosec B608
            "AND (assigned_to IS NULL OR assigned_to = '')", schema.ACTIVE_STATUSES).fetchall()
        if teams is not None:
            rows = [r for r in rows
                    if (r['team'] or routing.route(r['category'], r['subcategory'])) in teams]
        return sorted(_visible(conn, user, rows, now), key=_urgency)


def _check_assignee(conn, ticket, username, *, force: bool) -> str:
    row = conn.execute("SELECT username, role FROM users WHERE username = ?",
                       (str(username or '').strip(),)).fetchone()
    if row is None:
        raise ValueError(f"No user '{username}' was found")
    if not _auth.is_support_staff({'username': row[0], 'role': row[1]}):
        raise ValueError(f"{row[0]} is not support staff")
    if not _auth.can_view_ticket({'username': row[0], 'role': row[1]}, ticket, conn):
        raise ValueError(f"{row[0]} cannot see ticket #{ticket['ticket_id']}")
    team = ticket['team'] or routing.route(ticket['category'], ticket['subcategory'])
    members = routing.team_members(team, conn) | routing.duty_officers(conn)
    if members and row[0] not in members and not force:
        raise ValueError(f"{row[0]} is not in {routing.team_label(team)}")
    if not force:
        cap = {c['username']: c for c in routing.capacity(conn, team)}.get(row[0])
        if cap and cap['open'] >= cap['max']:
            raise ValueError(f"{row[0]} is at capacity ({cap['open']} of {cap['max']} tickets)")
    return row[0]


def reassign(actor, ticket_id, new_assignee, reason, *, force: bool = False) -> dict:
    """Hand a ticket to another adviser with a reason (audited, internal note,
    both advisers told). The new adviser must be in the ticket's team and
    under capacity unless ``force`` (admins and team leads only)."""
    user = _require_staff(actor)
    reason = str(reason or '').strip()
    if not reason:
        raise ValueError("Give a reason for the handover")
    if len(reason) > MAX_REASON:
        raise ValueError(f"The reason must be {MAX_REASON} characters or less")
    notices = []
    with store.writing() as conn:
        ticket = conn.execute("SELECT * FROM support_tickets WHERE ticket_id = ?",
                              (int(ticket_id),)).fetchone()
        if ticket is None:
            raise ValueError(f"Ticket #{ticket_id} was not found")
        if not _auth.can_view_ticket(user, ticket, conn):
            raise PermissionError(f"You do not have access to ticket #{ticket['ticket_id']}")
        team = ticket['team'] or routing.route(ticket['category'], ticket['subcategory'])
        if force and not (_auth.is_admin(user) or user['username'] in routing.team_leads(team, conn)):
            raise PermissionError("Only an administrator or the team's lead can override "
                                  "team membership or capacity")
        new = _check_assignee(conn, ticket, new_assignee, force=force)
        old = ticket['assigned_to']
        if old and str(old) == new:
            raise ValueError(f"Ticket #{ticket['ticket_id']} is already with {new}")
        now = _now()
        conn.execute("UPDATE support_tickets SET assigned_to = ?, updated_at = ?, "
                     "last_activity_at = ? WHERE ticket_id = ?", (new, now, now, ticket['ticket_id']))
        me = _auth.current_requester(user, conn)
        conn.execute(
            "INSERT INTO ticket_responses (ticket_id, responder_id, responder_username, "
            "responder_role, response_text, response_datetime, is_internal, is_auto_generated) "
            "VALUES (?, ?, ?, ?, ?, ?, 1, 1)",
            (ticket['ticket_id'], str(me.users_id if me.users_id is not None else me.username),
             me.username, me.role, f"Handed over from {old or 'nobody'} to {new}: {reason}", now))
        log_audit('reassign', resource_id=ticket['ticket_id'], actor=user, conn=conn,
                  old_values={'assigned_to': old}, new_values={'assigned_to': new},
                  details={'reason': reason, 'forced': bool(force)})
        if new != me.username:
            notices += notify.assigned(ticket['ticket_id'], ticket['subject'], new)
        if old and str(old) not in (new, me.username):
            notices.append(notify.Notice(str(old), f"Ticket #{ticket['ticket_id']} handed over",
                                         f"Support ticket #{ticket['ticket_id']} has been handed "
                                         f"over to {new}.", 'handover', ticket['ticket_id']))
        notify.deliver_in_app(conn, notices, sender_username=me.username)
    notify.after_commit(notices)
    return {'old': old, 'new': new}


def take(actor, ticket_id) -> dict:
    """Pick an unassigned ticket up from the team queue."""
    user = _require_staff(actor)
    with store.writing() as conn:
        ticket = conn.execute("SELECT * FROM support_tickets WHERE ticket_id = ?",
                              (int(ticket_id),)).fetchone()
        if ticket is None:
            raise ValueError(f"Ticket #{ticket_id} was not found")
        if not _auth.can_view_ticket(user, ticket, conn):
            raise PermissionError(f"You do not have access to ticket #{ticket['ticket_id']}")
        if ticket['assigned_to']:
            raise ValueError(f"Ticket #{ticket['ticket_id']} is already with {ticket['assigned_to']}")
        now = _now()
        status = schema.normalize_status(ticket['status'], default='open')
        new_status = 'in_progress' if status == 'open' else status
        conn.execute("UPDATE support_tickets SET assigned_to = ?, status = ?, updated_at = ?, "
                     "last_activity_at = ? WHERE ticket_id = ?",
                     (user['username'], new_status, now, now, ticket['ticket_id']))
        log_audit('take', resource_id=ticket['ticket_id'], actor=user, conn=conn,
                  old_values={'assigned_to': None, 'status': status},
                  new_values={'assigned_to': user['username'], 'status': new_status})
    return {'assigned_to': user['username'], 'status': new_status}


def capacity(actor, team=None) -> list:
    """Open tickets against capacity for each adviser (in ``team``, or the
    adviser's own teams; admins: all)."""
    user = _require_staff(actor)
    with store.reading() as conn:
        rows = routing.capacity(conn, team)
        if not _auth.is_admin(user):
            mine = routing.user_teams(user['username'], conn)
            rows = [r for r in rows if r['team'] in mine]
    for r in rows:
        r['team_label'] = routing.team_label(r['team'])
    return rows


def set_capacity(actor, username, max_concurrent, team, *, auto_assign: Optional[bool] = None) -> dict:
    """Change an adviser's capacity in a team (team lead or admin; audited)."""
    return routing.set_member(actor, team, username, max_concurrent=max_concurrent,
                              auto_assign=auto_assign)


__all__ = ['my_caseload', 'team_queue', 'reassign', 'take', 'capacity', 'set_capacity']
