"""What every Student Support screen shares: who is signed in, what they may
do, and the small widgets the ticket screens repeat.

The screens never read or write the ticket tables themselves. They call the
ticket service (``student_support.service``) and its companions (caseload,
routing, referrals, consent, confidentiality, sla, gdpr, deflection,
history360), each of which takes the signed-in actor first, checks permission
and raises ``PermissionError`` / ``ValueError`` with a message fit to show as
it is — :func:`run` does exactly that.

Role checks all come from ``student_support.auth`` (the domain's one
definition of support staff, case workers and admins), with the role compared
in lower case, plus ``auth.check_permission`` where the permission system has
a permission for the action (``manage_users``).
"""

from __future__ import annotations

import csv
import importlib
import logging
import tkinter as tk
from tkinter import ttk

from education_system.systems.university.infrastructure.i18n import get_text as _t

from ._dialogs import make_toplevel, messagebox, filedialog

logger = logging.getLogger(__name__)

_SS = "education_system.systems.university.domains.student_support.domain.student_support"

#: Largest size a Student Support dialog asks for (the house window size).
MAX_DIALOG = (1400, 900)

TIER_COLOURS = {
    'standard': ('#e5e7eb', '#374151'),
    'restricted': ('#fde68a', '#92400e'),
    'safeguarding': ('#fecaca', '#991b1b'),
}

#: Categories whose tickets are confidential by default: the form says so.
SENSITIVE_HINT = _t(
    'gui.pastoral.student_support.common.confidential_hint',
    default="This kind of request is confidential: only the specialist team (and, for "
            "health matters, the health team) can read it, and every look at it is recorded.")


def ss(name: str):
    """A Student Support domain module (``service``, ``routing``, ...)."""
    return importlib.import_module(f"{_SS}.{name}")


# ── who is signed in ─────────────────────────────────────────────────────


def actor(gui) -> dict:
    """The signed-in user as the domain takes it: the session's
    ``current_user`` with the role in lower case ({} when nobody)."""
    auth = getattr(gui, 'auth', None)
    user = getattr(auth, 'current_user', None) if auth is not None else None
    if not isinstance(user, dict) or not user.get('username'):
        return {}
    return dict(user, role=str(user.get('role') or '').strip().lower())


def username(gui) -> str:
    return str(actor(gui).get('username') or '')


def role(gui) -> str:
    return str(actor(gui).get('role') or '')


def is_admin(gui) -> bool:
    return bool(actor(gui)) and ss('auth').is_admin(actor(gui))


def is_support_staff(gui) -> bool:
    """Support roles and admins (reports, exports, bulk updates)."""
    return bool(actor(gui)) and ss('auth').is_support_staff(actor(gui))


def is_case_worker(gui) -> bool:
    """Works tickets at all: support staff, admins, the health team,
    safeguarding leads, or anyone routing puts in a team."""
    return bool(actor(gui)) and ss('auth').is_case_worker(actor(gui))


def can_work(gui, ticket) -> bool:
    """May act on ``ticket`` as staff (status, assign, refer, internal notes)."""
    return bool(actor(gui)) and ss('auth').can_work_ticket(actor(gui), ticket)


def can_see_internal(gui, ticket=None) -> bool:
    return bool(actor(gui)) and ss('auth').can_see_internal(actor(gui), ticket)


def has_permission(gui, permission: str) -> bool:
    """``auth.check_permission`` when the session's auth object has one."""
    check = getattr(getattr(gui, 'auth', None), 'check_permission', None)
    if check is None:
        return False
    try:
        return bool(check(permission))
    except Exception:
        logger.debug("Permission check for %s failed", permission, exc_info=True)
        return False


def can_manage_users(gui) -> bool:
    return is_admin(gui) or has_permission(gui, 'manage_users')


def can_manage_team(gui, team) -> bool:
    """Admins, and the team's own leads (routing.set_member's rule)."""
    if is_admin(gui):
        return True
    return is_support_staff(gui) and username(gui) in ss('routing').team_leads(team)


# ── calling the domain ───────────────────────────────────────────────────


def run(parent, fn, *args, title=None, **kwargs):
    """Call ``fn``; show a PermissionError / ValueError as it is (the domain
    writes them for people). Returns the result, or None after a message."""
    where = {'parent': parent} if parent is not None else {}
    try:
        return fn(*args, **kwargs)
    except PermissionError as exc:
        messagebox.showwarning(title or _t('gui.pastoral.student_support.common.not_allowed',
                                           default="Not allowed"), str(exc), **where)
    except (ValueError, FileNotFoundError, OSError) as exc:
        messagebox.showerror(title or _t('gui.pastoral.student_support.common.error',
                                         default="Error"), str(exc), **where)
    except Exception as exc:  # an unexpected fault: log it, say something useful
        logger.exception("Student Support action failed")
        messagebox.showerror(title or _t('gui.pastoral.student_support.common.error',
                                         default="Error"),
                             _t('gui.pastoral.student_support.common.unexpected',
                                default="Something went wrong: {error}").format(error=exc),
                             **where)
    return None


# ── labels ───────────────────────────────────────────────────────────────


def status_label(value) -> str:
    try:
        return ss('schema').status_label(value)
    except Exception:
        return str(value or '')


def status_choices() -> list:
    """``[(label, value)]`` for the one status vocabulary."""
    return [(label, value) for value, label in ss('schema').STATUS_LABELS.items()]


def status_value(label_or_value):
    """The stored status for a label or value ('' / 'All' -> None)."""
    text = str(label_or_value or '').strip()
    if not text or text.lower() == 'all':
        return None
    return ss('schema').normalize_status(text)


def category_label(value) -> str:
    return ss('routing').category_label(value)


def team_label(value) -> str:
    return ss('routing').team_label(value) if value else ''


def categories() -> list:
    """The UK categories offered on new tickets."""
    return list(ss('config').SUPPORT_CATEGORIES)


def priorities() -> list:
    return list(ss('config').TICKET_PRIORITIES)


def tier_of(ticket) -> str:
    return ss('confidentiality').tier_of(ticket)


def tier_label(tier) -> str:
    return ss('confidentiality').TIER_LABELS.get(tier, str(tier or '').title())


def is_sensitive_category(category) -> bool:
    """Would a ticket in ``category`` be restricted from the start?"""
    try:
        return ss('confidentiality').classify(category) != 'standard'
    except Exception:
        return False


# ── SLA ──────────────────────────────────────────────────────────────────


def sla_state(ticket) -> dict | None:
    """Where ``ticket`` stands against its service level, with ``warning``
    when the next target is close: under a quarter of its hours left."""
    sla = ss('sla')
    try:
        with ss('store').reading() as conn:
            state = sla.ticket_sla(conn, ticket)
    except Exception:
        logger.debug("SLA unavailable for ticket", exc_info=True)
        return None
    targets = state.get('targets') or {}
    pending_first = not ticket.get('first_response_at')
    target = targets.get('first_response_hours' if pending_first else 'resolution_hours') or 0
    hours = state.get('hours_left')
    breached = bool(state.get('first_response_breached') or state.get('resolution_breached'))
    state['breached'] = breached
    state['warning'] = (not breached and hours is not None and target
                        and 0 <= hours <= max(target * 0.25, 0.5))
    return state


def sla_text(state) -> str:
    if not state:
        return _t('gui.pastoral.student_support.common.sla_unknown', default="Not available")
    if state.get('next_due') is None:
        met = []
        if state.get('first_response_met') is not None:
            met.append("first response " + ("met" if state['first_response_met'] else "missed"))
        if state.get('resolution_met') is not None:
            met.append("resolution " + ("met" if state['resolution_met'] else "missed"))
        return "Closed — " + (", ".join(met) or "no target measured")
    hours = state.get('hours_left')
    if state.get('breached'):
        return f"BREACHED — was due {state['next_due']} ({abs(hours or 0):.1f} h over)"
    if state.get('paused'):
        return f"Paused — waiting on the student ({hours:.1f} h left when it restarts)"
    flag = "Due soon — " if state.get('warning') else ""
    return f"{flag}due {state['next_due']} ({hours:.1f} h left)"


def sla_colour(state) -> str:
    if not state or state.get('next_due') is None:
        return '#374151'
    if state.get('breached'):
        return '#b91c1c'
    if state.get('warning'):
        return '#b45309'
    return '#15803d'


# ── widgets ──────────────────────────────────────────────────────────────


def dialog(gui, title, width=900, height=600, *, modal=False):
    """A Student Support dialog: parented to the portal, centred, no larger
    than the house window size; Ctrl+W closes it (bound by make_toplevel)."""
    from education_system.platform.delivery.gui import window_sizing
    win = make_toplevel(gui.root)
    win.title(title)
    window_sizing.center(win, min(int(width), MAX_DIALOG[0]), min(int(height), MAX_DIALOG[1]))
    if modal:
        try:
            win.grab_set()
        except tk.TclError:
            pass
    return win


def tier_badge(parent, tier):
    bg, fg = TIER_COLOURS.get(tier, TIER_COLOURS['standard'])
    return tk.Label(parent, text=f" {tier_label(tier).upper()} ", bg=bg, fg=fg,
                    font=('Segoe UI', 9, 'bold'), padx=6, pady=2)


def crisis_lines(crisis) -> list:
    lines = list((crisis or {}).get('lines') or [])
    if not lines and (crisis or {}).get('message'):
        lines = [line for line in str(crisis['message']).splitlines() if line]
    return lines


def crisis_banner(parent, crisis):
    """The persistent red banner with the crisis contacts."""
    frame = tk.Frame(parent, bg='#fee2e2', highlightbackground='#dc2626', highlightthickness=2)
    tk.Label(frame, text=_t('gui.pastoral.student_support.common.crisis_title',
                            default="If you are in danger or might act on thoughts of harming "
                                    "yourself, get help now:"),
             bg='#fee2e2', fg='#991b1b', font=('Segoe UI', 10, 'bold'), anchor='w',
             justify='left', wraplength=1100).pack(fill='x', padx=10, pady=(8, 2))
    for line in crisis_lines(crisis):
        tk.Label(frame, text=line, bg='#fee2e2', fg='#7f1d1d', anchor='w', justify='left',
                 wraplength=1100, font=('Segoe UI', 10)).pack(fill='x', padx=18)
    ref = (crisis or {}).get('safeguarding_reference')
    if ref:
        tk.Label(frame, text=_t('gui.pastoral.student_support.common.crisis_reference',
                                default="The safeguarding team has been told (reference {ref}).")
                 .format(ref=ref), bg='#fee2e2', fg='#7f1d1d', anchor='w').pack(
                     fill='x', padx=18)
    tk.Frame(frame, height=6, bg='#fee2e2').pack()
    return frame


def show_crisis(gui, crisis, parent=None):
    """Show the crisis contacts at once, in a window of their own."""
    if not crisis:
        return None
    win = dialog(gui, _t('gui.pastoral.student_support.common.crisis_window',
                         default="Help is available now"), 760, 460)
    try:
        win.transient(parent or gui.root)
    except tk.TclError:
        pass
    crisis_banner(win, crisis).pack(fill='both', expand=True, padx=12, pady=12)
    ttk.Label(win, text=_t('gui.pastoral.student_support.common.crisis_followup',
                           default="Your message has been passed to the wellbeing team, who "
                                   "will contact you. These contacts are also shown on your "
                                   "ticket."), wraplength=700).pack(padx=12, anchor='w')
    ttk.Button(win, text=_t('gui.pastoral.student_support.common.close', default="Close"),
               command=win.destroy).pack(pady=10)
    win.lift()
    win.focus_force()
    return win


def tree_with_scroll(parent, columns, headings=None, widths=None, height=15,
                     selectmode='browse'):
    """A Treeview with a vertical scrollbar, packed to fill ``parent``."""
    frame = ttk.Frame(parent)
    frame.pack(fill='both', expand=True)
    tree = ttk.Treeview(frame, columns=columns, show='headings', height=height,
                        selectmode=selectmode)
    for col in columns:
        tree.heading(col, text=(headings or {}).get(col, col))
        tree.column(col, width=(widths or {}).get(col, 120), anchor='w')
    bar = ttk.Scrollbar(frame, orient='vertical', command=tree.yview)
    tree.configure(yscrollcommand=bar.set)
    bar.pack(side='right', fill='y')
    tree.pack(side='left', fill='both', expand=True)
    return tree


def export_tree_csv(gui, tree, default_name="tickets.csv"):
    """Save the rows the tree is showing, as shown, to a CSV file."""
    rows = [tree.item(i, 'values') for i in tree.get_children()]
    if not rows:
        messagebox.showinfo(_t('gui.pastoral.student_support.common.export', default="Export"),
                            _t('gui.pastoral.student_support.common.nothing_to_export',
                               default="There is nothing in the list to export."))
        return None
    path = filedialog.asksaveasfilename(
        title=_t('gui.pastoral.student_support.common.export_list', default="Export list"),
        defaultextension=".csv", initialfile=default_name,
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
    if not path:
        return None
    columns = tree['columns']
    with open(path, 'w', newline='', encoding='utf-8') as fh:
        writer = csv.writer(fh)
        writer.writerow([tree.heading(c, 'text') for c in columns])
        writer.writerows(rows)
    messagebox.showinfo(_t('gui.pastoral.student_support.common.export', default="Export"),
                        _t('gui.pastoral.student_support.common.exported_rows',
                           default="{count} rows saved to {path}").format(count=len(rows),
                                                                           path=path))
    return path


def write_xlsx(path, columns, rows, sheet="Export"):
    """Write ``rows`` under ``columns`` to an .xlsx workbook (openpyxl)."""
    from openpyxl import Workbook  # imported here: only the Excel export needs it
    from openpyxl.utils import get_column_letter

    book = Workbook()
    ws = book.active
    ws.title = sheet[:31]
    ws.append([str(c) for c in columns])
    for row in rows:
        ws.append([v if isinstance(v, (int, float)) or v is None else str(v) for v in row])
    for idx, col in enumerate(columns, 1):
        width = max([len(str(col))] + [len(str(r[idx - 1] or '')) for r in rows[:500]])
        ws.column_dimensions[get_column_letter(idx)].width = min(max(width + 2, 8), 60)
    ws.freeze_panes = "A2"
    book.save(path)


def team_assignees(team) -> list:
    """``[(username, label)]`` for whom a ticket of ``team`` can go to: the
    team's members and the duty officers, with their open load and capacity."""
    routing = ss('routing')
    with ss('store').reading() as conn:
        members = routing.team_members(team, conn) | routing.duty_officers(conn)
        caps = {c['username']: c for c in routing.capacity(conn, team)}
        load = routing.open_load(conn, members)
    out = []
    for name in sorted(members):
        cap = caps.get(name)
        if cap:
            text = f"{name} ({cap['open']}/{cap['max']} open)"
        else:
            text = f"{name} ({load.get(name, 0)} open)"
        out.append((name, text))
    return out


__all__ = [
    'ss', 'actor', 'username', 'role', 'is_admin', 'is_support_staff', 'is_case_worker',
    'can_work', 'can_see_internal', 'has_permission', 'can_manage_users', 'can_manage_team',
    'run', 'status_label', 'status_choices', 'status_value', 'category_label', 'team_label',
    'categories', 'priorities', 'tier_of', 'tier_label', 'is_sensitive_category', 'sla_state',
    'sla_text', 'sla_colour', 'dialog', 'tier_badge', 'crisis_banner', 'show_crisis',
    'tree_with_scroll', 'export_tree_csv', 'write_xlsx', 'team_assignees', 'SENSITIVE_HINT',
]
