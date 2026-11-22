"""A student's contacts with support services, in one timeline.

:func:`contacts_for_student` gathers, newest first:

* Student Support and Helpdesk tickets — each one only if
  ``auth.can_view_ticket`` lets the viewer see it (the confidentiality tiers
  live there; nothing here bypasses it);
* early-warning interventions (Pastoral, read through
  ``early_warning.early_warning_queries``) — support staff and admins, or
  the member of staff the intervention is assigned to;
* mitigating-circumstances claims, bursary applications and safeguarding
  concerns — other slices, read through the
  ``services.bus.student_contacts_bus`` port, which applies their owners'
  rules (safeguarding: safeguarding leads only).

Items are summaries (date, status, a title where the viewer may see the
ticket). Support staff, admins and the student themselves may ask;
every staff view is audited.
"""

from __future__ import annotations

import logging

from education_system.systems.university.domains.student_support.domain.student_support import (
    auth as _auth,
    routing,
    schema,
    store,
)
from education_system.systems.university.domains.student_support.domain.student_support.utils.audit import (
    log_audit,
)

logger = logging.getLogger(__name__)


def _item(source, kind, ref, date, status, title, **extra) -> dict:
    return {'source': source, 'kind': kind, 'id': ref, 'date': str(date or ''),
            'status': status, 'title': title, **extra}


def _student_usernames(conn, student_id) -> list:
    return [r[0] for r in conn.execute("SELECT username FROM users WHERE student_id = ?",
                                       (str(student_id),)).fetchall()]


def _tickets(conn, actor, student_id, usernames) -> list:
    clauses, params = ["student_id = ?", "(requester_username IS NULL AND user_id = ?)"], \
        [str(student_id), str(student_id)]
    if usernames:
        clauses.append(f"requester_username IN ({', '.join('?' * len(usernames))})")
        params += usernames
    rows = conn.execute("SELECT * FROM support_tickets WHERE " + " OR ".join(clauses)  # nosec B608
                        + " ORDER BY created_at DESC, ticket_id DESC", params).fetchall()
    out = []
    for row in rows:
        if not _auth.can_view_ticket(actor, row, conn):
            continue
        source = row['source'] or 'support'
        out.append(_item('helpdesk' if source == 'helpdesk' else 'student_support', 'ticket',
                         row['ticket_id'], row['created_at'], schema.status_label(row['status']),
                         row['subject'], category=routing.category_label(row['category']),
                         team=routing.team_label(row['team']) if row['team'] else None,
                         confidentiality=row['confidentiality']))
    return out


def _interventions(user, student_id) -> list:
    from education_system.systems.university.domains.student_support.domain.early_warning import (
        early_warning_queries,
    )
    staff = _auth.is_support_staff(user)
    try:
        rows = early_warning_queries.interventions_for_student(str(student_id))
    except Exception:
        logger.warning("Early-warning interventions unreadable for the 360 view", exc_info=True)
        return []
    return [_item('early_warning', 'intervention', r.get('intervention_id'), r.get('created_at'),
                  r.get('status'), str(r.get('intervention_type') or '').replace('_', ' ').title(),
                  priority=r.get('priority'), assigned_to=r.get('assigned_to'))
            for r in rows if staff or str(r.get('assigned_to') or '') == user['username']]


def contacts_for_student(actor, student_id) -> list:
    """Every contact ``actor`` may see for ``student_id`` (a student number),
    newest first: ``[{'source', 'kind', 'id', 'date', 'status', 'title', ...}]``."""
    from education_system.systems.university.services.bus import student_contacts_bus as port
    user = _auth.require_auth(actor)
    student_id = str(student_id or '').strip()
    if not student_id:
        raise ValueError("Say which student")
    with store.reading() as conn:
        me = _auth.current_requester(user, conn)
        own = bool(me.student_id) and me.student_id == student_id
        if not own and not _auth.is_support_staff(user):
            raise PermissionError("Only support staff can see a student's support history")
        usernames = _student_usernames(conn, student_id)
        items = _tickets(conn, user, student_id, usernames)
        viewer = {'username': me.username, 'role': me.role, 'student_id': me.student_id,
                  'teams': sorted(routing.user_teams(me.username, conn))}
    if not own:
        items += _interventions(user, student_id)
    items += [_item('mitigating_circumstances', 'claim', r['id'], r['date'], r['status'],
                    'Mitigating circumstances claim', module=r.get('module_code'))
              for r in port.mitigating_claims(student_id, viewer)]
    items += [_item('bursary', 'application', r['id'], r['date'], r['status'],
                    f"Bursary application{(' - ' + r['fund']) if r.get('fund') else ''}")
              for r in port.bursary_applications(student_id, viewer)]
    if not own:
        for name in usernames:
            items += [_item('safeguarding', 'concern', r['id'], r['date'], r['status'],
                            'Safeguarding concern', severity=r.get('severity'))
                      for r in port.safeguarding_concerns(name, viewer)]
    items.sort(key=lambda i: (i['date'], str(i['id'])), reverse=True)
    if not own:
        log_audit('view_student_360', resource_id=student_id, resource_type='student', actor=user,
                  details={'items': len(items),
                           'sources': sorted({i['source'] for i in items})})
    return items


__all__ = ['contacts_for_student']
