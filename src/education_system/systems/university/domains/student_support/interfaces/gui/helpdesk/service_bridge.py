"""The ticket service as the Helpdesk screens use it.

The Helpdesk screens never query ``support_tickets`` or its child tables:
lists and searches go through the ticket service (which applies the
visibility gate and shows a confidential ticket's text only to whoever may
read it), figures come from :func:`counts` (scoped, counts only) and every
change goes through the service so tiers, crisis detection, SLA, routing
and e-mail apply. Imported lazily: the support package is not needed until
a screen asks for tickets.
"""

from __future__ import annotations


def service():
    """The Helpdesk ticket service (``helpdesk.tickets.service``)."""
    from education_system.systems.university.domains.student_support.domain.helpdesk.tickets import (
        service as _service,
    )
    return _service


def support():
    """The Student Support ticket service (``student_support.service``)."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        service as _support,
    )
    return _support


def actor(gui):
    """The signed-in person for the service: the auth session's user (it
    carries the student number), else the screen's ``current_user``."""
    auth = getattr(gui, 'auth', None)
    user = getattr(auth, 'current_user', None) if auth is not None else None
    if isinstance(user, dict) and user.get('username'):
        return user
    return getattr(gui, 'current_user', None)


def is_case_worker(gui) -> bool:
    """Does the signed-in person work tickets (staff queues, figures)?"""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        auth as _auth,
    )
    who = actor(gui)
    return bool(who) and _auth.is_case_worker(who)


def status_label(value) -> str:
    """Display label for a stored (lower-case) status."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        schema,
    )
    return schema.status_label(value)


def status_choices() -> list:
    """``[(value, label)]`` for the status vocabulary, in order."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        schema,
    )
    return [(s, schema.STATUS_LABELS[s]) for s in schema.STATUSES]


def status_value(label_or_value):
    """The stored status for a label or value chosen on screen (None for
    'All' / blank)."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        schema,
    )
    if not label_or_value or str(label_or_value).strip().lower() in ('all', 'any', ''):
        return None
    return schema.normalize_status(label_or_value)


def counts(gui, by=None, filters=None, mine=False):
    """Ticket figures the signed-in person may see (no ticket text)."""
    return service().ticket_counts(actor(gui), by=by, filters=filters, mine=mine)


def all_tickets(gui, filters=None, mine=False) -> list:
    """Every ticket the signed-in person may see (``mine``: that they raised)."""
    return list(service().iter_tickets(actor(gui), filters, mine))


def display_name(row, *keys) -> str:
    """The first non-empty of ``keys`` in ``row`` (a dict) as text."""
    for key in keys:
        value = row.get(key)
        if value not in (None, ''):
            return str(value)
    return ''


def requester(row) -> str:
    """Who raised a ticket, for display."""
    return display_name(row, 'requester_username', 'student_id', 'user_id')


def local_user_id(gui):
    """The signed-in person's ``users.id`` in the university database
    (resolved by username: the session's id is an auth.db id), or None."""
    who = actor(gui)
    if not who or not who.get('username'):
        return None
    from education_system.systems.university.infrastructure.auth.session_user import (
        resolve_local_identity,
    )
    return resolve_local_identity(str(who['username']))[0]


def _day_end(value: str) -> str:
    value = str(value).strip()
    return value + ' 23:59:59' if len(value) == 10 else value


def criteria_filters(criteria: dict) -> dict:
    """Service filters for a search form's criteria (text / status /
    priority / category / start_date or date_from / end_date or date_to /
    assigned_user); 'all' and blanks are ignored."""
    filters = {}

    def given(*keys):
        for key in keys:
            value = criteria.get(key)
            if value not in (None, '') and str(value).strip().lower() not in ('all', 'any'):
                return str(value).strip()
        return None

    if given('text'):
        filters['search'] = given('text')
    if given('status'):
        filters['status'] = status_value(given('status'))
    if given('priority'):
        filters['priority'] = given('priority')
    if given('category'):
        filters['category'] = given('category')
    if given('start_date', 'date_from'):
        filters['date_from'] = given('start_date', 'date_from')
    if given('end_date', 'date_to'):
        filters['date_to'] = _day_end(given('end_date', 'date_to'))
    if given('assigned_user', 'assigned_to'):
        filters['assigned_to'] = given('assigned_user', 'assigned_to')
    return filters


def find(gui, criteria: dict, limit=None) -> list:
    """Tickets matching a search form's ``criteria``: support staff search
    every ticket they may see, anyone else their own. Each ticket carries
    ``submitter``, ``assignee`` and ``status_label`` for display."""
    filters = criteria_filters(criteria)
    mine = not is_case_worker(gui)
    if limit:
        lister = service().list_my_tickets if mine else service().list_tickets
        rows = lister(actor(gui), filters, 1, int(limit))['tickets']
    else:
        rows = all_tickets(gui, filters, mine=mine)
    for row in rows:
        row['submitter'] = requester(row)
        row['assignee'] = display_name(row, 'assigned_to')
        row.setdefault('status_label', status_label(row.get('status')))
    return rows


PERIOD_DAYS = {'7d': 7, '30d': 30, '90d': 90, '1y': 365}


def period_start(period) -> str:
    """The first day of a '7d' / '30d' / '90d' / '1y' period."""
    from datetime import datetime, timedelta
    days = PERIOD_DAYS.get(str(period), 30)
    return (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')


def _hours(start, end):
    from datetime import datetime
    try:
        a = datetime.fromisoformat(str(start)[:19])
        b = datetime.fromisoformat(str(end)[:19])
    except (TypeError, ValueError):
        return None
    return (b - a).total_seconds() / 3600


def ticket_stats(gui, date_from=None, date_to=None) -> dict:
    """Figures over the tickets the signed-in staff member may see that were
    raised in the period — counts, averages and breakdowns only (no ticket
    text). Staff only (the service raises PermissionError otherwise)."""
    from collections import Counter, defaultdict
    filters = {}
    if date_from:
        filters['date_from'] = str(date_from)
    if date_to:
        filters['date_to'] = _day_end(date_to)
    rows = all_tickets(gui, filters)
    done = {'resolved', 'closed'}
    by_status, by_priority, by_category, by_day = Counter(), Counter(), Counter(), Counter()
    ratings = Counter()
    staff = defaultdict(lambda: {'assigned': 0, 'resolved': 0, 'hours': [], 'ratings': []})
    depts = defaultdict(lambda: {'total': 0, 'resolved': 0, 'hours': []})
    hours_all, responded = [], 0
    for t in rows:
        status = str(t.get('status') or '')
        by_status[status] += 1
        by_priority[str(t.get('priority') or '').lower()] += 1
        by_category[t.get('category') or 'Uncategorized'] += 1
        by_day[str(t.get('created_at') or '')[:10]] += 1
        if t.get('first_response_at'):
            responded += 1
        hours = _hours(t.get('created_at'), t.get('resolved_at')) if t.get('resolved_at') else None
        if hours is not None:
            hours_all.append(hours)
        rating = t.get('satisfaction_rating')
        if rating is not None:
            ratings[int(rating)] += 1
        who = t.get('assigned_to')
        if who not in (None, ''):
            s = staff[str(who)]
            s['assigned'] += 1
            s['resolved'] += 1 if status in done else 0
            if hours is not None:
                s['hours'].append(hours)
            if rating is not None:
                s['ratings'].append(int(rating))
        d = depts[t.get('department') or 'Unassigned']
        d['total'] += 1
        d['resolved'] += 1 if status in done else 0
        if hours is not None:
            d['hours'].append(hours)

    def avg(values):
        return sum(values) / len(values) if values else None

    total = len(rows)
    resolved = sum(n for s, n in by_status.items() if s in done)
    rated = sum(ratings.values())
    return {
        'total_tickets': total,
        'open_tickets': by_status.get('open', 0),
        'resolved_tickets': resolved,
        'closed_tickets': by_status.get('closed', 0),
        'resolved_only': by_status.get('resolved', 0),
        'active_tickets': total - resolved,
        'high_priority': by_priority.get('high', 0) + by_priority.get('critical', 0)
        + by_priority.get('urgent', 0),
        'resolution_rate': (resolved / total * 100) if total else 0,
        'avg_resolution_hours': avg(hours_all) or 0,
        'avg_satisfaction': (sum(r * n for r, n in ratings.items()) / rated) if rated else 0,
        'rated': rated,
        'ratings': dict(sorted(ratings.items(), reverse=True)),
        'responded': responded,
        'by_status': {status_label(s): n for s, n in by_status.most_common()},
        'categories': dict(by_category.most_common()),
        'by_day': dict(sorted(by_day.items())),
        'staff_performance': sorted(
            ({'username': u, 'assigned': s['assigned'], 'resolved': s['resolved'],
              'avg_hours': avg(s['hours']), 'avg_satisfaction': avg(s['ratings'])}
             for u, s in staff.items()),
            key=lambda s: (-s['assigned'], s['username'])),
        'departments': sorted(
            ({'department': k, 'total': v['total'], 'resolved': v['resolved'],
              'avg_hours': avg(v['hours'])} for k, v in depts.items()),
            key=lambda d: -d['total']),
    }


def user_roles(usernames) -> dict:
    """``{username: role}`` from the university users table."""
    names = [str(u) for u in usernames if u]
    if not names:
        return {}
    from education_system.systems.university.infrastructure.database.db import get_connection
    conn = get_connection()
    try:
        marks = ", ".join("?" * len(names))
        return {r[0]: r[1] for r in conn.execute(
            f"SELECT username, role FROM users WHERE username IN ({marks})",  # nosec B608 - placeholders only
            names).fetchall()}
    finally:
        conn.close()


def delete_attachment(gui, ticket_id, attachment_id) -> None:
    """Delete an attachment (support staff working the ticket; audited)."""
    from education_system.systems.university.domains.student_support.domain.helpdesk.tickets import (
        service as hd,
    )
    hd.delete_attachment(actor(gui), ticket_id, attachment_id)
