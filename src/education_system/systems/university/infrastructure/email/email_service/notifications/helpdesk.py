"""Helpdesk and support ticket notification emails.

Kept for the Email Manager's "send ticket notification" dialogs and older
callers. Every e-mail is planned and sent by the Student Support notifier
(``student_support.notify``): it goes through the outbox with a ``to_ref``
(so a notice is never sent twice), respects the person's e-mail preferences,
and a restricted or safeguarding ticket's e-mail never carries its title or
text (sealed text is never read here). The ticket service already sends
these when a ticket changes; calling these again re-sends nothing that went.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from education_system.systems.university.infrastructure.logs import handle_exception, log_event

_SENT = 'sent to outbox'


def _notify():
    # Imported here: the support package is heavy and this module is loaded
    # with the e-mail service.
    from education_system.systems.university.domains.student_support.domain.student_support import (
        notify,
    )
    return notify


def _ticket(ticket_id):
    """The routing columns of a ticket — never its description or replies."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        store,
    )
    with store.reading() as conn:
        return conn.execute('''
            SELECT ticket_id, subject, requester_username, student_id, assigned_to, team,
                   confidentiality, crisis_flag, status, priority
            FROM support_tickets WHERE ticket_id = ?''', (int(ticket_id),)).fetchone()


def _requester(ticket, fallback=None):
    return ticket['requester_username'] or ticket['student_id'] or fallback


def _sent(outcomes) -> bool:
    return any(status == _SENT for _ref, status in outcomes)


def _staff_mails(ticket, usernames, event, subject_line, body):
    """E-mails to staff (``admin_list`` of older callers) about ``ticket``;
    a confidential ticket's title is left out."""
    notify = _notify()
    from education_system.systems.university.domains.student_support.domain.student_support import (
        store,
    )
    tid = ticket['ticket_id']
    private = notify._is_private(ticket)
    if not private:
        body = f"{body}\n\nTitle: {ticket['subject']}"
    mails = []
    with store.reading() as conn:
        for name in dict.fromkeys(str(u) for u in usernames if u):
            person = notify._person(conn, name)
            if not person or '@' not in str(person.get('email') or '') \
                    or not notify.wants_email(conn, person):
                continue
            mails.append(notify._Mail('send_email', person['email'],
                                      f"support:{tid}:{event}:{name}", subject_line, body))
    return notify.send_mails(mails)


def _admin_names(admin_list):
    for admin in admin_list or []:
        yield admin[0] if isinstance(admin, (list, tuple)) else admin


@handle_exception
def send_ticket_notification(ticket_id, subject, username, admin_list=None):
    """E-mail the requester that ticket ``ticket_id`` was received (and the
    staff in ``admin_list`` that it was raised)."""
    try:
        ticket = _ticket(ticket_id)
        if ticket is None:
            log_event('error', f"Could not find ticket {ticket_id}")
            return False
        notify = _notify()
        outcomes = notify.after_commit(notify.ticket_created(
            ticket['ticket_id'], ticket['subject'], _requester(ticket, username)))
        if admin_list:
            outcomes += _staff_mails(
                ticket, [n for n in _admin_names(admin_list)], 'created',
                f"New support ticket #{ticket['ticket_id']}",
                f"Support ticket #{ticket['ticket_id']} has been raised. Sign in to the "
                "Helpdesk to see it.")
        ok = _sent(outcomes)
        if ok:
            log_event('info', f"Ticket notification sent for ticket #{ticket_id}")
        return ok
    except Exception as e:
        log_event('error', f"Error sending ticket notification: {e}")
        return False


@handle_exception
def send_reply_notification(ticket_id, user_id=None, username=None, responder=None, admin_list=None,
                            status_update=None):
    """E-mail the requester about the latest staff reply on a ticket, or —
    with ``status_update`` — that its status changed."""
    try:
        ticket = _ticket(ticket_id)
        if ticket is None:
            log_event('error', f"Could not find ticket with ID {ticket_id}")
            return False
        notify = _notify()
        tid, title = ticket['ticket_id'], ticket['subject']
        requester = _requester(ticket, username)
        if status_update:
            from education_system.systems.university.domains.student_support.domain.student_support import (
                schema,
            )
            notices = notify.status_changed(tid, title, requester,
                                            schema.status_label(status_update))
        else:
            notices = notify.reply_added(tid, title, requester, True)
        outcomes = notify.after_commit(notices)
        staff = [n for n in _admin_names(admin_list) if n != responder]
        if staff:
            what = 'status changed' if status_update else 'new reply'
            outcomes += _staff_mails(ticket, staff, 'update', f"Support ticket #{tid}: {what}",
                                     f"Support ticket #{tid} has been updated ({what}).")
        ok = _sent(outcomes)
        if ok:
            log_event('info', f"Reply notification sent for ticket #{ticket_id}")
        return ok
    except Exception as e:
        log_event('error', f"Error sending reply notification: {e}")
        return False


@handle_exception
def send_sla_alert(ticket_id, alert_type='overdue'):
    """Alert the ticket's assignee and its team's leads about its SLA."""
    try:
        ticket = _ticket(ticket_id)
        if ticket is None:
            log_event('error', f"Ticket {ticket_id} not found for SLA alert")
            return False
        notify = _notify()
        from education_system.systems.university.domains.student_support.domain.student_support import (
            routing,
            sla,
            store,
        )
        with store.reading() as conn:
            full = conn.execute("SELECT ticket_id, created_at, first_response_at, resolved_at, "
                                "closed_at, status, team, category, subcategory, priority "
                                "FROM support_tickets WHERE ticket_id = ?",
                                (ticket['ticket_id'],)).fetchone()
            info = sla.ticket_sla(conn, full)
            leads = routing.team_leads(ticket['team'], conn) if ticket['team'] else set()
        recipients = ([str(ticket['assigned_to'])] if ticket['assigned_to'] else []) + sorted(leads)
        kind = {'overdue': 'resolution_breach', 'escalation': 'escalation'}.get(alert_type, alert_type)
        what = {'overdue': 'is past its resolution target',
                'escalation': 'has been escalated'}.get(alert_type, 'needs attention')
        notices = []
        for who in dict.fromkeys(recipients):
            notices += notify.sla_alert(ticket['ticket_id'], ticket['subject'], who, kind=kind,
                                        what=what, due=info['resolution_due'])
        ok = _sent(notify.after_commit(notices))
        if ok:
            log_event('info', f"SLA alert sent for ticket #{ticket_id}")
        return ok
    except Exception as e:
        log_event('error', f"Error sending SLA alert for ticket {ticket_id}: {e}")
        return False


@handle_exception
def send_satisfaction_survey(ticket_id, custom_message=None):
    """Send the satisfaction survey for a resolved or closed ticket (once).
    ``custom_message`` is kept for older callers; the survey text is the
    notifier's."""
    try:
        ticket = _ticket(ticket_id)
        if ticket is None:
            log_event('error', f"Ticket {ticket_id} not found for satisfaction survey")
            return False
        from education_system.systems.university.domains.student_support.domain.student_support import (
            schema,
        )
        if schema.normalize_status(ticket['status'], default='open') not in schema.DONE_STATUSES:
            log_event('warning', f"Cannot send satisfaction survey for ticket {ticket_id} - "
                                 f"status is {ticket['status']}")
            return False
        notify = _notify()
        ok = _sent(notify.after_commit(notify.satisfaction_invite(
            ticket['ticket_id'], ticket['subject'], _requester(ticket))))
        if ok:
            log_event('info', f"Satisfaction survey sent for ticket #{ticket_id}")
        return ok
    except Exception as e:
        log_event('error', f"Error sending satisfaction survey for ticket {ticket_id}: {e}")
        return False


@handle_exception
def send_bulk_satisfaction_surveys(days_old=1):
    """Send the survey for every ticket resolved in the last ``days_old``
    days that has not had one; returns ``(sent, considered)``."""
    try:
        from education_system.systems.university.domains.student_support.domain.student_support import (
            store,
        )
        cutoff = (datetime.now() - timedelta(days=days_old)).strftime('%Y-%m-%d %H:%M:%S')
        notify = _notify()
        with store.reading() as conn:
            ids = [r[0] for r in conn.execute(
                "SELECT ticket_id FROM support_tickets WHERE status IN ('resolved', 'closed') "
                "AND resolved_at >= ? AND satisfaction_rating IS NULL "
                "AND data_purged_at IS NULL ORDER BY ticket_id", (cutoff,)).fetchall()]
            ids = [t for t in ids if not notify._survey_recorded(conn, t)]
        sent = sum(1 for tid in ids if send_satisfaction_survey(tid))
        log_event('info', f"Bulk satisfaction surveys: {sent}/{len(ids)} sent successfully")
        return sent, len(ids)
    except Exception as e:
        log_event('error', f"Error sending bulk satisfaction surveys: {e}")
        return 0, 0
