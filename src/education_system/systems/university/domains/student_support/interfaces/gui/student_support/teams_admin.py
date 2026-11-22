"""Teams admin: who is in each support team, who leads it, each member's
capacity and auto-assign flag, and the duty officer rota.

Changes go through ``routing.set_member`` / ``routing.remove_member``
(administrators and the team's leads; audited). The duty rota is the
``duty`` team: its members are the duty officers who can take any team's
tickets.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

from education_system.systems.university.infrastructure.i18n import get_text as _t

from . import common as _c
from ._dialogs import messagebox

logger = logging.getLogger(__name__)


class TeamsAdminMixin:
    """Mixin for StudentSupportGUI: the Teams screen."""

    def show_teams_admin(self):
        self.clear_content()
        self.set_view('teams')
        frame = ttk.Frame(self.notebook, padding="5")
        self.notebook.add(frame, text=_t('gui.pastoral.student_support.teams.tabs.teams', default="👥 Teams"))
        if not self.is_admin():
            ttk.Label(frame, text=_t('gui.pastoral.student_support.teams.labels.admin_only', default="❌ Administrators only"),
                      style='Title.TLabel').pack(pady=20)
            return

        ttk.Label(frame, text=_t('gui.pastoral.student_support.teams.labels.title', default="👥 Support teams"), style='Title.TLabel').pack(anchor="w")
        ttk.Label(frame, foreground=self.colors['text_secondary'], wraplength=1000,
                  text=_t('gui.pastoral.student_support.teams.labels.explain', default="New tickets go to the team of their category and are given to the least-loaded member with auto-assign on and room under their capacity. Leads hear about service-level breaches. Duty officers can take any team's tickets.")).pack(anchor="w", pady=(0, 8))

        body = ttk.Frame(frame)
        body.pack(fill="both", expand=True)
        left = ttk.Frame(body)
        left.pack(side="left", fill="y", padx=(0, 10))
        ttk.Label(left, text=_t('gui.pastoral.student_support.teams.labels.teams', default="Teams"), style='Heading.TLabel').pack(anchor="w")
        self.teams_list = tk.Listbox(left, width=34, height=18, exportselection=False)
        self.teams_list.pack(fill="y", expand=True)
        routing = _c.ss('routing')
        self._team_keys = [t['key'] for t in routing.teams()] + [routing.DUTY_TEAM]
        for key in self._team_keys:
            label = _c.team_label(key)
            if key == routing.DUTY_TEAM:
                label = _t('gui.pastoral.student_support.teams.values.duty_rota', default="{label} (duty rota)").format(label=label)
            self.teams_list.insert(tk.END, label)
        self.teams_list.bind('<<ListboxSelect>>', lambda e: self.refresh_teams_admin())

        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)
        bar = ttk.Frame(right)
        bar.pack(side="bottom", fill="x", pady=(8, 0))
        ttk.Button(bar, text=_t('gui.pastoral.student_support.teams.buttons.add', default="➕ Add member…"),
                   command=lambda: self._edit_member(None)).pack(side="left")
        ttk.Button(bar, text=_t('gui.pastoral.student_support.teams.buttons.edit', default="✏️ Edit selected…"),
                   command=self._edit_selected_member).pack(side="left", padx=5)
        ttk.Button(bar, text=_t('gui.pastoral.student_support.teams.buttons.remove', default="➖ Remove selected"),
                   command=self._remove_selected_member).pack(side="left")
        self.team_heading = ttk.Label(right, style='Heading.TLabel')
        self.team_heading.pack(anchor="w")
        self.team_info = ttk.Label(right, foreground=self.colors['text_secondary'])
        self.team_info.pack(anchor="w", pady=(0, 6))
        self.members_tree = _c.tree_with_scroll(
            right, ('username', 'open', 'max', 'available', 'auto', 'lead'),
            {'username': 'Member', 'open': 'Open tickets', 'max': 'Capacity', 'available': 'Available',
             'auto': 'Auto-assign', 'lead': 'Lead'},
            {'username': 200, 'open': 100, 'max': 90, 'available': 90, 'auto': 100, 'lead': 140},
            height=16)
        self.members_tree.bind('<Double-1>', lambda e: self._edit_selected_member())
        self.teams_list.selection_set(0)
        self.refresh_teams_admin()

    def _selected_team(self):
        sel = self.teams_list.curselection() if getattr(self, 'teams_list', None) else ()
        return self._team_keys[sel[0]] if sel else None

    def refresh_teams_admin(self):
        team = self._selected_team()
        if not team or not self.members_tree.winfo_exists():
            return
        routing = _c.ss('routing')
        routing.clear_cache()
        with _c.ss('store').reading() as conn:
            rows = {r['username']: r for r in routing.capacity(conn, team)}
            members = routing.team_members(team, conn)
            dept = routing.team_department(team, conn) or {}
            load = routing.open_load(conn, members)
        self.team_heading.config(text=_c.team_label(team))
        info = []
        if dept.get('name'):
            info.append(f"Department: {dept['name']}")
        if dept.get('manager'):
            info.append(f"Manager: {dept['manager']}")
        if dept.get('email'):
            info.append(f"Inbox: {dept['email']}")
        self.team_info.config(text="   ".join(info) or _t('gui.pastoral.student_support.teams.labels.no_department', default="No department record"))
        self.members_tree.delete(*self.members_tree.get_children())
        for name in sorted(members | set(rows)):
            r = rows.get(name)
            if r:
                lead = 'yes' if r.get('lead') else ('manager' if name == dept.get('manager') else '')
                values = (name, r['open'], r['max'], r['available'],
                          'yes' if r.get('auto_assign') else 'no', lead)
            else:
                # The department's manager, not (yet) a member row.
                values = (name, load.get(name, 0), '—', '—', 'no', 'manager')
            self.members_tree.insert('', 'end', iid=name, values=values)

    def _support_staff_usernames(self):
        roles = sorted(set(_c.ss('auth').SUPPORT_ROLES) | set(_c.ss('auth').ADMIN_ROLES))
        marks = ", ".join("?" * len(roles))
        with _c.ss('store').reading() as conn:
            return [r[0] for r in conn.execute(
                f"SELECT username FROM users WHERE lower(role) IN ({marks}) "  # nosec B608 - placeholders only
                "ORDER BY username", roles).fetchall()]

    def _edit_selected_member(self):
        sel = self.members_tree.selection()
        if not sel:
            messagebox.showinfo(_t('gui.pastoral.student_support.teams.dialogs.members', default="Team members"),
                                _t('gui.pastoral.student_support.teams.dialogs.select_member', default="Select a member first."))
            return
        self._edit_member(sel[0])

    def _edit_member(self, username):
        team = self._selected_team()
        if not team:
            return
        values = self.members_tree.item(username, 'values') if username else None
        win = _c.dialog(self, _t('gui.pastoral.student_support.teams.windows.member', default="{team} — member").format(team=_c.team_label(team)), 560, 360, modal=True)
        form = ttk.Frame(win, padding=15)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text=_t('gui.pastoral.student_support.teams.labels.member', default="Member:")).grid(row=0, column=0, sticky="w", pady=4)
        try:
            names = self._support_staff_usernames()
        except Exception:
            logger.warning("Support staff list unavailable", exc_info=True)
            names = []
        who = ttk.Combobox(form, values=names, width=30, state="readonly" if username is None else "disabled")
        who.set(username or '')
        who.grid(row=0, column=1, sticky="w", pady=4)
        ttk.Label(form, text=_t('gui.pastoral.student_support.teams.labels.capacity', default="Capacity (open tickets):")).grid(row=1, column=0, sticky="w", pady=4)
        current_max = values[2] if values and str(values[2]).isdigit() else 10
        capacity = tk.Spinbox(form, from_=0, to=200, width=6)
        capacity.delete(0, tk.END)
        capacity.insert(0, str(current_max))
        capacity.grid(row=1, column=1, sticky="w", pady=4)
        auto = tk.BooleanVar(value=(values[4] == 'yes') if values else True)
        ttk.Checkbutton(form, text=_t('gui.pastoral.student_support.teams.buttons.auto_assign', default="Give new tickets automatically"), variable=auto).grid(row=2, column=1, sticky="w", pady=4)
        lead = tk.BooleanVar(value=(values[5] == 'yes') if values else False)
        ttk.Checkbutton(form, text=_t('gui.pastoral.student_support.teams.buttons.lead', default="Team lead (hears about breaches, can manage the team)"), variable=lead).grid(row=3, column=1, sticky="w", pady=4)

        def save():
            name = who.get().strip()
            if not name:
                messagebox.showerror(_t('gui.pastoral.student_support.teams.dialogs.members', default="Team members"),
                                     _t('gui.pastoral.student_support.teams.dialogs.choose_member', default="Choose a member of staff."), parent=win)
                return
            try:
                cap = int(capacity.get())
            except ValueError:
                messagebox.showerror(_t('gui.pastoral.student_support.teams.dialogs.members', default="Team members"),
                                     _t('gui.pastoral.student_support.teams.dialogs.capacity_number', default="Capacity must be a whole number."), parent=win)
                return
            if _c.run(win, _c.ss('routing').set_member, _c.actor(self), team, name,
                      max_concurrent=cap, auto_assign=auto.get(), lead=lead.get()):
                win.destroy()
                self.refresh_teams_admin()

        bar = ttk.Frame(form)
        bar.grid(row=4, column=0, columnspan=2, sticky="w", pady=(15, 0))
        ttk.Button(bar, text=_t('gui.pastoral.student_support.teams.buttons.save', default="Save"), command=save).pack(side="left")
        ttk.Button(bar, text=_t('gui.pastoral.student_support.teams.buttons.cancel', default="Cancel"), command=win.destroy).pack(side="left", padx=8)

    def _remove_selected_member(self):
        team = self._selected_team()
        sel = self.members_tree.selection()
        if not team or not sel:
            messagebox.showinfo(_t('gui.pastoral.student_support.teams.dialogs.members', default="Team members"),
                                _t('gui.pastoral.student_support.teams.dialogs.select_member', default="Select a member first."))
            return
        name = sel[0]
        if not messagebox.askyesno(_t('gui.pastoral.student_support.teams.dialogs.remove', default="Remove member"),
                                   _t('gui.pastoral.student_support.teams.dialogs.remove_confirm', default="Take {who} out of {team}? Their tickets stay with them.").format(
                                       who=name, team=_c.team_label(team))):
            return
        removed = _c.run(None, _c.ss('routing').remove_member, _c.actor(self), team, name)
        if removed is False:
            messagebox.showinfo(_t('gui.pastoral.student_support.teams.dialogs.remove', default="Remove member"),
                                _t('gui.pastoral.student_support.teams.dialogs.not_member_row', default="{who} leads this team through its department record, not as a member, so there is nothing to remove here.").format(who=name))
        self.refresh_teams_admin()
