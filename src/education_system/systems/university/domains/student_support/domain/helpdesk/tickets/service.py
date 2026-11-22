"""Helpdesk tickets on the one ticket model.

The Helpdesk and Student Support share ``support_tickets``; every write goes
through the Student Support ticket service (``student_support.service``),
which fills the canonical columns (requester_username, student_id, source,
channel, the lower-case status vocabulary) and checks permissions. This
module adds what is Helpdesk-specific: the team and department from the
category (``student_support.routing`` — Helpdesk categories go to IT
Services, Academic Registry or Fees & Funding), the assignee (the
least-loaded free member of that team, else the department's manager) and
``due_date`` = the SLA resolution time on the business-hours clock
(``student_support.sla``; the ticket service then sets ``sla_due_at``).

Functions take the signed-in user first (an auth object or its
``current_user`` dict) and raise PermissionError / ValueError with messages
fit to show the user.
"""

from __future__ import annotations

import logging
from datetime import datetime

from education_system.systems.university.domains.student_support.domain.student_support import (
    routing,
    schema,
    service as _support,
    sla,
    store,
)

logger = logging.getLogger(__name__)

STATUSES = schema.STATUSES
STATUS_LABELS = schema.STATUS_LABELS
normalize_status = schema.normalize_status

CATEGORY_DEPARTMENTS = {
    "Technical Support": "IT Support",
    "Academic Inquiry": "Academic Affairs",
    "Financial Services": "Financial Services",
    "Account Access": "IT Support",
}


def _sla_due(conn, priority, impact=None, urgency=None, team=None):
    """The resolution due time for a new ticket of ``team`` / ``priority``
    (``impact`` / ``urgency`` are kept for older callers; the targets are
    per team and priority)."""
    t = sla.targets(conn, team, priority)
    due = sla.Clock(conn).add(datetime.now(), t['resolution_hours'], t['business_hours_only'])
    return due.strftime('%Y-%m-%d %H:%M:%S')


def _department_manager(conn, department):
    row = conn.execute('''
        SELECT u.username FROM departments d JOIN users u ON u.id = d.manager_id
        WHERE d.name = ? AND COALESCE(d.is_active, 1) = 1''', (department,)).fetchone()
    return row[0] if row else None


def submit_helpdesk_ticket(actor, *, subject, description, category, priority='medium',
                           impact='low', urgency='low', subcategory=None, channel='web',
                           requester=None, attachments=None, confidentiality=None) -> dict:
    """Raise a Helpdesk ticket. Returns ``{'ticket_id', 'team',
    'confidentiality', 'crisis'}`` as ``student_support.service.submit_ticket``
    does — show ``crisis`` (the crisis contacts) at once when it is set.

    The category's team and department are recorded; the team's least-loaded
    free member gets the ticket (else the department's manager); the team /
    priority SLA sets ``due_date``.
    """
    team = routing.route(category, subcategory)
    with store.reading() as conn:
        dept = routing.team_department(team, conn)
        department = (dept or {}).get('name') or CATEGORY_DEPARTMENTS.get(str(category or '').strip())
        due = _sla_due(conn, priority, impact, urgency, team=team)
        assignee = routing.pick_assignee(team, conn)
        if assignee is None and department:
            has_departments = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' "
                                           "AND name = 'departments'").fetchone()
            assignee = _department_manager(conn, department) if has_departments else None
    return _support.submit_ticket(
        actor, subject=subject, description=description, category=category,
        priority=priority, requester=requester, source='helpdesk', channel=channel,
        attachments=attachments, subcategory=subcategory, impact=impact, urgency=urgency,
        department=department, due_date=due, assigned_to=assignee, team=team,
        confidentiality=confidentiality)


def create_helpdesk_ticket(actor, **fields) -> int:
    """Raise a Helpdesk ticket; returns its number (:func:`submit_helpdesk_ticket`
    for the crisis support and tier too). Takes the same keyword arguments."""
    return submit_helpdesk_ticket(actor, **fields)['ticket_id']


def list_tickets(actor, filters=None, page=1, per_page=50) -> dict:
    """Every ticket (Helpdesk and Student Support alike) for support staff."""
    return _support.list_tickets(actor, filters, page, per_page)


def list_my_tickets(actor, filters=None, page=1, per_page=50) -> dict:
    """The tickets the signed-in person raised, from either front-end."""
    return _support.list_my_tickets(actor, filters, page, per_page)


def iter_tickets(actor, filters=None, mine=False):
    """Every ticket ``actor`` may see (``mine``: only those they raised),
    page by page — for exports and reports that need the whole set. Sealed
    text is the service's placeholder, as in :func:`list_tickets`."""
    lister = _support.list_my_tickets if mine else _support.list_tickets
    page = 1
    while True:
        result = lister(actor, filters, page, 500)
        yield from result['tickets']
        if page >= result['total_pages']:
            return
        page += 1


# Columns a count may be grouped by (fixed: never caller text in the SQL).
COUNT_GROUPS = {
    'status': schema.status_case_sql('status'),
    'priority': "lower(COALESCE(priority, ''))",
    'category': "COALESCE(category, '')",
    'team': "COALESCE(team, '')",
    'source': "COALESCE(source, '')",
    'department': "COALESCE(department, '')",
    'assigned_to': "COALESCE(assigned_to, '')",
    'confidentiality': "COALESCE(confidentiality, 'standard')",
    'day': "date(created_at)",
    'month': "strftime('%Y-%m', created_at)",
}


def ticket_counts(actor, by=None, filters=None, mine=False):
    """How many tickets ``actor`` may see — no ticket text, counts only.

    ``by`` (a key of :data:`COUNT_GROUPS`) gives ``{value: count}``; without
    it the total. ``filters`` as :func:`list_tickets`; ``mine`` counts only
    the tickets ``actor`` raised (anyone may); otherwise support staff only.
    """
    if by is not None and by not in COUNT_GROUPS:
        raise ValueError(f"Cannot count tickets by '{by}'")
    from education_system.systems.university.domains.student_support.domain.student_support import (
        auth as _auth,
    )
    if not mine and not _auth.is_case_worker(actor):
        raise PermissionError("Only support staff can see ticket figures")
    with store.reading() as conn:
        if mine:
            me = _auth.current_requester(actor, conn)
            if me.student_id:
                where = ("(requester_username = ? OR (requester_username IS NULL AND "
                         "(student_id = ? OR user_id = ?)))")
                params = [me.username, me.student_id, me.student_id]
            else:
                where, params = "requester_username = ?", [me.username]
        else:
            where, params = _auth.ticket_scope_sql(actor, conn=conn)
        fsql, fparams = _support._filter_sql(filters)
        base = f"FROM support_tickets WHERE {where}{fsql}"  # nosec B608 - fixed fragments
        if by is None:
            return conn.execute(f"SELECT COUNT(*) {base}",  # nosec B608
                                params + fparams).fetchone()[0]
        expr = COUNT_GROUPS[by]
        rows = conn.execute(f"SELECT {expr} AS k, COUNT(*) AS n {base} "  # nosec B608
                            "GROUP BY k ORDER BY n DESC", params + fparams).fetchall()
        return {r['k']: r['n'] for r in rows}


def sla_status(ticket) -> dict:
    """Where ``ticket`` (a dict from :func:`get_ticket` / a list) stands
    against its SLA — ``student_support.sla.ticket_sla`` plus ``'label'``
    ('Met', 'Breached', 'Due in 3.5h', 'Overdue by 2h', ...)."""
    with store.reading() as conn:
        info = sla.ticket_sla(conn, ticket)
    if info['resolution_met'] is not None:
        label = 'Met' if info['resolution_met'] else 'Breached'
    elif info['hours_left'] is None:
        label = '-'
    elif info['hours_left'] < 0:
        label = f"Overdue by {abs(info['hours_left']):.1f}h"
    else:
        label = f"Due in {info['hours_left']:.1f}h"
    if info.get('paused'):
        label += " (paused: waiting on student)"
    info['label'] = label
    return info


def delete_attachment(actor, ticket_id, attachment_id) -> None:
    """Delete an attachment of ``ticket_id``: support staff working the
    ticket only; audited; the file is removed after the commit."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        auth as _auth,
        gdpr,
    )
    from education_system.systems.university.domains.student_support.domain.student_support.utils.audit import (
        log_audit,
    )
    _auth.require_auth(actor)
    with store.writing() as conn:
        att = conn.execute("SELECT attachment_id, ticket_id, file_path, original_filename "
                           "FROM ticket_attachments WHERE attachment_id = ?",
                           (attachment_id,)).fetchone()
        if att is None or int(att['ticket_id']) != int(ticket_id):
            raise ValueError(f"Attachment {attachment_id} was not found on ticket #{ticket_id}")
        ticket = conn.execute("SELECT * FROM support_tickets WHERE ticket_id = ?",
                              (att['ticket_id'],)).fetchone()
        if ticket is None or not _auth.can_work_ticket(actor, ticket, conn):
            raise PermissionError("Only support staff working this ticket can delete its attachments")
        conn.execute("DELETE FROM ticket_attachments WHERE attachment_id = ?", (attachment_id,))
        log_audit('delete_attachment', resource_id=att['ticket_id'], actor=actor, conn=conn,
                  details={'attachment_id': att['attachment_id'], 'file': att['original_filename']})
    if att['file_path']:
        gdpr.delete_files([att['file_path']])


get_ticket = _support.get_ticket
post_reply = _support.post_response
add_reply = _support.add_response
set_status = _support.set_status
assign = _support.assign
escalate = _support.escalate

__all__ = [
    'STATUSES', 'STATUS_LABELS', 'normalize_status', 'CATEGORY_DEPARTMENTS',
    'create_helpdesk_ticket', 'submit_helpdesk_ticket', 'list_tickets', 'list_my_tickets',
    'iter_tickets', 'ticket_counts', 'COUNT_GROUPS', 'sla_status', 'get_ticket', 'add_reply',
    'post_reply', 'delete_attachment',
    'set_status', 'assign', 'escalate',
]
