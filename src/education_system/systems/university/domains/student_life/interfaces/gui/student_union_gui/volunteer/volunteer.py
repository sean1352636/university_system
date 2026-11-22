
from education_system.systems.university.infrastructure.i18n import get_text as _t
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
from education_system.systems.university.domains.student_life.interfaces.gui.student_union_gui.analytics.analytics import (
    EngagementTrendAnalysisDialog, MemberRetentionInsightsDialog
)

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
    volunteering_records as vol,
)
from education_system.systems.university.domains.student_life.interfaces.gui.student_union_gui.core import (
    su_records,
)

_K = 'gui.pastoral.student_union_gui.volunteer.volunteer'


def _fmt_hours(value) -> str:
    try:
        return f"{float(value):g}"
    except (TypeError, ValueError):
        return "—"


class VolunteerOpportunitiesDialog:
    """Dialog for browsing volunteer opportunities (read from volunteer_opportunities)"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager
        self.staff = su_records.is_staff(auth_manager)
        self._rows = {}

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t(f'{_K}.windows.volunteer_opportunities', default="Volunteer Opportunities"))
        self.dialog.geometry("1000x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_opportunities()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text=_t(f'{_K}.labels.volunteer_opportunities', default="🌟 Volunteer Opportunities"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Filter frame
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(filter_frame, text=_t(f'{_K}.labels.category', default="Category:")).pack(side='left', padx=(0, 5))
        self.category_var = tk.StringVar()
        category_combo = ttk.Combobox(filter_frame, textvariable=self.category_var, width=20, state='readonly')
        category_combo['values'] = ('All',) + vol.CATEGORIES
        category_combo.current(0)
        category_combo.pack(side='left', padx=(0, 15))

        self.show_closed_var = tk.BooleanVar(value=False)
        if self.staff:
            ttk.Checkbutton(filter_frame, text="Include closed", variable=self.show_closed_var,
                            command=self.load_opportunities).pack(side='left', padx=(0, 15))

        ttk.Button(filter_frame, text=_t(f'{_K}.buttons.filter', default="Filter"), command=self.load_opportunities).pack(side='left')

        # Buttons (packed before the expanding list so they stay visible)
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(side='bottom', fill='x')

        ttk.Button(button_frame, text=_t(f'{_K}.buttons.sign_up', default="Sign Up"), command=self.sign_up).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t(f'{_K}.buttons.my_activities', default="My Activities"), command=self.view_my_activities).pack(side='left', padx=(0, 10))
        if self.staff:
            ttk.Button(button_frame, text="New Opportunity", command=self.new_opportunity).pack(side='left', padx=(0, 10))
            ttk.Button(button_frame, text="Edit Opportunity", command=self.edit_opportunity).pack(side='left', padx=(0, 10))
            ttk.Button(button_frame, text="Verify Hours", command=self.review_hours).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t(f'{_K}.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='right')

        # Details frame
        details_frame = ttk.LabelFrame(main_frame, text=_t(f'{_K}.labels.opportunity_details', default="Opportunity Details"))
        details_frame.pack(side='bottom', fill='x', pady=(0, 10))

        self.details_text = scrolledtext.ScrolledText(details_frame, height=6, wrap=tk.WORD)
        self.details_text.pack(fill='both', expand=True, padx=5, pady=5)

        # Opportunities list
        list_frame = ttk.LabelFrame(main_frame, text=_t(f'{_K}.labels.available_opportunities', default="Available Opportunities"))
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('Organization', 'Description', 'Date', 'Hours', 'Spots', 'Status')
        self.opp_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)

        for col in columns:
            self.opp_tree.heading(col, text=col)
            if col == 'Description':
                self.opp_tree.column(col, width=250)
            elif col == 'Organization':
                self.opp_tree.column(col, width=150)
            else:
                self.opp_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.opp_tree.yview)
        self.opp_tree.configure(yscrollcommand=scrollbar.set)

        self.opp_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self.opp_tree.bind('<<TreeviewSelect>>', self.on_select)

    def load_opportunities(self):
        for item in self.opp_tree.get_children():
            self.opp_tree.delete(item)
        self._rows = {}
        self.details_text.delete(1.0, tk.END)

        try:
            with su_records.db() as conn:
                rows = vol.list_opportunities(conn, category=self.category_var.get() or None,
                                              include_closed=self.show_closed_var.get())
        except Exception as e:
            messagebox.showerror("Error", f"Could not load volunteer opportunities:\n{e}", parent=self.dialog)
            return

        if not rows:
            self.details_text.insert(1.0, "No volunteer opportunities are listed yet."
                                     + (" Use 'New Opportunity' to add one." if self.staff else
                                        " Check back later — the Student Union adds them as they come in."))
            return

        for r in rows:
            spots = (f"{r['signed_up']}/{r['max_volunteers']}" if r.get('max_volunteers')
                     else f"{r['signed_up']}/∞")
            iid = str(r['opportunity_id'])
            self.opp_tree.insert('', 'end', iid=iid, values=(
                r['organization_name'] or '', (r['description'] or '').splitlines()[0][:80] if r['description'] else '',
                r['start_date'] or 'Flexible', _fmt_hours(r['hours_required']), spots,
                (r['status'] or 'open').title()))
            self._rows[iid] = r

    def on_select(self, event):
        selection = self.opp_tree.selection()
        if not selection:
            return
        r = self._rows.get(selection[0])
        if not r:
            return
        lines = [r['organization_name'] or '', '', r['description'] or '', '']
        for label, key in (("Category", 'category'), ("Location", 'location'),
                           ("Starts", 'start_date'), ("Ends", 'end_date'),
                           ("Skills needed", 'skills_needed'), ("Contact", 'contact_person'),
                           ("Contact email", 'contact_email')):
            if r.get(key):
                lines.append(f"{label}: {r[key]}")
        self.details_text.delete(1.0, tk.END)
        self.details_text.insert(1.0, "\n".join(lines))

    def _selected(self):
        selection = self.opp_tree.selection()
        if not selection:
            messagebox.showwarning(_t(f'{_K}.dialogs.warning', default="Warning"), _t(f'{_K}.dialogs.please_select_an_opportunity', default="Please select an opportunity."), parent=self.dialog)
            return None
        return self._rows.get(selection[0])

    def sign_up(self):
        r = self._selected()
        if not r:
            return
        org = r['organization_name']
        if not messagebox.askyesno(_t(f'{_K}.dialogs.confirm', default="Confirm"), f"Sign up for volunteer opportunity with {org}?", parent=self.dialog):
            return
        try:
            with su_records.db() as conn:
                owner = su_records.owner_id(conn, self.auth)
                vol.sign_up(conn, r['opportunity_id'], owner)
                awarded = False
                try:
                    from education_system.systems.university.domains.student_life.domain.student_life.student_union.services.points import auto_award_points
                    awarded = auto_award_points(owner, "Community Service", 20,
                                                f"Signed up for volunteer opportunity: {org}",
                                                conn.cursor(), conn)
                except Exception:
                    awarded = False
        except ValueError as e:
            messagebox.showwarning(_t(f'{_K}.dialogs.warning', default="Warning"), str(e), parent=self.dialog)
            return
        except Exception as e:
            messagebox.showerror("Error", f"Could not sign you up:\n{e}", parent=self.dialog)
            return
        msg = f"You're signed up with {org}."
        if r.get('contact_email'):
            msg += f"\n\nThe organiser's contact is {r['contact_email']}."
        if awarded:
            msg += "\n\n+20 Community Service Points earned!"
        messagebox.showinfo(_t(f'{_K}.dialogs.success', default="Success"), msg, parent=self.dialog)
        self.load_opportunities()

    def view_my_activities(self):
        dialog = MyVolunteerActivitiesDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def new_opportunity(self):
        dialog = VolunteerOpportunityEditor(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)
        if dialog.saved:
            self.load_opportunities()

    def edit_opportunity(self):
        r = self._selected()
        if not r:
            return
        dialog = VolunteerOpportunityEditor(self.dialog, self.auth, r['opportunity_id'])
        self.dialog.wait_window(dialog.dialog)
        if dialog.saved:
            self.load_opportunities()

    def review_hours(self):
        dialog = VolunteerHoursReviewDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)


class VolunteerOpportunityEditor:
    """SU staff form to create or edit a volunteer opportunity"""

    FIELDS = (
        ("organization_name", "Organisation *"), ("description", "Description *"),
        ("category", "Category"), ("location", "Location"),
        ("start_date", "Start date (YYYY-MM-DD)"), ("end_date", "End date (YYYY-MM-DD)"),
        ("hours_required", "Hours per session"), ("max_volunteers", "Places (blank = unlimited)"),
        ("skills_needed", "Skills needed"), ("contact_person", "Contact person"),
        ("contact_email", "Contact email"), ("status", "Status"),
    )

    def __init__(self, parent, auth_manager, opportunity_id=None):
        self.auth = auth_manager
        self.opportunity_id = opportunity_id
        self.saved = False

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Edit Opportunity" if opportunity_id else "New Opportunity")
        self.dialog.geometry("620x560")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        existing = {}
        if opportunity_id:
            try:
                with su_records.db() as conn:
                    existing = vol.get_opportunity(conn, opportunity_id) or {}
            except Exception as e:
                messagebox.showerror("Error", f"Could not load the opportunity:\n{e}", parent=self.dialog)

        form = ttk.Frame(self.dialog)
        form.pack(fill='both', expand=True, padx=15, pady=15)
        self.widgets = {}
        for row, (key, label) in enumerate(self.FIELDS):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky='nw', pady=4)
            if key == 'description':
                w = scrolledtext.ScrolledText(form, height=4, width=45, wrap=tk.WORD)
                w.insert(1.0, existing.get(key) or '')
            elif key in ('category', 'status'):
                w = ttk.Combobox(form, width=43, state='readonly',
                                 values=vol.CATEGORIES if key == 'category' else vol.OPPORTUNITY_STATUSES)
                w.set(existing.get(key) or ('open' if key == 'status' else ''))
            else:
                w = ttk.Entry(form, width=45)
                value = existing.get(key)
                if value is not None:
                    w.insert(0, _fmt_hours(value) if key == 'hours_required' else str(value))
            w.grid(row=row, column=1, sticky='ew', pady=4)
            self.widgets[key] = w
        form.columnconfigure(1, weight=1)

        btns = ttk.Frame(self.dialog)
        btns.pack(fill='x', padx=15, pady=(0, 15))
        ttk.Button(btns, text="Save", command=self.save).pack(side='left', padx=(0, 10))
        ttk.Button(btns, text="Cancel", command=self.dialog.destroy).pack(side='left')

    def save(self):
        data = {}
        for key, w in self.widgets.items():
            data[key] = w.get(1.0, tk.END).strip() if key == 'description' else w.get().strip()
        try:
            with su_records.db() as conn:
                vol.save_opportunity(conn, data, actor=su_records.owner_id(conn, self.auth),
                                     opportunity_id=self.opportunity_id)
        except ValueError as e:
            messagebox.showwarning("Check the form", str(e), parent=self.dialog)
            return
        except Exception as e:
            messagebox.showerror("Error", f"Could not save the opportunity:\n{e}", parent=self.dialog)
            return
        self.saved = True
        self.dialog.destroy()


class VolunteerHoursReviewDialog:
    """SU staff queue: verify or reject logged volunteering hours"""

    def __init__(self, parent, auth_manager):
        self.auth = auth_manager
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Verify Volunteering Hours")
        self.dialog.geometry("1000x560")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        top = ttk.Frame(self.dialog)
        top.pack(fill='x', padx=10, pady=(10, 0))
        ttk.Label(top, text="Show:").pack(side='left')
        self.status_var = tk.StringVar(value='pending')
        combo = ttk.Combobox(top, textvariable=self.status_var, state='readonly', width=12,
                             values=('pending', 'verified', 'rejected', 'all'))
        combo.pack(side='left', padx=5)
        combo.bind('<<ComboboxSelected>>', lambda e: self.load())

        btns = ttk.Frame(self.dialog)
        btns.pack(side='bottom', fill='x', padx=10, pady=10)
        ttk.Button(btns, text="Verify", command=lambda: self.review(True)).pack(side='left', padx=(0, 10))
        ttk.Button(btns, text="Reject", command=lambda: self.review(False)).pack(side='left', padx=(0, 10))
        ttk.Button(btns, text="Close", command=self.dialog.destroy).pack(side='right')

        cols = ('Student', 'Organisation', 'Activity', 'Date', 'Hours', 'Supervisor', 'Status', 'Note')
        self.tree = ttk.Treeview(self.dialog, columns=cols, show='headings')
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=150 if c in ('Student', 'Organisation', 'Activity', 'Supervisor') else 90)
        self.tree.pack(fill='both', expand=True, padx=10, pady=10)
        self.load()

    def load(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        status = self.status_var.get()
        try:
            with su_records.db() as conn:
                rows = vol.list_hours(conn, status=None if status == 'all' else status)
                names = {r['owner_id']: vol.display_name(conn, r['owner_id']) for r in rows}
        except Exception as e:
            messagebox.showerror("Error", f"Could not load submissions:\n{e}", parent=self.dialog)
            return
        if not rows:
            self.tree.insert('', 'end', iid='empty', values=('No submissions', '', '', '', '', '', '', ''))
            return
        for r in rows:
            sup = r['supervisor_name'] or ''
            if r.get('supervisor_email'):
                sup += f" <{r['supervisor_email']}>"
            self.tree.insert('', 'end', iid=str(r['hours_id']), values=(
                f"{names.get(r['owner_id'], r['owner_id'])} ({r['owner_id']})", r['organization'],
                r['activity'] or '', r['activity_date'], _fmt_hours(r['hours']), sup,
                r['status'].title(), r.get('review_note') or ''))

    def review(self, approve):
        sel = self.tree.selection()
        if not sel or sel[0] == 'empty':
            messagebox.showwarning("Warning", "Select a submission first.", parent=self.dialog)
            return
        note = simpledialog.askstring("Verify" if approve else "Reject",
                                      "Note (optional, shown to the student):", parent=self.dialog)
        if note is None:
            return
        try:
            with su_records.db() as conn:
                vol.review_hours(conn, int(sel[0]), approve=approve,
                                 reviewer=su_records.owner_id(conn, self.auth), note=note)
        except ValueError as e:
            messagebox.showwarning("Warning", str(e), parent=self.dialog)
            return
        except Exception as e:
            messagebox.showerror("Error", f"Could not update the submission:\n{e}", parent=self.dialog)
            return
        self.load()


class MyVolunteerActivitiesDialog:
    """Dialog for viewing student's volunteer activities"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t(f'{_K}.windows.my_volunteer_activities', default="My Volunteer Activities"))
        self.dialog.geometry("900x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text=_t(f'{_K}.labels.my_volunteer_activities', default="🤝 My Volunteer Activities"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        signups, hours, stats = [], [], None
        self.owner = None
        try:
            with su_records.db() as conn:
                self.owner = su_records.owner_id(conn, self.auth)
                if self.owner:
                    signups = vol.my_signups(conn, self.owner)
                    hours = vol.list_hours(conn, owner_id=self.owner)
                    stats = vol.summary(conn, self.owner)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load your activities:\n{e}", parent=self.dialog)

        # Stats frame
        stats_frame = ttk.LabelFrame(main_frame, text=_t(f'{_K}.labels.volunteer_statistics', default="Volunteer Statistics"))
        stats_frame.pack(fill='x', pady=(0, 15))

        if stats is None:
            stats_text = "Sign in to see your volunteering record."
        else:
            stats_text = (f"Verified Hours: {stats['verified_hours']:.1f}\n"
                          f"Hours Awaiting Verification: {stats['pending_hours']:.1f}\n"
                          f"Opportunities Signed Up For: {stats['signups']}\n"
                          f"Organizations Helped: {stats['organisations']}\n"
                          f"Community Service Points: {stats['points']}\n\n"
                          f"🏆 Level: {stats['level']}")
        ttk.Label(stats_frame, text=stats_text, justify='left', font=('Arial', 10)).pack(padx=15, pady=10, anchor='w')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(side='bottom', fill='x')

        ttk.Button(button_frame, text=_t(f'{_K}.buttons.download_certificate', default="Download Certificate"), command=self.download_cert).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t(f'{_K}.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='right')

        # Activities list
        list_frame = ttk.LabelFrame(main_frame, text=_t(f'{_K}.labels.activity_history', default="Activity History"))
        list_frame.pack(fill='both', expand=True, pady=(0, 15))

        columns = ('Organization', 'Activity', 'Date', 'Hours', 'Status')
        tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)

        for col in columns:
            tree.heading(col, text=col)
            if col in ('Organization', 'Activity'):
                tree.column(col, width=180)
            else:
                tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        for s in signups:
            status = (s['status'] or 'signed_up').replace('_', ' ').title()
            tree.insert('', 'end', values=(s['organization_name'] or '', (s['description'] or '')[:60],
                                           s['start_date'] or (s['signup_date'] or '')[:10],
                                           _fmt_hours(s['hours_completed'] or 0), f"Sign-up: {status}"))
        for h in hours:
            label = {'pending': 'Hours pending', 'verified': 'Verified ✓', 'rejected': 'Rejected'}[h['status']]
            if h.get('review_note'):
                label += f" — {h['review_note']}"
            tree.insert('', 'end', values=(h['organization'], h['activity'] or '', h['activity_date'],
                                           _fmt_hours(h['hours']), label))
        if not signups and not hours:
            tree.insert('', 'end', values=("No volunteering recorded yet", "", "", "", ""))

    def download_cert(self):
        if not self.owner:
            messagebox.showwarning("Warning", "Sign in to download a certificate.", parent=self.dialog)
            return
        out_dir = paths.UNIVERSITY_EXPORTS_PDF_DIR / "volunteering"
        try:
            with su_records.db() as conn:
                path = vol.write_certificate(conn, self.owner, out_dir)
                total = vol.summary(conn, self.owner)['verified_hours']
        except vol.CertificateUnavailable as e:
            messagebox.showerror("Certificate unavailable", str(e), parent=self.dialog)
            return
        except ValueError as e:
            messagebox.showinfo("No verified hours", f"{e}\n\nLog hours under Community Service Hours; "
                                "they count once Student Union staff verify them.", parent=self.dialog)
            return
        except Exception as e:
            messagebox.showerror("Error", f"Could not write the certificate:\n{e}", parent=self.dialog)
            return
        opened = su_records.open_target(path)
        messagebox.showinfo(_t(f'{_K}.dialogs.success', default="Success"),
                            f"Volunteer hours certificate saved.\n\nFile: {path}\n\n"
                            f"Verified Hours: {total:.1f}"
                            + ("" if opened else "\n\n(It could not be opened automatically.)"),
                            parent=self.dialog)


class CommunityServiceHoursDialog:
    """Dialog for logging community service hours for SU staff verification"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager
        self.staff = su_records.is_staff(auth_manager)
        self._signups = {}

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t(f'{_K}.windows.community_service_hours', default="Community Service Hours"))
        self.dialog.geometry("800x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_submissions()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text=_t(f'{_K}.labels.track_community_service_hours', default="📋 Track Community Service Hours"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Log hours form
        form_frame = ttk.LabelFrame(main_frame, text=_t(f'{_K}.labels.log_service_hours', default="Log Service Hours"))
        form_frame.pack(fill='x', pady=(0, 15))

        form = ttk.Frame(form_frame)
        form.pack(padx=15, pady=15, fill='x')

        # Optional link to one of my sign-ups
        ttk.Label(form, text="My opportunity (optional):").grid(row=0, column=0, sticky='w', pady=5)
        self.signup_combo = ttk.Combobox(form, width=38, state='readonly')
        self.signup_combo.grid(row=0, column=1, pady=5, sticky='ew')
        self.signup_combo.bind('<<ComboboxSelected>>', self._on_signup)

        # Organization
        ttk.Label(form, text=_t(f'{_K}.labels.organization', default="Organization:")).grid(row=1, column=0, sticky='w', pady=5)
        self.org_entry = ttk.Entry(form, width=40)
        self.org_entry.grid(row=1, column=1, pady=5, sticky='ew')

        # Activity
        ttk.Label(form, text=_t(f'{_K}.labels.activity', default="Activity:")).grid(row=2, column=0, sticky='w', pady=5)
        self.activity_entry = ttk.Entry(form, width=40)
        self.activity_entry.grid(row=2, column=1, pady=5, sticky='ew')

        # Date
        ttk.Label(form, text=_t(f'{_K}.labels.date', default="Date:")).grid(row=3, column=0, sticky='w', pady=5)
        self.date_entry = ttk.Entry(form, width=40)
        self.date_entry.grid(row=3, column=1, pady=5, sticky='ew')
        self.date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))

        # Hours
        ttk.Label(form, text=_t(f'{_K}.labels.hours', default="Hours:")).grid(row=4, column=0, sticky='w', pady=5)
        self.hours_entry = ttk.Entry(form, width=40)
        self.hours_entry.grid(row=4, column=1, pady=5, sticky='ew')

        # Supervisor
        ttk.Label(form, text=_t(f'{_K}.labels.supervisor_name', default="Supervisor Name:")).grid(row=5, column=0, sticky='w', pady=5)
        self.supervisor_entry = ttk.Entry(form, width=40)
        self.supervisor_entry.grid(row=5, column=1, pady=5, sticky='ew')

        # Supervisor Email
        ttk.Label(form, text=_t(f'{_K}.labels.supervisor_email', default="Supervisor Email:")).grid(row=6, column=0, sticky='w', pady=5)
        self.supervisor_email_entry = ttk.Entry(form, width=40)
        self.supervisor_email_entry.grid(row=6, column=1, pady=5, sticky='ew')

        form.columnconfigure(1, weight=1)

        ttk.Button(form_frame, text=_t(f'{_K}.buttons.submit_for_verification', default="Submit for Verification"), command=self.submit_hours).pack(pady=(0, 10))

        bottom = ttk.Frame(main_frame)
        bottom.pack(side='bottom', fill='x')
        if self.staff:
            ttk.Button(bottom, text="Verify Hours (Staff)", command=self.review_hours).pack(side='left')
        ttk.Button(bottom, text=_t(f'{_K}.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='right')

        # Pending verification
        pending_frame = ttk.LabelFrame(main_frame, text=_t(f'{_K}.labels.pending_verification', default="Pending Verification"))
        pending_frame.pack(fill='both', expand=True, pady=(0, 15))

        columns = ('Organization', 'Hours', 'Date', 'Status')
        self.tree = ttk.Treeview(pending_frame, columns=columns, show='headings', height=6)

        for col in columns:
            self.tree.heading(col, text=col)

        self.tree.pack(fill='both', expand=True, padx=5, pady=5)

    def load_submissions(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        self.owner = None
        rows = []
        try:
            with su_records.db() as conn:
                self.owner = su_records.owner_id(conn, self.auth)
                if self.owner:
                    rows = vol.list_hours(conn, owner_id=self.owner)
                    self._signups = {f"{s['organization_name']} — {(s['description'] or '')[:40]}": s
                                     for s in vol.my_signups(conn, self.owner)
                                     if (s['status'] or 'signed_up') != 'cancelled'}
        except Exception as e:
            messagebox.showerror("Error", f"Could not load your hours:\n{e}", parent=self.dialog)
        self.signup_combo['values'] = ('(none)',) + tuple(self._signups)
        self.signup_combo.set('(none)')
        if not rows:
            self.tree.insert('', 'end', values=("No hours logged yet", "", "", ""))
        for r in rows:
            status = {'pending': 'Pending', 'verified': 'Verified ✓', 'rejected': 'Rejected'}[r['status']]
            self.tree.insert('', 'end', values=(r['organization'], _fmt_hours(r['hours']), r['activity_date'], status))

    def _on_signup(self, event=None):
        s = self._signups.get(self.signup_combo.get())
        if s:
            self.org_entry.delete(0, tk.END)
            self.org_entry.insert(0, s['organization_name'] or '')

    def submit_hours(self):
        org = self.org_entry.get().strip()
        hours = self.hours_entry.get().strip()
        supervisor = self.supervisor_entry.get().strip()

        if not all([org, hours, supervisor]):
            messagebox.showwarning(_t(f'{_K}.dialogs.warning', default="Warning"), _t(f'{_K}.dialogs.please_fill_in_all_required_fields', default="Please fill in all required fields."), parent=self.dialog)
            return
        if not self.owner:
            messagebox.showwarning("Warning", "Sign in to log hours.", parent=self.dialog)
            return

        signup = self._signups.get(self.signup_combo.get())
        try:
            with su_records.db() as conn:
                vol.submit_hours(conn, self.owner, organization=org,
                                 activity=self.activity_entry.get(),
                                 activity_date=self.date_entry.get(), hours=hours,
                                 supervisor_name=supervisor,
                                 supervisor_email=self.supervisor_email_entry.get(),
                                 opportunity_id=signup['opportunity_id'] if signup else None)
        except ValueError as e:
            messagebox.showwarning("Check the form", str(e), parent=self.dialog)
            return
        except Exception as e:
            messagebox.showerror("Error", f"Could not save your hours:\n{e}", parent=self.dialog)
            return

        messagebox.showinfo(_t(f'{_K}.dialogs.success', default="Success"),
                            f"Hours submitted for verification.\n\nStudent Union staff will check them "
                            f"with your supervisor ({supervisor}); they count toward your total and "
                            f"certificate once verified.\n\nHours: {hours}\nOrganization: {org}",
                            parent=self.dialog)

        # Clear form
        self.org_entry.delete(0, tk.END)
        self.activity_entry.delete(0, tk.END)
        self.hours_entry.delete(0, tk.END)
        self.supervisor_entry.delete(0, tk.END)
        self.supervisor_email_entry.delete(0, tk.END)
        self.load_submissions()

    def review_hours(self):
        dialog = VolunteerHoursReviewDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)
        self.load_submissions()


# ============================================================================
# ANALYTICS DIALOGS
# ============================================================================


class CommunityEngagementDialog:
    """Main dialog for community engagement"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.pastoral.student_union_gui.volunteer.volunteer.windows.community_engagement', default="Community Engagement"))
        self.dialog.geometry("1000x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.volunteer.volunteer.labels.community_engagement_outreach', default="🤝 Community Engagement & Outreach"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Tabs for different features
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 10))

        # Tab 1: Community Projects
        projects_frame = ttk.Frame(notebook)
        notebook.add(projects_frame, text=_t('gui.pastoral.student_union_gui.volunteer.volunteer.tabs.community_projects', default="Community Projects"))
        self.create_projects_tab(projects_frame)

        # Tab 2: Engagement Analytics
        analytics_frame = ttk.Frame(notebook)
        notebook.add(analytics_frame, text=_t('gui.pastoral.student_union_gui.volunteer.volunteer.tabs.engagement_analytics', default="Engagement Analytics"))
        self.create_analytics_tab(analytics_frame)

        # Tab 3: Retention Insights
        retention_frame = ttk.Frame(notebook)
        notebook.add(retention_frame, text=_t('gui.pastoral.student_union_gui.volunteer.volunteer.tabs.retention_insights', default="Retention Insights"))
        self.create_retention_tab(retention_frame)

        ttk.Button(main_frame, text=_t('gui.pastoral.student_union_gui.volunteer.volunteer.buttons.close', default="Close"), command=self.dialog.destroy).pack()

    def create_projects_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text=_t('gui.pastoral.student_union_gui.volunteer.volunteer.labels.active_community_projects', default="Active Community Projects"), font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        columns = ('Project', 'Lead', 'Impact Area', 'Beneficiaries', 'Status')
        tree = ttk.Treeview(frame, columns=columns, show='headings', height=15)

        for col in columns:
            tree.heading(col, text=col)

        tree.pack(fill='both', expand=True)

        # Real projects from social_impact_projects
        rows = []
        try:
            with su_records.db() as conn:
                exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                                      "AND name='social_impact_projects'").fetchone()
                if exists:
                    rows = [tuple(r) for r in conn.execute(
                        "SELECT project_name, lead_student_id, impact_area, target_beneficiaries, status "
                        "FROM social_impact_projects ORDER BY COALESCE(created_at, '') DESC").fetchall()]
                    rows = [(r[0], vol.display_name(conn, r[1]) if r[1] else '', r[2] or '',
                             r[3] if r[3] else '—', (r[4] or '').title()) for r in rows]
        except Exception as e:
            logging.getLogger(__name__).debug("community projects load failed: %s", e)

        if not rows:
            tree.insert('', 'end', values=("No community projects recorded yet", "", "", "", ""))
        for project in rows:
            tree.insert('', 'end', values=project)

    def create_analytics_tab(self, parent):
        dialog = EngagementTrendAnalysisDialog(parent, self.auth, embedded=True)

    def create_retention_tab(self, parent):
        dialog = MemberRetentionInsightsDialog(parent, self.auth, embedded=True)



def open_volunteer_opportunities_dialog(self):
    """Open volunteer opportunities dialog"""
    dialog = VolunteerOpportunitiesDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


def open_community_service_hours_dialog(self):
    """Open community service hours tracking dialog"""
    dialog = CommunityServiceHoursDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


def open_community_engagement_dialog(self):
    """Open community engagement dialog"""
    dialog = CommunityEngagementDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


