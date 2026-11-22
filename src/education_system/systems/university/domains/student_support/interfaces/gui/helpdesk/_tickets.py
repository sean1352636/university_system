"""The Helpdesk screens' link to the one ticket service.

Every ticket read and write the Helpdesk GUI makes goes through the Student
Support ticket service (``student_support.service``) or its Helpdesk front
(``helpdesk.tickets.service``): they check who may see and do what (team and
confidentiality tier), reveal sealed text only after the gate, detect crisis
language, keep the SLA and send the notices. Nothing here touches the ticket
tables; this module only adapts the service's results for Tk — status labels,
tier badges, SLA labels, the crisis dialog and the assignee lists.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk

from education_system.systems.university.domains.student_support.domain.helpdesk.tickets import (
    service as hd,
)
from education_system.systems.university.domains.student_support.domain.student_support import (
    auth as ss_auth,
    routing,
    schema,
    service as svc,
    store,
)

try:
    from education_system.systems.university.infrastructure.i18n import get_text as _t
except ImportError:  # pragma: no cover - i18n is part of the university package
    _t = lambda key, **kwargs: kwargs.get("default", key)  # noqa: E731

logger = logging.getLogger(__name__)

SEALED_PLACEHOLDER = svc.SEALED_PLACEHOLDER

# Helpdesk categories (the routing maps each to its team: IT Services,
# Academic Registry, Fees & Funding; 'Other' goes to the general team).
CATEGORIES = ["Technical Support", "Academic Inquiry", "Financial Services",
              "Account Access", "Other"]
PRIORITIES = ["low", "medium", "high"]

TIER_BADGES = {
    'restricted': lambda: _t('gui.pastoral.helpdesk.tier.restricted', default="Restricted"),
    'safeguarding': lambda: _t('gui.pastoral.helpdesk.tier.safeguarding', default="Safeguarding"),
}


# ── who is signed in ─────────────────────────────────────────────────────


def actor(gui):
    """The signed-in person to hand the service: the auth object when it has
    a session, else the GUI's ``current_user`` dict (identity is always
    resolved by username in the service)."""
    auth = getattr(gui, 'auth', None)
    if auth is not None and getattr(auth, 'current_user', None):
        return auth
    return getattr(gui, 'current_user', None)


def username(gui):
    user = ss_auth.user_of(actor(gui)) or {}
    return user.get('username')


def local_user_id(gui):
    """The signed-in person's ``student_records.db`` ``users.id`` (resolved
    by username — the session's id is an ``auth.db`` id), or None. Only for
    the Helpdesk's own users.id-keyed tables (time tracking, links, audit)."""
    name = username(gui)
    if not name:
        return None
    try:
        from education_system.systems.university.infrastructure.auth.session_user import (
            resolve_local_identity,
        )
        return resolve_local_identity(name)[0]
    except Exception:
        logger.debug("Could not resolve %s to a local user", name, exc_info=True)
        return None


def is_case_worker(gui) -> bool:
    return ss_auth.is_case_worker(actor(gui))


def deflection():
    """``student_support.deflection`` (self-help suggestions from both KBs)."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        deflection as _deflection,
    )
    return _deflection


# ── labels ───────────────────────────────────────────────────────────────


def status_label(value) -> str:
    return schema.status_label(value)


def status_choices() -> list:
    """``[(status, label)]`` in the one vocabulary's order."""
    return [(s, schema.STATUS_LABELS[s]) for s in schema.STATUSES]


def status_labels(with_all=False) -> list:
    labels = [label for _s, label in status_choices()]
    return ([_t('gui.pastoral.helpdesk.values.all', default="all")] + labels) if with_all else labels


def status_from_label(label):
    """The stored status for a label shown in a list (None for 'all' / blank)."""
    if not label or str(label).strip().lower() == 'all':
        return None
    return schema.normalize_status(label)


def tier_badge(ticket) -> str:
    tier = (ticket or {}).get('confidentiality') or 'standard'
    badge = TIER_BADGES.get(tier)
    return badge() if badge else ''


def sla_label(ticket) -> str:
    """'Met', 'Breached', 'Due in 3.5h', 'Overdue by 2h' … ('' if unknown)."""
    try:
        return hd.sla_status(ticket)['label']
    except Exception:
        logger.debug("No SLA status for ticket %s", (ticket or {}).get('ticket_id'),
                     exc_info=True)
        return ''


def requester_of(ticket) -> str:
    return str(ticket.get('requester_username') or ticket.get('student_id')
               or _t('gui.pastoral.helpdesk.values.unknown', default="Unknown"))


# ── messages ─────────────────────────────────────────────────────────────


def show_error(exc, parent=None, title=None) -> None:
    """The service's PermissionError / ValueError messages are written to be
    shown as they are; anything else is shown with its text too."""
    title = title or _t('gui.pastoral.helpdesk.dialogs.error', default="Error")
    if isinstance(exc, PermissionError):
        title = _t('gui.pastoral.helpdesk.dialogs.permission_denied', default="Permission Denied")
    elif not isinstance(exc, ValueError):
        logger.exception("Helpdesk action failed", exc_info=exc)
    messagebox.showerror(title, str(exc), parent=parent)


def show_crisis(crisis, parent=None) -> None:
    """Show the crisis contacts at once (``crisis`` from submit / reply)."""
    if not crisis:
        return
    text = crisis.get('message') or "\n".join(crisis.get('lines') or [])
    messagebox.showwarning(
        _t('gui.pastoral.helpdesk.crisis.title', default="Support is available now"),
        text, parent=parent)


# ── assignment ───────────────────────────────────────────────────────────


def _roles(usernames) -> dict:
    names = sorted({str(u) for u in usernames if u})
    if not names:
        return {}
    marks = ", ".join("?" * len(names))
    with store.reading() as conn:
        return {r[0]: r[1] for r in conn.execute(
            f"SELECT username, role FROM users WHERE username IN ({marks})",  # nosec B608
            names).fetchall()}


def _admins() -> list:
    marks = ", ".join("?" * len(ss_auth.ADMIN_ROLES))
    with store.reading() as conn:
        return [r[0] for r in conn.execute(
            f"SELECT username FROM users WHERE role IN ({marks}) ORDER BY username",  # nosec B608
            sorted(ss_auth.ADMIN_ROLES)).fetchall()]


def staff_choices(team=None) -> list:
    """Who a ticket of ``team`` (all teams when None) can be given to:
    ``[{'id', 'username', 'role', 'team', 'department', 'open', 'max',
    'available'}]`` — the team members by load, then the admins. ``id`` is
    the username (assignment is by username)."""
    with store.reading() as conn:
        rows = routing.capacity(conn, team)
    seen, out = set(), []
    for r in sorted(rows, key=lambda r: (r['open'], r['username'])):
        if r['username'] in seen:
            continue
        seen.add(r['username'])
        out.append({'id': r['username'], 'username': r['username'], 'role': None,
                    'team': r['team'], 'department': routing.team_label(r['team']),
                    'open': r['open'], 'max': r['max'], 'available': r['available']})
    for name in _admins():
        if name not in seen:
            seen.add(name)
            out.append({'id': name, 'username': name, 'role': None, 'team': None,
                        'department': _t('gui.pastoral.helpdesk.values.admin', default="Admin"),
                        'open': None, 'max': None, 'available': None})
    roles = _roles(seen)
    for s in out:
        s['role'] = roles.get(s['username'], 'staff')
    return out


def team_for_department(department):
    """The team whose department is ``department`` (a departments.name)."""
    for key in routing.TEAMS:
        dept = routing.team_department(key)
        if dept and dept.get('name') == department:
            return key
    return routing.team_key(department)


# ── windows ──────────────────────────────────────────────────────────────


def size_window(win, width=1400, height=900) -> None:
    """The house window size (clamped to the screen by window_sizing)."""
    from education_system.platform.delivery.gui import window_sizing
    window_sizing.install()
    win.geometry(f"{width}x{height}")
    win.minsize(min(width, 1200), min(height, 800))


def banner(parent, ticket, *, wrap=900) -> None:
    """Tier badge, crisis banner and SLA line at the top of a ticket view."""
    tier = tier_badge(ticket)
    if ticket.get('crisis_flag'):
        tk.Label(parent, text=_t('gui.pastoral.helpdesk.crisis.banner',
                                 default="Crisis language was detected on this ticket: it is a "
                                         "safeguarding ticket and the safeguarding team has "
                                         "been told."),
                 bg='#b00020', fg='white', wraplength=wrap, justify='left',
                 padx=8, pady=6).pack(fill='x', padx=10, pady=(5, 0))
    if ticket.get('crisis_support'):
        text = ticket['crisis_support'].get('message') or ''
        tk.Label(parent, text=text, bg='#fff3cd', fg='#5c4400', wraplength=wrap,
                 justify='left', padx=8, pady=6).pack(fill='x', padx=10, pady=(5, 0))
    line = []
    if tier:
        line.append(_t('gui.pastoral.helpdesk.tier.label', default="Confidentiality: {tier}")
                    .format(tier=tier))
    sla = sla_label(ticket)
    if sla:
        line.append(_t('gui.pastoral.helpdesk.sla.label', default="SLA: {status}").format(status=sla))
    if line:
        ttk.Label(parent, text="   |   ".join(line),
                  style='Warning.TLabel' if tier else 'Heading.TLabel'
                  ).pack(anchor='w', padx=10, pady=(5, 0))


__all__ = [
    'hd', 'svc', 'schema', 'routing', 'ss_auth', 'store', 'CATEGORIES', 'PRIORITIES',
    'SEALED_PLACEHOLDER', 'deflection', 'actor', 'username', 'local_user_id', 'is_case_worker',
    'status_label', 'status_choices', 'status_labels', 'status_from_label', 'tier_badge',
    'sla_label', 'requester_of', 'show_error', 'show_crisis', 'staff_choices',
    'team_for_department', 'size_window', 'banner',
]
