"""Telling people about ticket events.

In-app notices are ``messages`` rows (the Notifications Hub is an unread
inbox over ``messages``; the old ``notifications`` table was removed by
design and must not come back). They are written on the caller's connection
inside the change's own transaction, each under a savepoint so a notice that
cannot be delivered never undoes the change.

:func:`after_commit` runs once the change is committed and sends the e-mail
copies through the university outbox (``email_manager`` helpers, straight
to the outbox: the in-app copy already exists):

* ticket received — to the requester (with the out-of-hours and crisis
  contacts when it was raised out of hours), and to the duty officer for a
  Critical ticket raised out of hours;
* a staff reply that is not an internal note — to the requester;
* status now waiting on the student, or resolved — to the requester;
* the satisfaction survey when a ticket is resolved or closed — once per
  ticket, and recorded (``system_metrics`` 'satisfaction_survey_sent') for
  the response-rate report;
* SLA warnings and breaches — to the assignee, the team and its leads;
* a reply, internal note or status change — to the ticket's followers (the
  in-app notice's text, which never carries the reply or note itself), and
  to a member of staff someone else made a follower.

When e-mail into tickets is on (``settings``: ``inbound_enabled`` and a
``support_address``), the e-mails to the requester say they can reply to
the e-mail, and carry the support address as Reply-To; the subject keeps
"Ticket #N", which ``email_in`` matches the reply on. Restricted and
safeguarding tickets never invite e-mail replies.

Each e-mail has an outbox reference (``to_ref``, e.g.
``support:12:reply:57``) and is never sent twice. The person's preferences
are respected (Student Support ``user_preferences.email_notifications`` and
the outbox ``email_preferences`` for 'support'). A restricted or
safeguarding ticket's e-mails — and its in-app notices — never carry its
title or text: they say there is an update and ask the person to sign in.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

PRIVATE_TIERS = ('restricted', 'safeguarding')
EMAIL_CATEGORY = 'support'
SURVEY_METRIC = 'satisfaction_survey_sent'


@dataclass
class Notice:
    """One message to one person about one ticket event."""
    recipient: str                      # username (student number / users.id also resolve)
    subject: str
    body: str
    event: str = 'ticket'
    ticket_id: Optional[int] = None
    delivered_message_id: Optional[int] = field(default=None, compare=False)
    meta: dict = field(default_factory=dict, compare=False)


def _sender_id(conn, sender_username: Optional[str]) -> Optional[int]:
    if not sender_username:
        return None
    row = conn.execute("SELECT id FROM users WHERE username = ?", (sender_username,)).fetchone()
    return row[0] if row else None


def _is_private(ticket) -> bool:
    if ticket is None:
        return False
    try:
        tier = ticket['confidentiality']
        crisis = ticket['crisis_flag']
    except (KeyError, IndexError):
        return False
    return (tier in PRIVATE_TIERS) or bool(crisis)


def _private_ids(conn, ids) -> set:
    ids = sorted({int(i) for i in ids if i is not None})
    if not ids:
        return set()
    marks = ", ".join("?" * len(ids))
    return {r[0] for r in conn.execute(
        f"SELECT ticket_id FROM support_tickets WHERE ticket_id IN ({marks}) AND "  # nosec B608
        "(confidentiality IN ('restricted', 'safeguarding') OR COALESCE(crisis_flag, 0) = 1)",
        ids).fetchall()}


def generic(notice: Notice) -> Notice:
    """The notice with nothing of the ticket in it (restricted tiers)."""
    notice.subject = f"Update on support ticket #{notice.ticket_id}"
    notice.body = (f"There is an update on support ticket #{notice.ticket_id}. "
                   "Please sign in to Student Support to read it.")
    return notice


def deliver_in_app(conn, notices: Iterable[Notice], sender_username: Optional[str] = None) -> list:
    """Write each notice as an unread ``messages`` row on ``conn``.

    Returns the notices delivered. A recipient with no account is skipped; a
    database error on one notice is logged and rolled back to its savepoint.
    Notices about restricted or safeguarding tickets are made generic first.
    """
    from education_system.systems.university.infrastructure.email.messages_inbox import (
        deliver_inbox_message_on,
    )
    notices = list(notices or [])
    delivered = []
    sender = _sender_id(conn, sender_username)
    try:
        private = _private_ids(conn, [n.ticket_id for n in notices])
    except Exception:
        logger.warning("Could not read ticket tiers; every notice sent generic", exc_info=True)
        private = {n.ticket_id for n in notices}
    seen = set()
    for notice in notices:
        if not notice.recipient:
            continue
        if notice.ticket_id in private:
            generic(notice)
        if notice.event == 'survey' and notice.ticket_id is not None \
                and _survey_recorded(conn, notice.ticket_id):
            continue        # one survey per ticket
        key = (str(notice.recipient), notice.subject)
        if key in seen:
            continue
        seen.add(key)
        conn.execute("SAVEPOINT support_notice")
        try:
            message_id = deliver_inbox_message_on(conn, notice.recipient, notice.subject,
                                                  notice.body, sender_id=sender)
            conn.execute("RELEASE SAVEPOINT support_notice")
        except Exception:
            conn.execute("ROLLBACK TO SAVEPOINT support_notice")
            conn.execute("RELEASE SAVEPOINT support_notice")
            logger.warning("Could not deliver the %s notice for ticket #%s to %s",
                           notice.event, notice.ticket_id, notice.recipient, exc_info=True)
            continue
        if message_id is None:
            logger.info("No account for %s; %s notice for ticket #%s not delivered",
                        notice.recipient, notice.event, notice.ticket_id)
            continue
        notice.delivered_message_id = message_id
        delivered.append(notice)
    return delivered


# ── e-mail (after commit) ────────────────────────────────────────────────


@dataclass
class _Mail:
    helper: str                 # email_manager function name
    address: str
    to_ref: str
    subject: Optional[str]
    body: str
    kwargs: dict = field(default_factory=dict)


def _get(row, key):
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return None


def _person(conn, ref) -> Optional[dict]:
    """``{'username', 'users_id', 'email'}`` for a username or student number."""
    ref = str(ref or '').strip()
    if not ref:
        return None
    row = conn.execute("SELECT id, username, email FROM users WHERE username = ?", (ref,)).fetchone()
    if row is None:
        row = conn.execute("SELECT id, username, email FROM users WHERE student_id = ? "
                           "ORDER BY id LIMIT 1", (ref,)).fetchone()
    if row is not None:
        return {'username': row[1], 'users_id': row[0], 'email': row[2]}
    try:
        st = conn.execute("SELECT email_address FROM students WHERE student_id = ?",
                          (ref,)).fetchone()
    except Exception:
        st = None
    if st and st[0]:
        return {'username': None, 'users_id': None, 'email': st[0]}
    return None


def wants_email(conn, person: dict) -> bool:
    """False when the person turned support e-mail off (Student Support
    preferences, or the outbox preferences for 'support')."""
    keys = [str(k) for k in (person.get('users_id'), person.get('username')) if k is not None]
    if not keys:
        return True
    marks = ", ".join("?" * len(keys))
    try:
        row = conn.execute(f"SELECT email_notifications FROM user_preferences "  # nosec B608
                           f"WHERE user_id IN ({marks}) LIMIT 1", keys).fetchone()
        if row is not None and row[0] is not None and not row[0]:
            return False
    except Exception:
        logger.debug("No Student Support preferences table", exc_info=True)
    if person.get('username'):
        try:
            row = conn.execute("SELECT enabled FROM email_preferences WHERE user_id = ? AND "
                               "event_kind IN (?, 'all') AND enabled = 0 LIMIT 1",
                               (person['username'], EMAIL_CATEGORY)).fetchone()
            if row is not None:
                return False
        except Exception:
            logger.debug("No outbox preferences table", exc_info=True)
    return True


def _survey_recorded(conn, ticket_id) -> bool:
    try:
        return conn.execute("SELECT 1 FROM system_metrics WHERE metric_name = ? AND "
                            "metric_value = ? LIMIT 1", (SURVEY_METRIC, int(ticket_id))
                            ).fetchone() is not None
    except Exception:
        return False


def _status_of(notice: Notice) -> Optional[str]:
    from education_system.systems.university.domains.student_support.domain.student_support import (
        schema,
    )
    value = notice.meta.get('status')
    if not value:
        value = notice.subject.rsplit(': ', 1)[-1] if ': ' in notice.subject else ''
    try:
        return schema.normalize_status(value)
    except ValueError:
        return None


def _latest_staff_reply(conn, ticket_id):
    """``(ref, responder, text)`` of the newest public staff reply, from
    ``ticket_responses`` or the Helpdesk's ``ticket_replies``."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        auth as _auth,
    )
    roles = sorted(_auth.SUPPORT_ROLES | _auth.ADMIN_ROLES)
    marks = ", ".join("?" * len(roles))
    found = []
    row = conn.execute(
        "SELECT response_datetime, response_id, responder_username, response_text "
        "FROM ticket_responses WHERE ticket_id = ? AND COALESCE(is_internal, 0) = 0 "
        f"AND COALESCE(is_auto_generated, 0) = 0 AND responder_role IN ({marks}) "  # nosec B608
        "ORDER BY response_datetime DESC, response_id DESC LIMIT 1",
        [int(ticket_id)] + roles).fetchone()
    if row:
        found.append((str(row[0] or ''), str(row[1]), row[2], row[3]))
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' "
                    "AND name = 'ticket_replies'").fetchone():
        row = conn.execute(
            "SELECT r.created_at, r.reply_id, u.username, r.message FROM ticket_replies r "
            "JOIN users u ON u.id = r.user_id WHERE r.ticket_id = ? AND COALESCE(r.is_internal, 0) = 0 "
            f"AND u.role IN ({marks}) ORDER BY r.created_at DESC, r.reply_id DESC LIMIT 1",  # nosec B608
            [int(ticket_id)] + roles).fetchone()
        if row:
            found.append((str(row[0] or ''), f"hd{row[1]}", row[2], row[3]))
    if not found:
        return None
    _when, ref, who, text = max(found)
    return ref, who, text


def _sign_in(ticket_id) -> str:
    return f"Sign in to Student Support to see ticket #{ticket_id} and reply."


def reply_address(conn) -> Optional[str]:
    """The support address replies may go to, when e-mail into tickets is on."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        settings,
    )
    try:
        cfg = settings.automation(conn)
    except Exception:
        logger.debug("Support settings unavailable", exc_info=True)
        return None
    address = str(cfg.get('support_address') or '').strip()
    return address if cfg.get('inbound_enabled') and '@' in address else None


def _reply_line(ticket_id) -> str:
    return (f"You can reply to this e-mail to add to your ticket — please keep "
            f"\"Ticket #{ticket_id}\" in the subject line.")


def _mails_for(conn, notice: Notice, ticket, clock) -> list:
    """The e-mails one notice calls for (may be none)."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        routing,
        schema,
        sla,
    )
    tid = notice.ticket_id
    private = _is_private(ticket)
    title = _get(ticket, 'subject') or ''
    event = notice.event
    out = []
    reply_to = None if private else reply_address(conn)

    def to_requester(body):
        """``(body, kwargs)`` for an e-mail to the requester: the reply line
        and Reply-To when e-mail replies are taken."""
        if not reply_to:
            return body, {}
        return f"{body}\n\n{_reply_line(tid)}", {'reply_to': reply_to}

    def person_ok(ref):
        person = _person(conn, ref)
        if not person or not person.get('email') or '@' not in str(person['email']):
            return None
        return person if wants_email(conn, person) else None

    if event == 'created':
        who = person_ok(notice.recipient)
        created = sla.parse(_get(ticket, 'created_at'))
        out_of_hours = bool(created) and not clock.is_business_time(created)
        if who:
            if private:
                body = (f"We have received your support request (ticket #{tid}). An adviser "
                        f"will be in touch. {_sign_in(tid)}")
            else:
                due = sla.due_times(conn, ticket, clock)['first_response_due']
                body = (f"We have received your support request \"{title}\" (ticket #{tid}) "
                        f"and passed it to {routing.team_label(_get(ticket, 'team') or routing.route(_get(ticket, 'category')))}. "
                        f"We aim to reply by {due.strftime('%a %d %b %Y %H:%M')}. {_sign_in(tid)}")
            if out_of_hours:
                body += "\n\n" + sla.out_of_hours_message(conn)
            body, extra = to_requester(body)
            out.append(_Mail('send_email', who['email'], f"support:{tid}:received",
                             f"Support ticket #{tid} received", body, extra))
        assignee = _get(ticket, 'assigned_to')
        if (out_of_hours and str(_get(ticket, 'priority') or '').lower() == 'critical'
                and assignee and str(assignee) in routing.duty_officers(conn)):
            duty = person_ok(assignee)
            if duty:
                body = (f"Critical support ticket #{tid} was raised out of hours and has been "
                        "given to you as duty officer.")
                if not private:
                    body += f"\n\nTitle: {title}"
                out.append(_Mail('send_email', duty['email'], f"support:{tid}:duty:{assignee}",
                                 f"Critical support ticket #{tid} (out of hours)", body))
    elif event == 'reply':
        reply = _latest_staff_reply(conn, tid)
        who = person_ok(notice.recipient)
        if reply and who:
            if private:
                body = f"You have a new reply on support ticket #{tid}. {_sign_in(tid)}"
            else:
                body = (f"{reply[1] or 'Student Support'} replied to your support ticket "
                        f"\"{title}\" (#{tid}):\n\n{reply[2]}\n\n{_sign_in(tid)}")
            body, extra = to_requester(body)
            out.append(_Mail('send_reply_notification', who['email'],
                             f"support:{tid}:reply:{reply[0]}", None, body,
                             {'reply_by': None if private else reply[1], **extra}))
    elif event == 'status':
        status = _status_of(notice)
        who = person_ok(notice.recipient)
        if status in ('waiting_on_student', 'resolved') and who:
            stamp = _get(ticket, 'resolved_at') if status == 'resolved' else _get(ticket, 'updated_at')
            label = schema.STATUS_LABELS[status]
            if private:
                body = f"Support ticket #{tid} is now {label}. {_sign_in(tid)}"
            elif status == 'waiting_on_student':
                body = (f"We need more information from you about \"{title}\" (ticket #{tid}). "
                        f"{_sign_in(tid)}")
            else:
                body = f"Your support ticket \"{title}\" (#{tid}) has been resolved."
                if _get(ticket, 'resolution'):
                    body += f"\n\n{_get(ticket, 'resolution')}"
                body += f"\n\nIf you still need help, reply on the ticket. {_sign_in(tid)}"
            body, extra = to_requester(body)
            out.append(_Mail('send_email', who['email'], f"support:{tid}:status:{status}:{stamp}",
                             f"Support ticket #{tid}: {label}", body, extra))
        if status == 'closed':
            out += _survey_mail(conn, notice, ticket, person_ok)
    elif event == 'survey':
        out += _survey_mail(conn, notice, ticket, person_ok)
    elif event == 'follow':
        out += _follower_mail(conn, notice, ticket, person_ok, private)
    elif event == 'sla':
        who = person_ok(notice.recipient)
        if who:
            kind = notice.meta.get('kind', 'breach')
            body = notice.body if not private else (
                f"Support ticket #{tid} {notice.meta.get('what', 'needs attention')}. "
                "Sign in to Student Support to act on it.")
            out.append(_Mail('send_sla_alert', who['email'],
                             f"support:{tid}:sla:{kind}:{notice.recipient}", None, body,
                             {'sla_breach_type': notice.meta.get('label', 'Alert'),
                              'time_remaining': notice.meta.get('due')}))
    return out


def _follower_mail(conn, notice, ticket, person_ok, private) -> list:
    """A follower's copy of the in-app notice — staff who may still see the
    ticket (checked again here: following does not outlast access)."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        auth as _auth,
    )
    import hashlib
    tid = notice.ticket_id
    who = person_ok(notice.recipient)
    if not who or not who.get('username'):
        return []
    account = conn.execute("SELECT id, username, role FROM users WHERE username = ?",
                           (who['username'],)).fetchone()
    if account is None or not _auth.can_view_ticket(
            {'username': account[1], 'role': str(account[2] or '').lower(), 'id': account[0]},
            ticket, conn):
        return []
    if private:
        generic(notice)
    body = (f"{notice.body}\n\n{_sign_in(tid)} You get these e-mails because you follow "
            f"ticket #{tid}; unfollow it on the ticket to stop them.")
    stamp = notice.delivered_message_id or hashlib.sha256(
        f"{notice.subject}\n{notice.body}".encode()).hexdigest()[:16]
    return [_Mail('send_email', who['email'], f"support:{tid}:follow:{who['username']}:{stamp}",
                  notice.subject, body)]


def _survey_mail(conn, notice, ticket, person_ok) -> list:
    from education_system.systems.university.domains.student_support.domain.student_support import (
        schema,
    )
    tid = notice.ticket_id
    status = schema.normalize_status(_get(ticket, 'status'), default='open')
    if status not in schema.DONE_STATUSES or _get(ticket, 'satisfaction_rating') is not None:
        return []
    requester = _get(ticket, 'requester_username') or _get(ticket, 'student_id') or notice.recipient
    who = person_ok(requester)
    if not who:
        return []
    body = (f"Your support ticket #{tid} has been "
            f"{schema.STATUS_LABELS[status].lower()}. How did we do? Please sign in to Student "
            "Support and rate the help you received (1-5) on the ticket's page. "
            "It takes a few seconds and helps us improve.")
    return [_Mail('send_satisfaction_survey', who['email'], f"support:{tid}:survey", None, body)]


def _record_surveys(ticket_ids) -> None:
    """Note each survey once (``system_metrics``) for the response-rate report."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        store,
    )
    import datetime
    import json
    ids = sorted({int(t) for t in ticket_ids if t is not None})
    if not ids:
        return
    stamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with store.writing() as conn:
        for tid in ids:
            if _survey_recorded(conn, tid):
                continue
            conn.execute("INSERT INTO system_metrics (metric_name, metric_value, category, "
                         "recorded_datetime, metadata) VALUES (?, ?, 'satisfaction', ?, ?)",
                         (SURVEY_METRIC, tid, stamp, json.dumps({'ticket_id': tid})))


def _plan(notices: list) -> tuple[list, list]:
    """``(mails, surveyed ticket ids)`` for the notices — read only."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        schema,
        sla,
        store,
    )
    mails, surveyed = [], []
    with store.reading() as conn:
        clock = sla.Clock(conn)
        tickets = {}
        for notice in notices:
            if notice.ticket_id is None or not notice.recipient:
                continue
            if notice.ticket_id not in tickets:
                tickets[notice.ticket_id] = conn.execute(
                    "SELECT * FROM support_tickets WHERE ticket_id = ?",
                    (int(notice.ticket_id),)).fetchone()
            ticket = tickets[notice.ticket_id]
            if ticket is None or _get(ticket, 'data_purged_at'):
                continue
            if notice.event == 'survey' or (
                    notice.event == 'status' and _status_of(notice) == 'closed'):
                if schema.normalize_status(_get(ticket, 'status'), default='open') in schema.DONE_STATUSES:
                    surveyed.append(notice.ticket_id)
            try:
                mails += _mails_for(conn, notice, ticket, clock)
            except Exception:
                logger.warning("Could not prepare the %s e-mail for ticket #%s", notice.event,
                               notice.ticket_id, exc_info=True)
    return mails, surveyed


def send_mails(mails: Iterable[_Mail]) -> list:
    """Send planned e-mails through the outbox; returns the outcomes."""
    from education_system.systems.university.infrastructure.email import email_manager
    outcomes = []
    seen = set()
    for mail in mails:
        if mail.to_ref in seen:
            continue
        seen.add(mail.to_ref)
        helper = getattr(email_manager, mail.helper)
        extra = dict(mail.kwargs)
        if mail.helper == 'send_email':
            status = helper(mail.address, mail.subject, mail.body, to_ref=mail.to_ref,
                            in_app_copy=False, category=EMAIL_CATEGORY, **extra)
        else:
            ticket_id = mail.to_ref.split(':')[1]
            status = helper(ticket_id=ticket_id, recipient=mail.address, body=mail.body,
                            to_ref=mail.to_ref, in_app_copy=False, category=EMAIL_CATEGORY,
                            **extra)
        outcomes.append((mail.to_ref, status))
    return outcomes


def announce(notices: Iterable[Notice], sender_username: Optional[str] = None) -> list:
    """Deliver notices in-app (their own short transaction) and then send
    their e-mail copies — for callers that have already committed their
    change on another connection."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        store,
    )
    notices = list(notices or [])
    with store.writing() as conn:
        deliver_in_app(conn, notices, sender_username=sender_username)
    return after_commit(notices)


def after_commit(notices: Iterable[Notice]) -> list:
    """Send the e-mail copies of committed notices (see the module notes).
    Never raises; returns ``[(to_ref, outcome)]``."""
    notices = [n for n in (notices or []) if isinstance(n, Notice)]
    if not notices:
        return []
    try:
        mails, surveyed = _plan(notices)
    except Exception:
        logger.warning("Could not prepare support e-mails", exc_info=True)
        return []
    outcomes = []
    try:
        outcomes = send_mails(mails)
    except Exception:
        logger.warning("Support e-mails were not all sent", exc_info=True)
    try:
        _record_surveys(surveyed)
    except Exception:
        logger.warning("Could not record the satisfaction surveys sent", exc_info=True)
    return outcomes


# ── notice builders ──────────────────────────────────────────────────────


def ticket_created(ticket_id, subject, requester, assignee=None) -> list:
    out = [Notice(requester, f"Support ticket #{ticket_id} received",
                  f"We have received your support request \"{subject}\" (ticket #{ticket_id}). "
                  "You will be notified when it is updated.", 'created', ticket_id)]
    if assignee:
        out.append(Notice(assignee, f"Ticket #{ticket_id} assigned to you",
                          f"You have been assigned support ticket #{ticket_id}: {subject}.",
                          'assigned', ticket_id))
    return out


def reply_added(ticket_id, subject, recipient, from_staff: bool) -> list:
    if not recipient:
        return []
    if from_staff:
        return [Notice(recipient, f"New reply on support ticket #{ticket_id}",
                       f"Your support ticket #{ticket_id} \"{subject}\" has a new reply.",
                       'reply', ticket_id)]
    return [Notice(recipient, f"Student replied on ticket #{ticket_id}",
                   f"Ticket #{ticket_id} \"{subject}\" has a new reply from the student.",
                   'student_reply', ticket_id)]


def status_changed(ticket_id, subject, requester, label) -> list:
    from education_system.systems.university.domains.student_support.domain.student_support import (
        schema,
    )
    return [Notice(requester, f"Support ticket #{ticket_id}: {label}",
                   f"Your support ticket #{ticket_id} \"{subject}\" is now {label}.",
                   'status', ticket_id,
                   meta={'status': schema.normalize_status(label, default=str(label))})]


def satisfaction_invite(ticket_id, subject, requester) -> list:
    return [Notice(requester, f"How did we do? Ticket #{ticket_id}",
                   f"Your support ticket #{ticket_id} \"{subject}\" has been resolved. "
                   "Please rate the help you received from the ticket's page.",
                   'survey', ticket_id)]


def assigned(ticket_id, subject, assignee) -> list:
    return [Notice(assignee, f"Ticket #{ticket_id} assigned to you",
                   f"You have been assigned support ticket #{ticket_id}: {subject}.",
                   'assigned', ticket_id)]


def escalation_alert(ticket_id, subject, recipient, reason) -> list:
    return [Notice(recipient, f"Ticket #{ticket_id} needs attention",
                   f"Support ticket #{ticket_id} \"{subject}\" needs attention: {reason}.",
                   'escalation', ticket_id)]


def sla_alert(ticket_id, subject, recipient, *, kind, what, due) -> list:
    """An SLA warning or breach for staff. ``kind`` is the de-duplication
    key ('first_response_warning', 'resolution_breach' ...)."""
    label = 'Breach' if kind.endswith('breach') else 'Warning'
    return [Notice(recipient, f"SLA {label.lower()}: ticket #{ticket_id}",
                   f"Support ticket #{ticket_id} \"{subject}\" {what} (due {due}).",
                   'sla', ticket_id, meta={'kind': kind, 'what': what, 'due': due,
                                           'label': label})]


def duty_alert(ticket_id, subject, recipient) -> list:
    return [Notice(recipient, f"Critical ticket #{ticket_id} out of hours",
                   f"Critical support ticket #{ticket_id} \"{subject}\" was raised out of hours "
                   "and needs the duty officer.", 'duty', ticket_id)]
