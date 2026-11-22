"""Major incidents: one problem, many tickets.

When something breaks for many people at once (the Wi-Fi, the VLE, a fees
run), support staff declare an incident (``support_incidents``) and attach
the tickets it caused (``support_tickets.incident_id``). From then on the
incident is worked once:

* :func:`post_update` puts the same public reply on every open ticket of the
  incident (each requester told as for any staff reply) and becomes the
  incident's public message;
* :func:`resolve` resolves every open ticket of the incident with the
  resolution — the ordinary status change, so each requester is told and
  asked to rate the help.

People who have not raised a ticket see the open incidents' title and
public message as known issues (:func:`known_issues`, shown before a new
ticket is raised) and can say they are affected (:func:`report_affected`),
which raises their ticket already attached. The title and public message
are therefore written for everyone to read.

Crisis and safeguarding tickets are never attached: each is handled on its
own. Declaring and working an incident is for support staff; attaching a
ticket needs the right to work that ticket.
"""

from __future__ import annotations

import datetime
import logging
from typing import Iterable, Optional

from education_system.systems.university.domains.student_support.domain.student_support import (
    auth as _auth,
    confidentiality as _tiers,
    notify,
    schema,
    store,
)
from education_system.systems.university.domains.student_support.domain.student_support.utils.audit import (
    log_audit,
)

logger = logging.getLogger(__name__)

STATUSES = ('open', 'monitoring', 'resolved')
STATUS_LABELS = {'open': 'Open', 'monitoring': 'Monitoring', 'resolved': 'Resolved'}
SEVERITIES = ('minor', 'major', 'critical')
MAX_TITLE = 200
MAX_TEXT = 5000


def _now() -> str:
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _service():
    from education_system.systems.university.domains.student_support.domain.student_support import (
        service,
    )
    return service


def _text(value, label, limit, required=True) -> str:
    text = str(value or '').strip()
    if required and not text:
        raise ValueError(f"{label} is required")
    if len(text) > limit:
        raise ValueError(f"{label} must be {limit} characters or less")
    return text


def _require_staff(actor) -> dict:
    user = _auth.require_auth(actor)
    if not _auth.is_case_worker(user):
        raise PermissionError("Only support staff can manage incidents")
    return user


def _incident(conn, incident_id):
    try:
        iid = int(incident_id)
    except (TypeError, ValueError):
        raise ValueError(f"'{incident_id}' is not an incident number") from None
    row = conn.execute("SELECT * FROM support_incidents WHERE incident_id = ?", (iid,)).fetchone()
    if row is None:
        raise ValueError(f"Incident #{iid} was not found")
    return row


def _ids(values) -> list:
    out = []
    for value in values or []:
        try:
            out.append(int(str(value).strip().lstrip('#')))
        except (TypeError, ValueError):
            raise ValueError(f"'{value}' is not a ticket number") from None
    return list(dict.fromkeys(out))


def _team(team) -> Optional[str]:
    if not team:
        return None
    from education_system.systems.university.domains.student_support.domain.student_support import (
        routing,
    )
    key = routing.team_key(team)
    if not key:
        raise ValueError(f"Unknown team '{team}'")
    return key


def _active_tickets(conn, incident_id) -> list:
    marks = ", ".join("?" * len(schema.ACTIVE_STATUSES))
    return conn.execute(
        f"SELECT * FROM support_tickets WHERE incident_id = ? AND status IN ({marks}) "  # nosec B608
        "ORDER BY ticket_id", [int(incident_id), *schema.ACTIVE_STATUSES]).fetchall()


def _attach_row(conn, incident, ticket, me) -> list:
    """Attach one ticket on ``conn``; returns the requester's notices."""
    service = _service()
    tid = ticket['ticket_id']
    if ticket['crisis_flag'] or _tiers.tier_of(ticket) == _tiers.SAFEGUARDING:
        raise ValueError(f"Ticket #{tid} is a safeguarding ticket and is handled on its own, "
                         "not as part of an incident")
    if schema.normalize_status(ticket['status'], default='open') == 'closed':
        raise ValueError(f"Ticket #{tid} is closed")
    current = ticket['incident_id']
    if current and int(current) != incident['incident_id']:
        raise ValueError(f"Ticket #{tid} is already part of incident #{current}")
    if current:
        return []
    now = _now()
    conn.execute("UPDATE support_tickets SET incident_id = ?, updated_at = ?, last_activity_at = ? "
                 "WHERE ticket_id = ?", (incident['incident_id'], now, now, tid))
    text = (f"This request is part of a known issue we are working on: {incident['title']}.")
    if incident['public_message']:
        text += f"\n\n{incident['public_message']}"
    text += "\n\nWe will update you here and close this request when it is fixed."
    service._add_auto_note(conn, tid, text, who=me)
    service._add_auto_note(conn, tid, f"Attached to incident #{incident['incident_id']}",
                           internal=True, who=me)
    return [notify.Notice(
        service._requester_ref(ticket), f"Support ticket #{tid}: known issue",
        f"Your support ticket #{tid} \"{ticket['subject']}\" is part of a known issue we are "
        f"working on: {incident['title']}. We will update you on the ticket.", 'incident', tid)]


# ── declare and attach ──────────────────────────────────────────────────


def declare(actor, title, description='', *, public_message='', team=None, severity='major',
            ticket_ids: Iterable = ()) -> dict:
    """Declare an incident, attaching ``ticket_ids`` if given. Returns
    ``{'incident_id', 'attached', 'skipped'}``."""
    user = _require_staff(actor)
    title = _text(title, "A title", MAX_TITLE)
    description = _text(description, "The description", MAX_TEXT, required=False)
    public_message = _text(public_message, "The public message", MAX_TEXT, required=False)
    severity = str(severity or 'major').strip().lower()
    if severity not in SEVERITIES:
        raise ValueError("Severity must be minor, major or critical")
    team = _team(team)
    with store.writing() as conn:
        now = _now()
        cur = conn.execute(
            "INSERT INTO support_incidents (title, description, public_message, team, severity, "
            "status, created_by, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'open', ?, ?, ?)",
            (title, description or None, public_message or None, team, severity,
             user['username'], now, now))
        iid = cur.lastrowid
        log_audit('declare_incident', resource_type='support_incident', resource_id=iid,
                  actor=user, conn=conn, details={'title': title, 'team': team,
                                                  'severity': severity})
    result = {'incident_id': iid, 'attached': 0, 'skipped': {}}
    if ticket_ids:
        attached = attach(user, iid, ticket_ids)
        result.update(attached)
    return result


def attach(actor, incident_id, ticket_ids) -> dict:
    """Attach tickets to an open incident. Each ticket you may not work, a
    safeguarding ticket or a closed one is skipped with the reason. Returns
    ``{'attached', 'skipped': {ticket_id: reason}}``."""
    user = _require_staff(actor)
    ids = _ids(ticket_ids)
    if not ids:
        raise ValueError("Choose at least one ticket")
    attached, skipped, notices = 0, {}, []
    with store.writing() as conn:
        incident = _incident(conn, incident_id)
        if incident['status'] == 'resolved':
            raise ValueError(f"Incident #{incident['incident_id']} is resolved")
        me = _auth.current_requester(user, conn)
        for tid in ids:
            ticket = conn.execute("SELECT * FROM support_tickets WHERE ticket_id = ?",
                                  (tid,)).fetchone()
            if ticket is None:
                skipped[tid] = "not found"
                continue
            if not _auth.can_work_ticket(user, ticket, conn):
                skipped[tid] = "you are not working this ticket"
                continue
            conn.execute("SAVEPOINT incident_attach")
            try:
                ticket_notices = _attach_row(conn, incident, ticket, me)
                conn.execute("RELEASE SAVEPOINT incident_attach")
            except ValueError as exc:
                conn.execute("ROLLBACK TO SAVEPOINT incident_attach")
                conn.execute("RELEASE SAVEPOINT incident_attach")
                skipped[tid] = str(exc)
                continue
            if ticket_notices:
                attached += 1
                notices += ticket_notices
        conn.execute("UPDATE support_incidents SET updated_at = ? WHERE incident_id = ?",
                     (_now(), incident['incident_id']))
        log_audit('attach_incident', resource_type='support_incident',
                  resource_id=incident['incident_id'], actor=user, conn=conn,
                  details={'attached': attached, 'skipped': sorted(skipped)})
        notify.deliver_in_app(conn, notices, sender_username=me.username)
    notify.after_commit(notices)
    return {'attached': attached, 'skipped': skipped}


def detach(actor, incident_id, ticket_id) -> bool:
    """Take a ticket out of an incident (it carries on as an ordinary ticket)."""
    user = _require_staff(actor)
    with store.writing() as conn:
        incident = _incident(conn, incident_id)
        ticket = conn.execute("SELECT * FROM support_tickets WHERE ticket_id = ? AND "
                              "incident_id = ?", (int(ticket_id), incident['incident_id'])).fetchone()
        if ticket is None:
            return False
        if not _auth.can_work_ticket(user, ticket, conn):
            raise PermissionError(f"Only support staff working ticket #{ticket_id} can detach it")
        conn.execute("UPDATE support_tickets SET incident_id = NULL WHERE ticket_id = ?",
                     (ticket['ticket_id'],))
        _service()._add_auto_note(conn, ticket['ticket_id'],
                                  f"Detached from incident #{incident['incident_id']}",
                                  internal=True, who=_auth.current_requester(user, conn))
        log_audit('detach_incident', resource_type='support_incident',
                  resource_id=incident['incident_id'], actor=user, conn=conn,
                  details={'ticket_id': ticket['ticket_id']})
        return True


# ── work the incident ───────────────────────────────────────────────────


def _public_reply(conn, ticket, text, me, now) -> None:
    """A staff public reply on ``conn`` (as ``service.post_response`` makes
    it: the first response is recorded and an open ticket goes into work)."""
    service = _service()
    tid = ticket['ticket_id']
    conn.execute(
        "INSERT INTO ticket_responses (ticket_id, responder_id, responder_username, "
        "responder_role, response_text, response_datetime, is_internal) "
        "VALUES (?, ?, ?, ?, ?, ?, 0)",
        (tid, str(me.users_id if me.users_id is not None else me.username), me.username,
         me.role, _tiers.seal('ticket_responses', 'response_text', text, _tiers.tier_of(ticket)),
         now))
    status = schema.normalize_status(ticket['status'], default='open')
    new_status = 'in_progress' if status == 'open' else status
    conn.execute("UPDATE support_tickets SET status = ?, assigned_to = COALESCE(assigned_to, ?), "
                 "first_response_at = COALESCE(first_response_at, ?), updated_at = ?, "
                 "last_activity_at = ? WHERE ticket_id = ?",
                 (new_status, me.username, now, now, now, tid))
    if not ticket['first_response_at']:
        sla = service._optional('sla')
        if sla is not None:
            sla.on_first_response(conn, tid)
    service._sync_pause(conn, tid)


def post_update(actor, incident_id, message) -> int:
    """Post the same public update on every open ticket of the incident (it
    becomes the public message too); returns how many tickets got it."""
    user = _require_staff(actor)
    message = _text(message, "The update", MAX_TEXT)
    service = _service()
    notices, count = [], 0
    with store.writing() as conn:
        incident = _incident(conn, incident_id)
        if incident['status'] == 'resolved':
            raise ValueError(f"Incident #{incident['incident_id']} is resolved")
        me = _auth.current_requester(user, conn)
        now = _now()
        text = f"Update on the known issue \"{incident['title']}\":\n\n{message}"
        for ticket in _active_tickets(conn, incident['incident_id']):
            if not _auth.can_work_ticket(user, ticket, conn):
                continue
            _public_reply(conn, ticket, text, me, now)
            notices += notify.reply_added(ticket['ticket_id'], ticket['subject'],
                                          service._requester_ref(ticket), True)
            count += 1
        conn.execute("UPDATE support_incidents SET public_message = ?, updated_at = ? "
                     "WHERE incident_id = ?", (message, now, incident['incident_id']))
        log_audit('incident_update', resource_type='support_incident',
                  resource_id=incident['incident_id'], actor=user, conn=conn,
                  details={'tickets': count})
        notify.deliver_in_app(conn, notices, sender_username=me.username)
    notify.after_commit(notices)
    return count


def set_status(actor, incident_id, status) -> dict:
    """Move an incident between open and monitoring (use :func:`resolve` to
    resolve it). Returns ``{'old', 'new'}``."""
    user = _require_staff(actor)
    new = str(status or '').strip().lower()
    if new not in ('open', 'monitoring'):
        raise ValueError("An incident is open or monitoring; resolve it to close its tickets")
    with store.writing() as conn:
        incident = _incident(conn, incident_id)
        old = incident['status']
        if old == 'resolved':
            raise ValueError(f"Incident #{incident['incident_id']} is resolved")
        if old != new:
            conn.execute("UPDATE support_incidents SET status = ?, updated_at = ? "
                         "WHERE incident_id = ?", (new, _now(), incident['incident_id']))
            log_audit('incident_status', resource_type='support_incident',
                      resource_id=incident['incident_id'], actor=user, conn=conn,
                      old_values={'status': old}, new_values={'status': new})
        return {'old': old, 'new': new}


def resolve(actor, incident_id, resolution) -> dict:
    """Resolve the incident and every open ticket of it with ``resolution``.
    Returns ``{'resolved', 'skipped'}`` (tickets you may not work are left
    open and listed)."""
    user = _require_staff(actor)
    resolution = _text(resolution, "The resolution", MAX_TEXT)
    service = _service()
    notices, resolved, skipped = [], 0, []
    with store.writing() as conn:
        incident = _incident(conn, incident_id)
        if incident['status'] == 'resolved':
            raise ValueError(f"Incident #{incident['incident_id']} is already resolved")
        me = _auth.current_requester(user, conn)
        for ticket in _active_tickets(conn, incident['incident_id']):
            if not _auth.can_work_ticket(user, ticket, conn):
                skipped.append(ticket['ticket_id'])
                continue
            result, ticket_notices = service._change_status(conn, user, me, ticket, 'resolved',
                                                            resolution)
            notices += ticket_notices
            resolved += bool(result['changed'])
        now = _now()
        conn.execute("UPDATE support_incidents SET status = 'resolved', resolution = ?, "
                     "resolved_by = ?, resolved_at = ?, updated_at = ? WHERE incident_id = ?",
                     (resolution, me.username, now, now, incident['incident_id']))
        log_audit('resolve_incident', resource_type='support_incident',
                  resource_id=incident['incident_id'], actor=user, conn=conn,
                  details={'resolved': resolved, 'skipped': skipped})
        notify.deliver_in_app(conn, notices, sender_username=me.username)
    notify.after_commit(notices)
    return {'resolved': resolved, 'skipped': skipped}


# ── read ────────────────────────────────────────────────────────────────


def _counts(conn) -> dict:
    out = {}
    marks = ", ".join("?" * len(schema.ACTIVE_STATUSES))
    for iid, total, active in conn.execute(
            f"SELECT incident_id, COUNT(*), SUM(CASE WHEN status IN ({marks}) THEN 1 ELSE 0 END) "  # nosec B608
            "FROM support_tickets WHERE incident_id IS NOT NULL GROUP BY incident_id",
            list(schema.ACTIVE_STATUSES)).fetchall():
        out[iid] = (total, active or 0)
    return out


def list_incidents(actor, status=None) -> list:
    """Incidents, newest first, with their ticket counts (support staff)."""
    _require_staff(actor)
    with store.reading() as conn:
        sql, params = "SELECT * FROM support_incidents", []
        if status:
            values = status if isinstance(status, (list, tuple, set)) else [status]
            sql += f" WHERE status IN ({', '.join('?' * len(values))})"
            params = [str(v).lower() for v in values]
        counts = _counts(conn)
        out = []
        for row in conn.execute(sql + " ORDER BY incident_id DESC", params).fetchall():
            item = dict(row)
            item['tickets'], item['open_tickets'] = counts.get(row['incident_id'], (0, 0))
            item['status_label'] = STATUS_LABELS.get(row['status'], row['status'])
            out.append(item)
        return out


def get_incident(actor, incident_id) -> dict:
    """An incident with the tickets of it ``actor`` may see."""
    user = _require_staff(actor)
    with store.reading() as conn:
        incident = dict(_incident(conn, incident_id))
        tickets = []
        for row in conn.execute("SELECT * FROM support_tickets WHERE incident_id = ? "
                                "ORDER BY ticket_id", (incident['incident_id'],)).fetchall():
            if not _auth.can_view_ticket(user, row, conn):
                continue
            tickets.append({'ticket_id': row['ticket_id'], 'subject': row['subject'],
                            'status': schema.status_label(row['status']),
                            'requester': row['requester_username'] or row['student_id'],
                            'assigned_to': row['assigned_to'], 'created_at': row['created_at']})
        incident['tickets'] = tickets
        incident['status_label'] = STATUS_LABELS.get(incident['status'], incident['status'])
        return incident


def known_issues(actor) -> list:
    """Open incidents as everyone may see them: ``{'incident_id', 'title',
    'public_message', 'since'}``."""
    _auth.require_auth(actor)
    with store.reading() as conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' "
                            "AND name = 'support_incidents'").fetchone():
            return []
        return [{'incident_id': r['incident_id'], 'title': r['title'],
                 'public_message': r['public_message'] or '', 'since': r['created_at'],
                 'status': STATUS_LABELS.get(r['status'], r['status'])}
                for r in conn.execute("SELECT * FROM support_incidents WHERE status IN "
                                      "('open', 'monitoring') ORDER BY created_at DESC").fetchall()]


def report_affected(actor, incident_id, details='') -> dict:
    """Raise the signed-in person's own ticket for a known issue, already
    attached to it. Returns :func:`service.submit_ticket`'s result. A second
    report from the same person returns their existing ticket instead."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        routing,
    )
    user = _auth.require_auth(actor)
    service = _service()
    with store.reading() as conn:
        incident = _incident(conn, incident_id)
        if incident['status'] == 'resolved':
            raise ValueError("That issue has been fixed. If you still have a problem, please "
                             "raise a new ticket.")
        me = _auth.current_requester(user, conn)
        marks = ", ".join("?" * len(schema.ACTIVE_STATUSES))
        mine = conn.execute(
            f"SELECT ticket_id FROM support_tickets WHERE incident_id = ? AND "  # nosec B608
            f"requester_username = ? AND status IN ({marks}) LIMIT 1",
            [incident['incident_id'], me.username, *schema.ACTIVE_STATUSES]).fetchone()
    if mine:
        return {'ticket_id': mine[0], 'existing': True, 'crisis': None}
    category = next((c for c, t in routing.CATEGORY_TEAM.items() if t == incident['team']),
                    'General')
    details = str(details or '').strip()
    created = service.submit_ticket(
        user, subject=f"Affected by: {incident['title']}"[:service.MAX_SUBJECT],
        description=details or f"I am affected by the known issue \"{incident['title']}\".",
        category=category, priority='Medium', channel='known_issue', team=incident['team'])
    if created.get('crisis'):
        # Crisis language: the ticket is a safeguarding ticket and stays on its own.
        return {**created, 'existing': False}
    with store.writing() as conn:
        ticket = conn.execute("SELECT * FROM support_tickets WHERE ticket_id = ?",
                              (created['ticket_id'],)).fetchone()
        current = _incident(conn, incident['incident_id'])
        if current['status'] != 'resolved':
            system = _auth.Requester(username='system', role='system', users_id=None,
                                     student_id=None)
            _attach_row(conn, current, ticket, system)
            log_audit('report_affected', resource_type='support_incident',
                      resource_id=current['incident_id'], actor=user, conn=conn,
                      details={'ticket_id': ticket['ticket_id']})
    return {**created, 'existing': False}


__all__ = [
    'STATUSES', 'STATUS_LABELS', 'SEVERITIES', 'declare', 'attach', 'detach', 'post_update',
    'set_status', 'resolve', 'list_incidents', 'get_incident', 'known_issues',
    'report_affected',
]
