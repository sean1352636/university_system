import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from education_system.systems.university.infrastructure.email.template_utils import render_template
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from education_system.systems.university.infrastructure.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.systems.university.infrastructure.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.UNIVERSITY_DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        LOW_BALANCE_THRESHOLD
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False
    print("Warning: Student finance account integration not available")

try:
    # Import CLI components to maintain backwards compatibility. If available,
    # include the full database initializer so the GUI can create the
    # comprehensive schema when running stand‑alone.
    from education_system.systems.university.infrastructure.database.db import get_connection
    from education_system.systems.university.domains.student_life.domain.student_life.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False



from education_system.systems.university.domains.student_life.domain.student_life.student_union.services import (
    interclub,
)
from education_system.systems.university.domains.student_life.interfaces.gui.student_union_gui.core import (
    su_records,
)

_C = "student_union.competitions"


class InterClubCompetitionsDialog:
    """Main dialog for inter-club competitions"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t(f"{_C}.dialog_title", default="Inter-Club Competitions"))
        self.dialog.geometry("1000x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text="🏆 " + _t(f"{_C}.interclub_header", default="Inter-Club Competitions"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Action buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(0, 15))

        ttk.Button(button_frame, text=_t(f"{_C}.view_active", default="View Active Competitions"),
                  command=self.view_active).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_t(f"{_C}.view_results", default="View Results"),
                  command=self.view_results).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_t(f"{_C}.create_competition_admin", default="Create Competition (Admin)"),
                  command=self.create_competition).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_t(f"{_C}.update_scores_admin", default="Update Scores (Admin)"),
                  command=self.update_scores).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Refresh", command=self.load_overview).pack(side='right', padx=5)

        ttk.Button(main_frame, text=_t(f"{_C}.close", default="Close"), command=self.dialog.destroy).pack(side='bottom')

        # Competitions display
        display_frame = ttk.LabelFrame(main_frame, text=_t(f"{_C}.overview_label", default="Overview"))
        display_frame.pack(fill='both', expand=True, pady=(0, 15))

        self.comp_text = scrolledtext.ScrolledText(display_frame, wrap=tk.WORD, height=25)
        self.comp_text.pack(fill='both', expand=True, padx=5, pady=5)

        self.load_overview()

    def load_overview(self):
        self.comp_text.delete(1.0, tk.END)
        try:
            with su_records.db() as conn:
                comps = interclub.list_competitions(conn, include_finished=True)
                table = interclub.standings(conn)
        except Exception as e:
            self.comp_text.insert(1.0, f"Could not load competitions: {e}")
            return

        open_comps = [c for c in comps if str(c.get('status') or 'upcoming').lower() not in interclub.FINISHED]
        done = [c for c in comps if str(c.get('status') or '').lower() == 'completed']
        lines = ["INTER-CLUB COMPETITIONS", "=" * 40, ""]
        if not comps:
            lines.append("No competitions have been set up yet."
                         + (" Use 'Create Competition' to add one." if su_records.is_staff(self.auth) else ""))
        else:
            lines.append(f"🏅 Open and upcoming ({len(open_comps)})")
            for c in open_comps:
                when = " – ".join(d for d in (c.get('start_date'), c.get('end_date')) if d) or "dates TBC"
                lines.append(f"  • {c['competition_name']} [{c.get('competition_type') or 'General'}] "
                             f"{when} — {c['clubs_entered']} club(s) entered, status {c.get('status') or 'upcoming'}")
            if not open_comps:
                lines.append("  (none)")
            lines += ["", f"✅ Completed ({len(done)})"]
            for c in done:
                lines.append(f"  • {c['competition_name']} — {c['clubs_entered']} club(s)")
            if not done:
                lines.append("  (none)")

        lines += ["", "📊 Overall club standings (by placings)"]
        ranked = [s for s in table if (s['gold'] or s['silver'] or s['bronze'])]
        if not ranked:
            lines.append("  No ranked results have been recorded yet.")
        for i, s in enumerate(ranked, 1):
            lines.append(f"  {i}. {s['club_name']} — 🥇{s['gold']} 🥈{s['silver']} 🥉{s['bronze']} "
                         f"({s['entered']} competition(s) entered)")
        self.comp_text.insert(1.0, "\n".join(lines))

    def _staff_only(self):
        if su_records.is_staff(self.auth):
            return True
        messagebox.showwarning("Staff only", "Only Student Union staff can do this.", parent=self.dialog)
        return False

    def view_active(self):
        dialog = ActiveCompetitionsDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)
        self.load_overview()

    def view_results(self):
        dialog = ActiveCompetitionsDialog(self.dialog, self.auth, include_finished=True)
        self.dialog.wait_window(dialog.dialog)

    def create_competition(self):
        if not self._staff_only():
            return
        from education_system.systems.university.domains.student_life.interfaces.gui.student_union_gui.competitions.competition_admin import CreateCompetitionDialog
        dialog = CreateCompetitionDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)
        self.load_overview()

    def update_scores(self):
        if not self._staff_only():
            return
        from education_system.systems.university.domains.student_life.interfaces.gui.student_union_gui.competitions.competition_admin import UpdateCompetitionScoresDialog
        dialog = UpdateCompetitionScoresDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)
        self.load_overview()



class ActiveCompetitionsDialog:
    """Dialog for viewing competitions (open ones, or all with include_finished)"""

    def __init__(self, parent, auth_manager, include_finished=False):
        self.parent = parent
        self.auth = auth_manager
        self.include_finished = include_finished
        self._rows = {}

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t(f"{_C}.active_title", default="Competitions"))
        self.dialog.geometry("1000x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_competitions()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text=_t(f"{_C}.active_title", default="Competitions"), font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(side='bottom', fill='x')

        ttk.Button(button_frame, text=_t(f"{_C}.register_club", default="Register Club"), command=self.register_club).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t(f"{_C}.view_standings", default="View Standings"), command=self.view_standings).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t(f"{_C}.close", default="Close"), command=self.dialog.destroy).pack(side='right')

        # Details frame
        details_frame = ttk.LabelFrame(main_frame, text=_t(f"{_C}.competition_details", default="Competition Details"))
        details_frame.pack(side='bottom', fill='x', pady=(0, 15))

        self.details_text = scrolledtext.ScrolledText(details_frame, height=8, wrap=tk.WORD)
        self.details_text.pack(fill='both', expand=True, padx=5, pady=5)

        # Competitions list
        list_frame = ttk.LabelFrame(main_frame, text=_t(f"{_C}.available_competitions", default="Competitions"))
        list_frame.pack(fill='both', expand=True, pady=(0, 15))

        columns = ('ID', 'Name', 'Type', 'Start Date', 'End Date', 'Clubs Entered', 'Status')
        self.comp_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)

        for col in columns:
            self.comp_tree.heading(col, text=col)
            self.comp_tree.column(col, width=200 if col == 'Name' else 100)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.comp_tree.yview)
        self.comp_tree.configure(yscrollcommand=scrollbar.set)

        self.comp_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self.comp_tree.bind('<<TreeviewSelect>>', self.on_select)

    def load_competitions(self):
        for item in self.comp_tree.get_children():
            self.comp_tree.delete(item)
        self._rows = {}
        try:
            with su_records.db() as conn:
                rows = interclub.list_competitions(conn, include_finished=self.include_finished)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load competitions:\n{e}", parent=self.dialog)
            return
        self.details_text.delete(1.0, tk.END)
        if not rows:
            self.details_text.insert(1.0, "No competitions to show yet.")
        for c in rows:
            iid = str(c['competition_id'])
            limit = c.get('max_participants_per_club')
            self.comp_tree.insert('', 'end', iid=iid, values=(
                c['competition_id'], c['competition_name'], c.get('competition_type') or '',
                c.get('start_date') or 'TBC', c.get('end_date') or 'TBC', c['clubs_entered'],
                str(c.get('status') or 'upcoming').replace('_', ' ').title()))
            self._rows[iid] = c

    def _selected(self):
        sel = self.comp_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Please select a competition first.", parent=self.dialog)
            return None
        return self._rows.get(sel[0])

    def on_select(self, event):
        sel = self.comp_tree.selection()
        if not sel:
            return
        c = self._rows.get(sel[0])
        if not c:
            return
        try:
            with su_records.db() as conn:
                ents = interclub.entries(conn, c['competition_id'])
        except Exception:
            ents = []
        lines = [c['competition_name'], ""]
        for label, key in (("Type", 'competition_type'), ("Starts", 'start_date'), ("Ends", 'end_date'),
                           ("Registration deadline", 'registration_deadline'),
                           ("Max members per club", 'max_participants_per_club'),
                           ("Prizes", 'prizes'), ("Status", 'status')):
            if c.get(key) not in (None, ''):
                lines.append(f"{label}: {c[key]}")
        if c.get('description'):
            lines += ["", c['description']]
        if c.get('rules'):
            lines += ["", "Rules:", c['rules']]
        lines += ["", f"Entered clubs ({len(ents)}):"]
        for e in ents:
            team = f" — team '{e['team_name']}'" if e.get('team_name') else ""
            members = f": {e['members']}" if e.get('members') else ""
            lines.append(f"  • {e['club_name'] or 'Club ' + str(e['club_id'])}{team}{members}")
        if not ents:
            lines.append("  (none yet)")
        self.details_text.delete(1.0, tk.END)
        self.details_text.insert(1.0, "\n".join(lines))

    def register_club(self):
        c = self._selected()
        if not c:
            return
        dialog = RegisterClubCompetitionDialog(self.dialog, self.auth, c['competition_id'], c['competition_name'])
        self.dialog.wait_window(dialog.dialog)
        if dialog.registered:
            self.load_competitions()

    def view_standings(self):
        c = self._selected()
        if not c:
            return
        from education_system.systems.university.domains.student_life.interfaces.gui.student_union_gui.competitions.competition_results import CompetitionResultsDialog
        dialog = CompetitionResultsDialog(self.dialog, self.auth, c['competition_id'])
        self.dialog.wait_window(dialog.dialog)



class RegisterClubCompetitionDialog:
    """Dialog for registering a club for a competition"""

    def __init__(self, parent, auth_manager, competition_id, competition_name=""):
        self.parent = parent
        self.auth = auth_manager
        self.competition_id = competition_id
        self.competition_name = competition_name
        self.registered = False
        self._clubs = {}
        self._members = []

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t(f"{_C}.register_club_title", default="Register Club"))
        self.dialog.geometry("700x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_clubs()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(main_frame, text=f"Register a club: {self.competition_name}",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Club selection
        ttk.Label(main_frame, text=_t(f"{_C}.register_dialog.select_club", default="Select club:")).pack(anchor='w', pady=(0, 5))
        self.club_combo = ttk.Combobox(main_frame, width=50, state='readonly')
        self.club_combo.pack(fill='x', pady=(0, 15))
        self.club_combo.bind('<<ComboboxSelected>>', self.load_members)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(side='bottom', fill='x')

        ttk.Button(button_frame, text=_t(f"{_C}.register_dialog.register", default="Register"), command=self.register).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t(f"{_C}.register_dialog.cancel", default="Cancel"), command=self.dialog.destroy).pack(side='left')

        # Team name
        self.team_entry = ttk.Entry(main_frame, width=50)
        self.team_entry.pack(side='bottom', fill='x', pady=(0, 15))
        ttk.Label(main_frame, text=_t(f"{_C}.register_dialog.team_name", default="Team name (optional):")).pack(side='bottom', anchor='w', pady=(0, 5))

        # Participant selection
        self.members_label = ttk.Label(main_frame, text=_t(f"{_C}.register_dialog.select_team_members", default="Select team members:"))
        self.members_label.pack(anchor='w', pady=(0, 5))

        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill='both', expand=True, pady=(0, 15))

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side='right', fill='y')

        self.members_listbox = tk.Listbox(list_frame, selectmode=tk.MULTIPLE, yscrollcommand=scrollbar.set, height=10)
        self.members_listbox.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=self.members_listbox.yview)

    def load_clubs(self):
        try:
            with su_records.db() as conn:
                owner = su_records.owner_id(conn, self.auth)
                clubs = interclub.clubs_for(conn, owner, staff=su_records.is_staff(self.auth))
        except Exception as e:
            messagebox.showerror("Error", f"Could not load clubs:\n{e}", parent=self.dialog)
            return
        self._clubs = {f"{c['club_name']} (ID: {c['club_id']})": c['club_id'] for c in clubs}
        self.club_combo['values'] = list(self._clubs)
        if clubs:
            self.club_combo.current(0)
            self.load_members()
        else:
            self.members_label.config(text="You are not a member of any active club, so there is no club to enter.")

    def load_members(self, event=None):
        self.members_listbox.delete(0, tk.END)
        club_id = self._clubs.get(self.club_combo.get())
        if club_id is None:
            return
        try:
            with su_records.db() as conn:
                self._members = interclub.club_members(conn, club_id)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load club members:\n{e}", parent=self.dialog)
            return
        for m in self._members:
            role = f" — {m['role']}" if m.get('role') else ""
            self.members_listbox.insert(tk.END, f"{m['name']} ({m['student_id']}){role}")
        if not self._members:
            self.members_label.config(text="This club has no members on record; it will be entered as a club.")
        else:
            self.members_label.config(text=_t(f"{_C}.register_dialog.select_team_members", default="Select team members:"))

    def register(self):
        club_id = self._clubs.get(self.club_combo.get())
        if club_id is None:
            messagebox.showwarning("Warning", "Please select a club.", parent=self.dialog)
            return
        selected = [self._members[i]['student_id'] for i in self.members_listbox.curselection()]
        try:
            with su_records.db() as conn:
                count = interclub.register_entry(conn, self.competition_id, club_id, selected,
                                                 self.team_entry.get())
        except ValueError as e:
            messagebox.showwarning("Warning", str(e), parent=self.dialog)
            return
        except Exception as e:
            messagebox.showerror("Error", f"Could not register the club:\n{e}", parent=self.dialog)
            return
        self.registered = True
        who = f"{len(selected)} team member(s)" if selected else "the club"
        messagebox.showinfo("Success", f"Registered {who} for {self.competition_name}.", parent=self.dialog)
        self.dialog.destroy()


# ============================================================================
# COMMUNITY ENGAGEMENT DIALOGS
# ============================================================================


def open_interclub_competitions_dialog(self):
    """Open inter-club competitions dialog"""
    dialog = InterClubCompetitionsDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)
