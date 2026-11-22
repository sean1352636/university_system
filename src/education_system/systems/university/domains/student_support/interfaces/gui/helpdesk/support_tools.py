"""Support tool windows shared by the Helpdesk and Student Support screens.

Each function opens one window over ``parent`` for the signed-in ``actor``
(an auth ``current_user`` dict) and does everything through the support
services, which check permission themselves:

* :func:`open_links`, :func:`open_time`, :func:`open_followers` — a ticket's
  links, time log and followers (``student_support.collaboration``);
* :func:`add_to_incident` — put a ticket into an open incident, or declare a
  new one for it;
* :func:`open_incidents` — the major incidents: declare, attach tickets,
  post an update to every ticket, monitor, resolve them all;
* :func:`open_known_issues` — what everyone sees: the open incidents, with
  "I'm affected" (raises the person's own ticket, attached);
* :func:`open_mail_quarantine` — support e-mail that could not be matched:
  read, raise a ticket for the right person, or discard;
* :func:`open_automation_settings` — auto-close, the SLA pause and e-mail
  into tickets (administrators).
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, scrolledtext, simpledialog, ttk

from education_system.systems.university.infrastructure.i18n import get_text as _t

logger = logging.getLogger(__name__)

_PKG = "education_system.systems.university.domains.student_support.domain.student_support"


def _mod(name):
    import importlib
    return importlib.import_module(f"{_PKG}.{name}")


def _error(exc, parent) -> None:
    title = _t('gui.pastoral.helpdesk.dialogs.error', default="Error")
    if isinstance(exc, PermissionError):
        title = _t('gui.pastoral.helpdesk.dialogs.permission_denied', default="Permission Denied")
    elif not isinstance(exc, (ValueError, FileNotFoundError)):
        logger.exception("Support tool action failed", exc_info=exc)
    messagebox.showerror(title, str(exc), parent=parent)


def _run(parent, fn, *args, **kwargs):
    """``fn(*args, **kwargs)``, or None after showing why it failed."""
    try:
        return fn(*args, **kwargs)
    except Exception as exc:          # every failure is shown to the user
        _error(exc, parent)
        return None


def _window(parent, title, width=900, height=600, big=False):
    win = tk.Toplevel(parent)
    win.title(title)
    if big:
        from education_system.platform.delivery.gui import window_sizing
        window_sizing.install()
        window_sizing.center(win, 1400, 900, minsize=(1200, 800))
    else:
        win.geometry(f"{width}x{height}")
    try:
        win.transient(parent.winfo_toplevel())
    except tk.TclError:
        pass
    return win


def _tree(parent, columns, height=12):
    frame = ttk.Frame(parent)
    tree = ttk.Treeview(frame, columns=[c[0] for c in columns], show='headings',
                        height=height, selectmode='browse')
    for key, label, width in columns:
        tree.heading(key, text=label)
        tree.column(key, width=width, anchor='w')
    bar = ttk.Scrollbar(frame, orient='vertical', command=tree.yview)
    tree.configure(yscrollcommand=bar.set)
    tree.pack(side='left', fill='both', expand=True)
    bar.pack(side='right', fill='y')
    return frame, tree


def _selected(tree, parent, what="an item"):
    sel = tree.selection()
    if not sel:
        messagebox.showinfo(_t('gui.pastoral.helpdesk.dialogs.select', default="Select"),
                            f"Select {what} first.", parent=parent)
        return None
    return sel[0]


def _text_dialog(parent, title, prompt, initial='') -> str | None:
    """A multi-line text prompt; None when cancelled."""
    win = tk.Toplevel(parent)
    win.title(title)
    win.geometry("640x360")
    win.transient(parent.winfo_toplevel())
    ttk.Label(win, text=prompt, wraplength=600, justify='left').pack(anchor='w', padx=10,
                                                                    pady=(10, 4))
    bar = ttk.Frame(win, padding=8)
    bar.pack(side='bottom', fill='x')
    box = scrolledtext.ScrolledText(win, wrap='word', height=10)
    box.pack(fill='both', expand=True, padx=10)
    box.insert('1.0', initial)
    result = {'text': None}

    def done():
        result['text'] = box.get('1.0', 'end').strip()
        win.destroy()
    ttk.Button(bar, text=_t('common.ok', default="OK"), command=done).pack(side='right')
    ttk.Button(bar, text=_t('common.cancel', default="Cancel"),
               command=win.destroy).pack(side='right', padx=6)
    box.focus_set()
    win.grab_set()
    win.wait_window()
    return result['text']


# ── a ticket's links ────────────────────────────────────────────────────


def link_dialog(parent, actor, ticket_id, on_done=None) -> None:
    """Link this ticket to another (both ways)."""
    collab = _mod('collaboration')
    win = tk.Toplevel(parent)
    win.title(f"Link Ticket #{ticket_id}")
    win.geometry("420x330")
    win.transient(parent.winfo_toplevel())
    frame = ttk.Frame(win, padding=10)
    frame.pack(fill='both', expand=True)
    ttk.Label(frame, text="Ticket ID to link:").grid(row=0, column=0, sticky='w', pady=5)
    other = tk.StringVar()
    ttk.Entry(frame, textvariable=other, width=20).grid(row=0, column=1, sticky='w', padx=5)
    ttk.Label(frame, text="Link type:").grid(row=1, column=0, sticky='nw', pady=5)
    kind = tk.StringVar(value='related_to')
    types = ttk.Frame(frame)
    types.grid(row=1, column=1, sticky='w', padx=5)
    for i, key in enumerate(('related_to', 'duplicate_of', 'blocks', 'blocked_by',
                             'parent_of', 'child_of')):
        ttk.Radiobutton(types, text=collab.LINK_LABELS[key], variable=kind,
                        value=key).grid(row=i, column=0, sticky='w')

    def save():
        result = _run(win, collab.link_tickets, actor, ticket_id, other.get().strip().lstrip('#'),
                      kind.get())
        if result is None:
            return
        if not result['created']:
            messagebox.showinfo("Link", "Those tickets were already linked that way.", parent=win)
        win.destroy()
        if on_done:
            on_done()
    bar = ttk.Frame(frame)
    bar.grid(row=2, column=0, columnspan=2, pady=10)
    ttk.Button(bar, text="Link", command=save).pack(side='left', padx=5)
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side='left', padx=5)


def open_links(parent, actor, ticket_id, open_ticket=None) -> None:
    """A ticket's links, with Link / Unlink (and Open, given ``open_ticket``)."""
    collab = _mod('collaboration')
    win = _window(parent, f"Linked tickets — #{ticket_id}", 860, 420)
    bar = ttk.Frame(win, padding=8)
    bar.pack(side='bottom', fill='x')
    frame, tree = _tree(win, (('ticket', 'Ticket', 90), ('type', 'Link', 140),
                              ('subject', 'Subject', 420), ('status', 'Status', 140)))
    frame.pack(fill='both', expand=True, padx=10, pady=10)

    def load():
        links = _run(win, collab.list_links, actor, ticket_id)
        tree.delete(*tree.get_children())
        for link in links or []:
            tree.insert('', 'end', iid=f"{link['ticket_id']}:{link['link_type']}", values=(
                f"#{link['ticket_id']}", link['label'],
                link['subject'] if link['visible'] else "(not available to you)",
                link['status'] or ''))

    def unlink():
        iid = _selected(tree, win, "a link")
        if iid and messagebox.askyesno("Unlink", "Remove the link between these tickets?",
                                       parent=win):
            _run(win, collab.unlink_tickets, actor, ticket_id, iid.split(':')[0])
            load()

    def open_selected():
        iid = _selected(tree, win, "a ticket")
        if iid and open_ticket:
            open_ticket(int(iid.split(':')[0]))
    ttk.Button(bar, text="Link Ticket…", command=lambda: link_dialog(win, actor, ticket_id,
                                                                     load)).pack(side='left')
    ttk.Button(bar, text="Unlink", command=unlink).pack(side='left', padx=6)
    if open_ticket:
        ttk.Button(bar, text="Open", command=open_selected).pack(side='left')
    ttk.Button(bar, text="Close", command=win.destroy).pack(side='right')
    load()


# ── a ticket's time ─────────────────────────────────────────────────────


def time_dialog(parent, actor, ticket_id, on_done=None) -> None:
    """Record time spent on a ticket (hours, as the Helpdesk always asked)."""
    collab = _mod('collaboration')
    win = tk.Toplevel(parent)
    win.title(f"Add Time Entry - Ticket #{ticket_id}")
    win.geometry("420x300")
    win.transient(parent.winfo_toplevel())
    frame = ttk.Frame(win, padding=10)
    frame.pack(fill='both', expand=True)
    ttk.Label(frame, text="Duration (hours):").grid(row=0, column=0, sticky='w', pady=5)
    hours = tk.StringVar(value="1.0")
    ttk.Entry(frame, textvariable=hours, width=20).grid(row=0, column=1, sticky='w', padx=5)
    ttk.Label(frame, text="Description:").grid(row=1, column=0, sticky='nw', pady=5)
    desc = scrolledtext.ScrolledText(frame, wrap='word', width=30, height=5)
    desc.grid(row=1, column=1, padx=5, pady=5)
    billable = tk.BooleanVar(value=False)
    ttk.Checkbutton(frame, text="Billable", variable=billable).grid(row=2, column=1, sticky='w')

    def save():
        try:
            minutes = float(hours.get()) * 60
        except ValueError:
            messagebox.showerror("Validation Error", "Please enter a valid number for duration.",
                                 parent=win)
            return
        result = _run(win, collab.log_time, actor, ticket_id, minutes,
                      desc.get('1.0', 'end').strip(), billable=billable.get())
        if result is None:
            return
        messagebox.showinfo("Success", f"Time entry added. Total on this ticket: "
                                       f"{result['total_minutes'] / 60:.2f} hours", parent=win)
        win.destroy()
        if on_done:
            on_done()
    bar = ttk.Frame(frame)
    bar.grid(row=3, column=0, columnspan=2, pady=10)
    ttk.Button(bar, text="Save", command=save).pack(side='left', padx=5)
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side='left', padx=5)


def open_time(parent, actor, ticket_id) -> None:
    """A ticket's time log, with Add and Remove."""
    collab = _mod('collaboration')
    win = _window(parent, f"Time spent — #{ticket_id}", 820, 420)
    bar = ttk.Frame(win, padding=8)
    bar.pack(side='bottom', fill='x')
    total = ttk.Label(bar, text="")
    total.pack(side='left', padx=(0, 12))
    frame, tree = _tree(win, (('when', 'When', 150), ('who', 'Who', 120),
                              ('minutes', 'Minutes', 80), ('billable', 'Billable', 70),
                              ('note', 'Description', 360)))
    frame.pack(fill='both', expand=True, padx=10, pady=10)

    def load():
        data = _run(win, collab.time_entries, actor, ticket_id) or {'entries': [],
                                                                    'total_minutes': 0}
        tree.delete(*tree.get_children())
        for e in data['entries']:
            tree.insert('', 'end', iid=str(e['time_id']), values=(
                e['created_at'], e['username'] or '', e['duration_minutes'],
                'Yes' if e['billable'] else '', e['description'] or ''))
        total.config(text=f"Total: {data['total_minutes'] / 60:.2f} hours")

    def remove():
        iid = _selected(tree, win, "an entry")
        if iid and messagebox.askyesno("Remove", "Remove this time entry?", parent=win):
            _run(win, collab.delete_time_entry, actor, int(iid))
            load()
    ttk.Button(bar, text="Add Time…", command=lambda: time_dialog(win, actor, ticket_id,
                                                                  load)).pack(side='left')
    ttk.Button(bar, text="Remove", command=remove).pack(side='left', padx=6)
    ttk.Button(bar, text="Close", command=win.destroy).pack(side='right')
    load()


# ── a ticket's followers ────────────────────────────────────────────────


def open_followers(parent, actor, ticket_id) -> None:
    """Who follows a ticket: Follow / Unfollow yourself, add or remove others."""
    collab = _mod('collaboration')
    me = (_mod('auth').user_of(actor) or {}).get('username')
    win = _window(parent, f"Followers — #{ticket_id}", 640, 400)
    ttk.Label(win, text="Followers are told about this ticket's replies, internal notes and "
                        "status changes. Only staff who can already see the ticket can follow it.",
              wraplength=600, justify='left').pack(anchor='w', padx=10, pady=(10, 0))
    bar = ttk.Frame(win, padding=8)
    bar.pack(side='bottom', fill='x')
    frame, tree = _tree(win, (('who', 'Follower', 160), ('by', 'Added by', 140),
                              ('when', 'Since', 160)), height=8)
    frame.pack(fill='both', expand=True, padx=10, pady=10)

    def load():
        tree.delete(*tree.get_children())
        for f in _run(win, collab.list_followers, actor, ticket_id) or []:
            tree.insert('', 'end', iid=f['username'],
                        values=(f['username'], f['added_by'], f['added_at']))

    def add():
        name = simpledialog.askstring("Add follower", "Username of the member of staff:",
                                      parent=win)
        if name and _run(win, collab.add_follower, actor, ticket_id, name.strip()) is not None:
            load()

    def remove():
        iid = _selected(tree, win, "a follower")
        if iid:
            _run(win, collab.remove_follower, actor, ticket_id, iid)
            load()
    ttk.Button(bar, text="Follow", command=lambda: (_run(win, collab.add_follower, actor,
                                                         ticket_id, me), load())
               ).pack(side='left')
    ttk.Button(bar, text="Unfollow", command=lambda: (_run(win, collab.remove_follower, actor,
                                                           ticket_id, me), load())
               ).pack(side='left', padx=6)
    ttk.Button(bar, text="Add…", command=add).pack(side='left')
    ttk.Button(bar, text="Remove", command=remove).pack(side='left', padx=6)
    ttk.Button(bar, text="Close", command=win.destroy).pack(side='right')
    load()


def open_followed(parent, actor, open_ticket=None) -> None:
    """The tickets the signed-in person follows."""
    collab = _mod('collaboration')
    win = _window(parent, "Tickets I follow", 900, 480)
    bar = ttk.Frame(win, padding=8)
    bar.pack(side='bottom', fill='x')
    frame, tree = _tree(win, (('id', 'Ticket', 80), ('subject', 'Subject', 380),
                              ('status', 'Status', 130), ('priority', 'Priority', 90),
                              ('assigned', 'Assigned to', 120)))
    frame.pack(fill='both', expand=True, padx=10, pady=10)
    for t in _run(win, collab.followed_tickets, actor) or []:
        tree.insert('', 'end', iid=str(t['ticket_id']), values=(
            f"#{t['ticket_id']}", t['subject'], t['status'], t['priority'] or '',
            t['assigned_to'] or ''))

    def open_selected():
        iid = _selected(tree, win, "a ticket")
        if iid and open_ticket:
            open_ticket(int(iid))
    if open_ticket:
        ttk.Button(bar, text="Open", command=open_selected).pack(side='left')
        tree.bind('<Double-1>', lambda _e: open_selected())
    ttk.Button(bar, text="Close", command=win.destroy).pack(side='right')


# ── incidents ───────────────────────────────────────────────────────────


def _incident_form(parent, title, *, ask_tickets=True, initial_tickets=''):
    """Title / description / public message / team / severity / tickets."""
    routing = _mod('routing')
    incidents = _mod('incidents')
    win = tk.Toplevel(parent)
    win.title(title)
    win.geometry("720x560")
    win.transient(parent.winfo_toplevel())
    frame = ttk.Frame(win, padding=10)
    frame.pack(fill='both', expand=True)
    frame.columnconfigure(1, weight=1)
    v = {k: tk.StringVar() for k in ('title', 'team', 'severity', 'tickets')}
    v['severity'].set('major')
    v['tickets'].set(initial_tickets)
    ttk.Label(frame, text="Title (everyone sees it):").grid(row=0, column=0, sticky='w', pady=4)
    ttk.Entry(frame, textvariable=v['title']).grid(row=0, column=1, sticky='ew', padx=5)
    ttk.Label(frame, text="Team:").grid(row=1, column=0, sticky='w', pady=4)
    teams = [''] + [routing.team_label(k) for k in routing.TEAMS]
    ttk.Combobox(frame, textvariable=v['team'], values=teams, state='readonly',
                 width=34).grid(row=1, column=1, sticky='w', padx=5)
    ttk.Label(frame, text="Severity:").grid(row=2, column=0, sticky='w', pady=4)
    ttk.Combobox(frame, textvariable=v['severity'], values=list(incidents.SEVERITIES),
                 state='readonly', width=12).grid(row=2, column=1, sticky='w', padx=5)
    ttk.Label(frame, text="Public message\n(shown to affected people):").grid(
        row=3, column=0, sticky='nw', pady=4)
    public = scrolledtext.ScrolledText(frame, wrap='word', height=5)
    public.grid(row=3, column=1, sticky='ew', padx=5)
    ttk.Label(frame, text="Internal description:").grid(row=4, column=0, sticky='nw', pady=4)
    desc = scrolledtext.ScrolledText(frame, wrap='word', height=5)
    desc.grid(row=4, column=1, sticky='ew', padx=5)
    if ask_tickets:
        ttk.Label(frame, text="Tickets (e.g. 12, 15, 18):").grid(row=5, column=0, sticky='w',
                                                                 pady=4)
        ttk.Entry(frame, textvariable=v['tickets']).grid(row=5, column=1, sticky='ew', padx=5)
    out = {}

    def ok():
        label = v['team'].get()
        team = next((k for k in routing.TEAMS if routing.team_label(k) == label), None)
        out.update(title=v['title'].get(), team=team, severity=v['severity'].get(),
                   public_message=public.get('1.0', 'end').strip(),
                   description=desc.get('1.0', 'end').strip(),
                   ticket_ids=[t for t in v['tickets'].get().replace(',', ' ').split() if t])
        win.destroy()
    bar = ttk.Frame(frame)
    bar.grid(row=6, column=0, columnspan=2, pady=10)
    ttk.Button(bar, text="Declare", command=ok).pack(side='left', padx=5)
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side='left', padx=5)
    win.grab_set()
    win.wait_window()
    return out or None


def _skipped_text(skipped) -> str:
    return "\n".join(f"#{tid}: {why}" for tid, why in sorted(skipped.items()))


def declare_incident(parent, actor, ticket_ids=()) -> int | None:
    """Ask for the incident's details and declare it; returns its number."""
    incidents = _mod('incidents')
    form = _incident_form(parent, "Declare a major incident",
                          initial_tickets=", ".join(str(t) for t in ticket_ids))
    if not form:
        return None
    result = _run(parent, incidents.declare, actor, form['title'], form['description'],
                  public_message=form['public_message'], team=form['team'],
                  severity=form['severity'], ticket_ids=form['ticket_ids'])
    if result is None:
        return None
    text = (f"Incident #{result['incident_id']} declared; "
            f"{result['attached']} ticket(s) attached.")
    if result['skipped']:
        text += "\n\nNot attached:\n" + _skipped_text(result['skipped'])
    messagebox.showinfo("Incident", text, parent=parent)
    return result['incident_id']


def add_to_incident(parent, actor, ticket_id) -> None:
    """Put a ticket into an open incident, or declare a new one for it."""
    incidents = _mod('incidents')
    open_ones = _run(parent, incidents.list_incidents, actor, ['open', 'monitoring'])
    if open_ones is None:
        return
    win = tk.Toplevel(parent)
    win.title(f"Add ticket #{ticket_id} to an incident")
    win.geometry("760x380")
    win.transient(parent.winfo_toplevel())
    bar = ttk.Frame(win, padding=8)
    bar.pack(side='bottom', fill='x')
    frame, tree = _tree(win, (('id', 'Incident', 80), ('title', 'Title', 380),
                              ('status', 'Status', 110), ('tickets', 'Tickets', 80)), height=8)
    frame.pack(fill='both', expand=True, padx=10, pady=10)
    for i in open_ones:
        tree.insert('', 'end', iid=str(i['incident_id']), values=(
            f"#{i['incident_id']}", i['title'], i['status_label'], i['tickets']))

    def attach():
        iid = _selected(tree, win, "an incident")
        if not iid:
            return
        result = _run(win, incidents.attach, actor, int(iid), [ticket_id])
        if result is None:
            return
        if result['skipped']:
            messagebox.showwarning("Not attached", _skipped_text(result['skipped']), parent=win)
            return
        messagebox.showinfo("Incident", f"Ticket #{ticket_id} is now part of incident #{iid}.",
                            parent=win)
        win.destroy()

    def new():
        win.destroy()
        declare_incident(parent, actor, [ticket_id])
    ttk.Button(bar, text="Add to selected", command=attach).pack(side='left')
    ttk.Button(bar, text="Declare new incident…", command=new).pack(side='left', padx=6)
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side='right')


def open_incidents(parent, actor, open_ticket=None) -> None:
    """The major incidents window (support staff)."""
    incidents = _mod('incidents')
    win = _window(parent, "Major Incidents", big=True)
    top = ttk.Frame(win, padding=(10, 8))
    top.pack(fill='x')
    ttk.Label(top, text="Major Incidents", font=('Arial', 16, 'bold')).pack(side='left')
    show = tk.StringVar(value='Active')
    ttk.Label(top, text="Show:").pack(side='left', padx=(20, 4))
    ttk.Combobox(top, textvariable=show, values=['Active', 'Resolved', 'All'], state='readonly',
                 width=10).pack(side='left')
    bar = ttk.Frame(win, padding=8)
    bar.pack(side='bottom', fill='x')
    panes = ttk.PanedWindow(win, orient='vertical')
    panes.pack(fill='both', expand=True, padx=10, pady=5)
    upper, tree = _tree(panes, (('id', 'Incident', 80), ('title', 'Title', 420),
                                ('severity', 'Severity', 90), ('status', 'Status', 110),
                                ('open', 'Open tickets', 100), ('tickets', 'All tickets', 90),
                                ('since', 'Declared', 150), ('by', 'By', 110)), height=10)
    panes.add(upper, weight=1)
    lower = ttk.LabelFrame(panes, text="Selected incident", padding=6)
    panes.add(lower, weight=1)
    detail = ttk.Label(lower, text="", wraplength=1200, justify='left')
    detail.pack(anchor='w')
    tframe, tickets = _tree(lower, (('id', 'Ticket', 80), ('subject', 'Subject', 420),
                                    ('status', 'Status', 130), ('requester', 'Requester', 130),
                                    ('assigned', 'Assigned to', 120)), height=8)
    tframe.pack(fill='both', expand=True, pady=(6, 0))

    def current():
        sel = tree.selection()
        return int(sel[0]) if sel else None

    def load(select=None):
        wanted = {'Active': ['open', 'monitoring'], 'Resolved': ['resolved'],
                  'All': None}[show.get()]
        rows = _run(win, incidents.list_incidents, actor, wanted) or []
        tree.delete(*tree.get_children())
        for i in rows:
            tree.insert('', 'end', iid=str(i['incident_id']), values=(
                f"#{i['incident_id']}", i['title'], i['severity'], i['status_label'],
                i['open_tickets'], i['tickets'], i['created_at'], i['created_by']))
        if select and tree.exists(str(select)):
            tree.selection_set(str(select))
        show_detail()

    def show_detail(_e=None):
        tickets.delete(*tickets.get_children())
        iid = current()
        if iid is None:
            detail.config(text="")
            return
        inc = _run(win, incidents.get_incident, actor, iid)
        if inc is None:
            return
        text = f"#{inc['incident_id']} {inc['title']} — {inc['status_label']}"
        if inc.get('public_message'):
            text += f"\nPublic message: {inc['public_message']}"
        if inc.get('description'):
            text += f"\nInternal: {inc['description']}"
        if inc.get('resolution'):
            text += f"\nResolution: {inc['resolution']}"
        detail.config(text=text)
        for t in inc['tickets']:
            tickets.insert('', 'end', iid=str(t['ticket_id']), values=(
                f"#{t['ticket_id']}", t['subject'], t['status'], t['requester'] or '',
                t['assigned_to'] or ''))

    def need():
        iid = current()
        if iid is None:
            messagebox.showinfo("Select", "Select an incident first.", parent=win)
        return iid

    def declare():
        new = declare_incident(win, actor)
        if new:
            show.set('Active')
            load(new)

    def attach():
        iid = need()
        if iid is None:
            return
        text = simpledialog.askstring("Attach tickets", "Ticket numbers (e.g. 12, 15, 18):",
                                      parent=win)
        if not text:
            return
        result = _run(win, incidents.attach, actor, iid, text.replace(',', ' ').split())
        if result is None:
            return
        msg = f"{result['attached']} ticket(s) attached."
        if result['skipped']:
            msg += "\n\nNot attached:\n" + _skipped_text(result['skipped'])
        messagebox.showinfo("Attach", msg, parent=win)
        load(iid)

    def detach():
        iid, sel = need(), tickets.selection()
        if iid is None or not sel:
            return
        _run(win, incidents.detach, actor, iid, int(sel[0]))
        load(iid)

    def update():
        iid = need()
        if iid is None:
            return
        text = _text_dialog(win, "Post an update",
                            "This update is posted as a reply on every open ticket of the "
                            "incident, and becomes its public message.")
        if text:
            count = _run(win, incidents.post_update, actor, iid, text)
            if count is not None:
                messagebox.showinfo("Update", f"Update posted to {count} ticket(s).", parent=win)
                load(iid)

    def monitoring():
        iid = need()
        if iid is not None:
            _run(win, incidents.set_status, actor, iid, 'monitoring')
            load(iid)

    def reopen():
        iid = need()
        if iid is not None:
            _run(win, incidents.set_status, actor, iid, 'open')
            load(iid)

    def resolve():
        iid = need()
        if iid is None:
            return
        text = _text_dialog(win, "Resolve incident",
                            "The resolution is sent to everyone on the incident's open tickets, "
                            "and each ticket is resolved.")
        if text:
            result = _run(win, incidents.resolve, actor, iid, text)
            if result is not None:
                msg = f"{result['resolved']} ticket(s) resolved."
                if result['skipped']:
                    msg += ("\n\nLeft open (you are not working them): "
                            + ", ".join(f"#{t}" for t in result['skipped']))
                messagebox.showinfo("Resolved", msg, parent=win)
                load(iid)

    def open_selected(_e=None):
        sel = tickets.selection()
        if sel and open_ticket:
            open_ticket(int(sel[0]))
    tree.bind('<<TreeviewSelect>>', show_detail)
    show.trace_add('write', lambda *_: load())
    for label, cmd in (("Declare…", declare), ("Attach Tickets…", attach),
                       ("Detach Ticket", detach), ("Post Update…", update),
                       ("Monitoring", monitoring), ("Reopen", reopen), ("Resolve…", resolve)):
        ttk.Button(bar, text=label, command=cmd).pack(side='left', padx=(0, 6))
    if open_ticket:
        ttk.Button(bar, text="Open Ticket", command=open_selected).pack(side='left')
        tickets.bind('<Double-1>', open_selected)
    ttk.Button(bar, text="Close", command=win.destroy).pack(side='right')
    ttk.Button(bar, text="Refresh", command=lambda: load(current())).pack(side='right', padx=6)
    load()


def known_issues_frame(parent, actor, on_reported=None):
    """A frame listing the open incidents with "I'm affected" — or None when
    there are none (the caller shows nothing)."""
    incidents = _mod('incidents')
    try:
        issues = incidents.known_issues(actor)
    except Exception:
        logger.debug("Known issues unavailable", exc_info=True)
        return None
    if not issues:
        return None
    box = ttk.LabelFrame(parent, text="Known issues right now", padding=8)
    for issue in issues:
        row = ttk.Frame(box)
        row.pack(fill='x', pady=2)
        text = issue['title'] + (f" — {issue['public_message']}" if issue['public_message'] else "")
        ttk.Label(row, text=text, wraplength=900, justify='left').pack(side='left', fill='x',
                                                                       expand=True)

        def affected(iid=issue['incident_id']):
            details = _text_dialog(parent, "I'm affected",
                                   "Tell us anything that will help (optional). You'll be "
                                   "updated on this issue through your own ticket.")
            if details is None:
                return
            result = _run(parent, incidents.report_affected, actor, iid, details)
            if result is None:
                return
            if result.get('crisis'):
                messagebox.showwarning("Support is available now",
                                       result['crisis'].get('message', ''), parent=parent)
            msg = (f"You already have ticket #{result['ticket_id']} for this issue."
                   if result.get('existing') else
                   f"Thanks — your ticket #{result['ticket_id']} has been added to this issue.")
            messagebox.showinfo("Known issue", msg, parent=parent)
            if on_reported:
                on_reported(result['ticket_id'])
        ttk.Button(row, text="I'm affected", command=affected).pack(side='right', padx=4)
    return box


def open_known_issues(parent, actor, on_reported=None) -> None:
    """The open incidents as everyone sees them."""
    win = _window(parent, "Known Issues", 1000, 480)
    box = known_issues_frame(win, actor, on_reported)
    if box is None:
        ttk.Label(win, text="There are no known issues right now.",
                  font=('Arial', 12)).pack(padx=20, pady=20)
    else:
        box.pack(fill='both', expand=True, padx=10, pady=10)
    ttk.Button(win, text="Close", command=win.destroy).pack(side='bottom', anchor='e',
                                                            padx=10, pady=8)


# ── e-mail quarantine ───────────────────────────────────────────────────


def open_mail_quarantine(parent, actor) -> None:
    """Support e-mail that could not be matched to a person (support staff)."""
    email_in = _mod('email_in')
    win = _window(parent, "Support E-mail", big=True)
    top = ttk.Frame(win, padding=(10, 8))
    top.pack(fill='x')
    ttk.Label(top, text="Support E-mail", font=('Arial', 16, 'bold')).pack(side='left')
    show = tk.StringVar(value='quarantined')
    ttk.Label(top, text="Show:").pack(side='left', padx=(20, 4))
    ttk.Combobox(top, textvariable=show, state='readonly', width=14,
                 values=['quarantined', 'processed', 'ignored', 'accepted', 'discarded']
                 ).pack(side='left')
    ttk.Label(top, text=f"Unreviewed messages are discarded after {email_in.QUARANTINE_DAYS} days.",
              foreground='#555555').pack(side='left', padx=12)
    bar = ttk.Frame(win, padding=8)
    bar.pack(side='bottom', fill='x')
    panes = ttk.PanedWindow(win, orient='vertical')
    panes.pack(fill='both', expand=True, padx=10, pady=5)
    upper, tree = _tree(panes, (('id', '#', 60), ('when', 'Received', 150),
                                ('from', 'From', 240), ('subject', 'Subject', 380),
                                ('reason', 'Why', 360), ('ticket', 'Ticket', 80)), height=12)
    panes.add(upper, weight=1)
    lower = ttk.LabelFrame(panes, text="Message", padding=6)
    panes.add(lower, weight=1)
    body = scrolledtext.ScrolledText(lower, wrap='word', height=12, state='disabled')
    body.pack(fill='both', expand=True)

    def load():
        rows = _run(win, email_in.list_mail, actor, show.get()) or []
        tree.delete(*tree.get_children())
        for r in rows:
            tree.insert('', 'end', iid=str(r['mail_id']), values=(
                r['mail_id'], r['received_at'], r['from_address'] or '', r['subject'] or '',
                r['reason'] or '', f"#{r['ticket_id']}" if r['ticket_id'] else ''))
        _show('')

    def _show(text):
        body.config(state='normal')
        body.delete('1.0', 'end')
        body.insert('1.0', text)
        body.config(state='disabled')

    def read():
        iid = _selected(tree, win, "a message")
        if not iid:
            return None
        msg = _run(win, email_in.read_quarantined, actor, int(iid))
        if msg:
            head = (f"From: {msg['from']}\nTo: {msg['to']}\nDate: {msg['date']}\n"
                    f"Subject: {msg['subject']}\nWhy it is here: {msg['reason']}\n")
            if msg['attachments']:
                head += "Attachments: " + ", ".join(msg['attachments']) + "\n"
            if msg['suggested']:
                head += "Accounts with this address: " + ", ".join(msg['suggested']) + "\n"
            _show(head + "\n" + msg['text'])
        return msg

    def accept():
        iid = _selected(tree, win, "a message")
        if not iid:
            return
        msg = read()
        if not msg:
            return
        who = simpledialog.askstring(
            "Raise a ticket", "Raise a ticket for (username or student number):",
            initialvalue=(msg['suggested'] or [''])[0], parent=win)
        if not who:
            return
        result = _run(win, email_in.accept_quarantined, actor, int(iid), who.strip())
        if result:
            messagebox.showinfo("Ticket raised", f"Ticket #{result['ticket_id']} raised for {who}.",
                                parent=win)
            load()

    def discard():
        iid = _selected(tree, win, "a message")
        if not iid:
            return
        reason = simpledialog.askstring("Discard", "Why is it being discarded?", parent=win)
        if reason and _run(win, email_in.discard_quarantined, actor, int(iid), reason):
            load()
    show.trace_add('write', lambda *_: load())
    ttk.Button(bar, text="Read", command=read).pack(side='left')
    ttk.Button(bar, text="Raise Ticket For…", command=accept).pack(side='left', padx=6)
    ttk.Button(bar, text="Discard…", command=discard).pack(side='left')
    ttk.Button(bar, text="Check Mailbox Now", command=lambda: (_run(win, email_in.poll), load())
               ).pack(side='left', padx=6)
    ttk.Button(bar, text="Close", command=win.destroy).pack(side='right')
    load()


# ── automation settings ─────────────────────────────────────────────────


def automation_frame(parent, actor):
    """The automation settings as a frame with its own Save (administrators)."""
    settings = _mod('settings')
    frame = ttk.Frame(parent, padding=10)
    values = _run(parent, settings.automation) or dict(settings.DEFAULTS)
    v = {
        'auto_close_days': tk.StringVar(value=str(values['auto_close_days'])),
        'sla_pause_waiting': tk.BooleanVar(value=values['sla_pause_waiting']),
        'inbound_enabled': tk.BooleanVar(value=values['inbound_enabled']),
        'inbound_mode': tk.StringVar(value=values['inbound_mode']),
        'imap_host': tk.StringVar(value=values['imap_host']),
        'imap_port': tk.StringVar(value=str(values['imap_port'])),
        'imap_user': tk.StringVar(value=values['imap_user']),
        'imap_folder': tk.StringVar(value=values['imap_folder']),
        'support_address': tk.StringVar(value=values['support_address']),
    }
    row = 0

    def label(text):
        nonlocal row
        ttk.Label(frame, text=text).grid(row=row, column=0, sticky='w', pady=4)

    label("Close resolved tickets after (days, 0 = never):")
    ttk.Entry(frame, textvariable=v['auto_close_days'], width=8).grid(row=row, column=1, sticky='w')
    row += 1
    ttk.Checkbutton(frame, text="Pause the SLA while a ticket waits on the student",
                    variable=v['sla_pause_waiting']).grid(row=row, column=0, columnspan=2,
                                                          sticky='w', pady=4)
    row += 1
    ttk.Separator(frame).grid(row=row, column=0, columnspan=2, sticky='ew', pady=8)
    row += 1
    ttk.Checkbutton(frame, text="Turn e-mail into tickets", variable=v['inbound_enabled']
                    ).grid(row=row, column=0, columnspan=2, sticky='w', pady=4)
    row += 1
    label("Mailbox:")
    ttk.Combobox(frame, textvariable=v['inbound_mode'], values=list(settings.INBOUND_MODES),
                 state='readonly', width=10).grid(row=row, column=1, sticky='w')
    row += 1
    for key, text in (('support_address', "Support address:"), ('imap_host', "IMAP server:"),
                      ('imap_port', "IMAP port:"), ('imap_user', "IMAP user:"),
                      ('imap_folder', "IMAP folder:")):
        label(text)
        ttk.Entry(frame, textvariable=v[key], width=40).grid(row=row, column=1, sticky='w')
        row += 1
    ttk.Label(frame, text="Folder mode reads .eml files from the support inbound folder. "
                          "The IMAP password is not kept here: set SUPPORT_IMAP_PASSWORD or the "
                          "support_imap_password secret file.",
              foreground='#555555', wraplength=560, justify='left').grid(
        row=row, column=0, columnspan=2, sticky='w', pady=(4, 8))
    row += 1

    def save():
        changes = {k: var.get() for k, var in v.items()}
        if _run(frame, settings.update, actor, changes) is not None:
            messagebox.showinfo("Saved", "Support automation settings saved.", parent=frame)
    ttk.Button(frame, text="Save Automation Settings", command=save).grid(
        row=row, column=0, sticky='w')
    return frame


def open_automation_settings(parent, actor) -> None:
    win = _window(parent, "Support Automation", 680, 520)
    automation_frame(win, actor).pack(fill='both', expand=True)


__all__ = [
    'open_links', 'link_dialog', 'open_time', 'time_dialog', 'open_followers', 'open_followed',
    'add_to_incident', 'declare_incident', 'open_incidents', 'known_issues_frame',
    'open_known_issues', 'open_mail_quarantine', 'automation_frame', 'open_automation_settings',
]
