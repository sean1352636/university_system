"""Caseload screens for support staff: my caseload by SLA urgency, the team
queue of unassigned tickets (with Take), team capacity, and the Student 360
view of one student's contacts with support services.

Everything comes from the domain — ``caseload.my_caseload / team_queue /
capacity / take / set_capacity`` and ``history360.contacts_for_student`` —
which apply the team and confidentiality rules; these screens show only
what those return.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

from education_system.systems.university.infrastructure.i18n import get_text as _t

from . import common as _c
from ._dialogs import messagebox, simpledialog

logger = logging.getLogger(__name__)

_CASE_COLUMNS = ('ID', 'Subject', 'Category', 'Team', 'Priority', 'Status', 'Tier', 'Assigned',
                 'Next due', 'Hours left')
_CASE_WIDTHS = {'ID': 55, 'Subject': 260, 'Category': 150, 'Team': 130, 'Priority': 75,
                'Status': 120, 'Tier': 90, 'Assigned': 90, 'Next due': 130, 'Hours left': 80}


class CaseloadMixin:
    """Mixin for StudentSupportGUI: the caseload tab and Student 360."""

    def show_caseload(self):
        self.clear_content()
        self.set_view('caseload')
        frame = ttk.Frame(self.notebook, padding="5")
        self.notebook.add(frame, text=_t('gui.pastoral.student_support.caseload.tabs.caseload', default="🗂️ My Caseload"))
        if not self.is_staff():
            ttk.Label(frame, text=_t('gui.pastoral.student_support.caseload.labels.staff_only', default="❌ Staff access required"),
                      style='Title.TLabel').pack(pady=20)
            return

        header = ttk.Frame(frame)
        header.pack(fill="x", pady=(0, 8))
        ttk.Label(header, text=_t('gui.pastoral.student_support.caseload.labels.title', default="🗂️ Caseload"), style='Title.TLabel').pack(side="left")
        ttk.Button(header, text=_t('gui.pastoral.student_support.caseload.buttons.refresh', default="🔄 Refresh"),
                   command=self.refresh_caseload).pack(side="right")
        ttk.Button(header, text=_t('gui.pastoral.student_support.caseload.buttons.student_360', default="🧭 Student 360…"),
                   command=lambda: self.show_student_360(None)).pack(side="right", padx=5)
        legend = ttk.Frame(frame)
        legend.pack(fill="x")
        for text, bg in (("past its service level", "#fee2e2"), ("due within 4 hours", "#fef3c7")):
            tk.Label(legend, text=f" {text} ", bg=bg).pack(side="left", padx=(0, 6))

        tabs = ttk.Notebook(frame)
        tabs.pack(fill="both", expand=True, pady=(6, 0))

        # My caseload
        mine = ttk.Frame(tabs, padding=6)
        tabs.add(mine, text=_t('gui.pastoral.student_support.caseload.tabs.mine', default="Mine (most urgent first)"))
        bar = ttk.Frame(mine)
        bar.pack(fill="x", pady=(0, 6))
        self.caseload_waiting_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text=_t('gui.pastoral.student_support.caseload.buttons.include_waiting', default="Include tickets waiting on the student"),
                        variable=self.caseload_waiting_var, command=self.refresh_caseload).pack(side="left")
        ttk.Button(bar, text=_t('gui.pastoral.student_support.caseload.buttons.export_csv', default="⬇️ Export CSV"),
                   command=lambda: _c.export_tree_csv(self, self.caseload_tree, "my_caseload.csv")).pack(side="right")
        self.caseload_message = ttk.Label(mine, foreground=self.colors['text_secondary'])
        self.caseload_message.pack(anchor="w")
        self.caseload_tree = self._case_tree(mine)

        # Team queue
        queue = ttk.Frame(tabs, padding=6)
        tabs.add(queue, text=_t('gui.pastoral.student_support.caseload.tabs.queue', default="Team queue (unassigned)"))
        qbar = ttk.Frame(queue)
        qbar.pack(fill="x", pady=(0, 6))
        ttk.Label(qbar, text=_t('gui.pastoral.student_support.caseload.labels.team', default="Team:")).pack(side="left")
        routing = _c.ss('routing')
        if self.is_admin():
            teams = [t['key'] for t in routing.teams()]
        else:
            teams = sorted(routing.user_teams(_c.username(self)))
        self._queue_teams = {_c.team_label(t): t for t in teams}
        self.queue_team_combo = ttk.Combobox(qbar, state="readonly", width=30,
                                             values=[_t('gui.pastoral.student_support.caseload.values.all_my_teams', default="All my teams")] + list(self._queue_teams))
        self.queue_team_combo.current(0)
        self.queue_team_combo.pack(side="left", padx=5)
        self.queue_team_combo.bind('<<ComboboxSelected>>', lambda e: self.refresh_caseload())
        ttk.Button(qbar, text=_t('gui.pastoral.student_support.caseload.buttons.take', default="✋ Take selected"),
                   command=self._take_from_queue).pack(side="left", padx=10)
        self.queue_message = ttk.Label(queue, foreground=self.colors['text_secondary'])
        self.queue_message.pack(anchor="w")
        self.queue_tree = self._case_tree(queue)

        # Capacity
        cap = ttk.Frame(tabs, padding=6)
        tabs.add(cap, text=_t('gui.pastoral.student_support.caseload.tabs.capacity', default="Capacity"))
        cbar = ttk.Frame(cap)
        cbar.pack(fill="x", pady=(0, 6))
        ttk.Button(cbar, text=_t('gui.pastoral.student_support.caseload.buttons.set_capacity', default="Set capacity of selected…"),
                   command=self._set_capacity).pack(side="left")
        self.capacity_message = ttk.Label(cap, foreground=self.colors['text_secondary'])
        self.capacity_message.pack(anchor="w")
        self.capacity_tree = _c.tree_with_scroll(
            cap, ('username', 'team', 'open', 'max', 'available', 'auto', 'lead'),
            {'username': 'Adviser', 'team': 'Team', 'open': 'Open', 'max': 'Capacity',
             'available': 'Available', 'auto': 'Auto-assign', 'lead': 'Lead'},
            {'username': 150, 'team': 220, 'open': 70, 'max': 80, 'available': 80, 'auto': 90,
             'lead': 60}, height=16)
        self.refresh_caseload()

    def _case_tree(self, parent):
        tree = _c.tree_with_scroll(parent, _CASE_COLUMNS, widths=_CASE_WIDTHS, height=18)
        tree.tag_configure('breached', background='#fee2e2')
        tree.tag_configure('warning', background='#fef3c7')
        tree.bind('<Double-1>', lambda e: self.on_ticket_double_click(tree))
        tree.bind('<Return>', lambda e: self.on_ticket_double_click(tree))
        return tree

    def _fill_case_tree(self, tree, items):
        tree.delete(*tree.get_children())
        for item in items:
            hours = item.get('hours_left')
            tag = 'breached' if item.get('breached') else ''
            if not tag and hours is not None and 0 <= hours <= 4:
                tag = 'warning'
            tree.insert('', 'end', tags=(tag,) if tag else (), values=(
                item['ticket_id'], item.get('subject') or '', item.get('category') or '',
                item.get('team_label') or '', item.get('priority') or '',
                item.get('status_label') or '', _c.tier_label(item.get('confidentiality') or 'standard'),
                item.get('assigned_to') or '', item.get('next_due') or '',
                '' if hours is None else f"{hours:.1f}"))

    def _load(self, label, fn, *args, **kwargs):
        """Call a caseload function; a refusal is shown on ``label``."""
        try:
            label.config(text='')
            return fn(*args, **kwargs)
        except (PermissionError, ValueError) as exc:
            label.config(text=str(exc))
        except Exception as exc:
            logger.exception("Caseload view failed")
            label.config(text=f"Could not load: {exc}")
        return None

    def refresh_caseload(self):
        if not getattr(self, 'caseload_tree', None) or not self.caseload_tree.winfo_exists():
            return
        caseload = _c.ss('caseload')
        me = _c.actor(self)
        mine = self._load(self.caseload_message, caseload.my_caseload, me,
                          include_waiting=self.caseload_waiting_var.get())
        self._fill_case_tree(self.caseload_tree, mine or [])
        if mine is not None:
            breached = sum(1 for m in mine if m.get('breached'))
            self.caseload_message.config(text=f"{len(mine)} active ticket(s), {breached} past their service level")

        team = self._queue_teams.get(self.queue_team_combo.get())
        queue = self._load(self.queue_message, caseload.team_queue, me, team)
        self._fill_case_tree(self.queue_tree, queue or [])
        if queue is not None and not self.queue_message.cget('text'):
            self.queue_message.config(text=f"{len(queue)} unassigned ticket(s)")

        caps = self._load(self.capacity_message, caseload.capacity, me)
        self.capacity_tree.delete(*self.capacity_tree.get_children())
        for c in caps or []:
            self.capacity_tree.insert('', 'end', values=(
                c['username'], c.get('team_label') or c['team'], c['open'], c['max'], c['available'],
                'yes' if c.get('auto_assign') else 'no', 'yes' if c.get('lead') else ''))
        self.update_status(_t('gui.pastoral.student_support.caseload.status.loaded', default="Caseload loaded"))

    def _take_from_queue(self):
        sel = self.queue_tree.selection()
        if not sel:
            messagebox.showinfo(_t('gui.pastoral.student_support.caseload.dialogs.take', default="Take ticket"),
                                _t('gui.pastoral.student_support.caseload.dialogs.select_first', default="Select a ticket in the queue first."))
            return
        ticket_id = self.queue_tree.item(sel[0], 'values')[0]
        if _c.run(None, _c.ss('caseload').take, _c.actor(self), ticket_id):
            self.update_status(f"Ticket #{ticket_id} taken")
            self.refresh_caseload()

    def _set_capacity(self):
        sel = self.capacity_tree.selection()
        if not sel:
            messagebox.showinfo(_t('gui.pastoral.student_support.caseload.dialogs.capacity', default="Capacity"),
                                _t('gui.pastoral.student_support.caseload.dialogs.select_adviser', default="Select an adviser first."))
            return
        username, team_label, _open, current = self.capacity_tree.item(sel[0], 'values')[:4]
        team = _c.ss('routing').team_key(team_label) or team_label
        value = simpledialog.askinteger(
            _t('gui.pastoral.student_support.caseload.dialogs.capacity', default="Capacity"),
            _t('gui.pastoral.student_support.caseload.dialogs.capacity_for', default="Most open tickets for {who} in {team}:").format(who=username, team=team_label),
            initialvalue=int(current), minvalue=0, maxvalue=200)
        if value is None:
            return
        if _c.run(None, _c.ss('caseload').set_capacity, _c.actor(self), username, value, team):
            self.refresh_caseload()

    # ── Student 360 ──────────────────────────────────────────────────────

    def show_student_360(self, student_id=None):
        """A student's contacts with support services, newest first — only
        what ``history360.contacts_for_student`` returns for this viewer."""
        if not _c.is_support_staff(self):
            messagebox.showwarning(_t('gui.pastoral.student_support.caseload.dialogs.not_allowed', default="Not allowed"),
                                   _t('gui.pastoral.student_support.caseload.dialogs.support_only', default="Only support staff can see a student's support history."))
            return
        if not student_id:
            student_id = simpledialog.askstring(_t('gui.pastoral.student_support.caseload.windows.student_360', default="Student 360"),
                                                _t('gui.pastoral.student_support.caseload.dialogs.which_student', default="Student number:"))
            if not student_id or not student_id.strip():
                return
            student_id = student_id.strip()
        items = _c.run(None, _c.ss('history360').contacts_for_student, _c.actor(self), student_id)
        if items is None:
            return
        win = _c.dialog(self, _t('gui.pastoral.student_support.caseload.windows.student_360_for', default="Student 360 — {student}").format(student=student_id), 1200, 700)
        bar = ttk.Frame(win, padding=8)
        bar.pack(side="bottom", fill="x")
        ttk.Label(win, text=_t('gui.pastoral.student_support.caseload.labels.contacts', default="{count} contact(s) you may see, newest first. Double-click a ticket to open it.").format(count=len(items)),
                  padding=8).pack(anchor="w")
        tree = _c.tree_with_scroll(win, ('date', 'source', 'kind', 'id', 'status', 'title', 'more'),
                                   {'date': 'Date', 'source': 'Service', 'kind': 'Type', 'id': 'Ref',
                                    'status': 'Status', 'title': 'Title', 'more': 'Details'},
                                   {'date': 140, 'source': 150, 'kind': 90, 'id': 70, 'status': 120,
                                    'title': 330, 'more': 260}, height=20)
        refs = {}
        for item in items:
            extra = {k: v for k, v in item.items()
                     if k not in ('source', 'kind', 'id', 'date', 'status', 'title') and v}
            more = ", ".join(f"{k.replace('_', ' ')}: {v}" for k, v in extra.items())
            iid = tree.insert('', 'end', values=(item['date'][:16], item['source'].replace('_', ' ').title(),
                                                 item['kind'], item['id'], item.get('status') or '',
                                                 item.get('title') or '', more))
            if item['kind'] == 'ticket':
                refs[iid] = item['id']

        def open_item(_e=None):
            sel = tree.selection()
            if sel and sel[0] in refs:
                self.view_ticket_details(refs[sel[0]])

        tree.bind('<Double-1>', open_item)
        ttk.Button(bar, text=_t('gui.pastoral.student_support.caseload.buttons.export_csv', default="⬇️ Export CSV"),
                   command=lambda: _c.export_tree_csv(self, tree, f"student_360_{student_id}.csv")).pack(side="left")
        ttk.Button(bar, text=_t('gui.pastoral.student_support.caseload.buttons.close', default="Close"),
                   command=win.destroy).pack(side="right")
