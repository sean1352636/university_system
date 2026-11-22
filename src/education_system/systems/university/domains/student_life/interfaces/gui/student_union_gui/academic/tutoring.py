
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
from education_system.systems.university.infrastructure.shared_context import get_auth
from education_system.systems.university.domains.student_life.interfaces.gui.student_union_gui.academic._hub_gui import (
    hub, hub_conn, owner_id, report_error, fill_tree, selected_id, ask_form, show_list, stars,
)

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


class PeerTutoringDialog:
    """Peer tutoring system"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.pastoral.student_union_gui.academic.tutoring.windows.peer_tutoring', default="Peer Tutoring"))
        self.dialog.geometry("1100x750")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_tutors()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.academic.tutoring.labels.peer_tutoring', default="👨‍🏫 Peer Tutoring"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Top buttons
        top_btn_frame = ttk.Frame(main_frame)
        top_btn_frame.pack(fill='x', pady=(0, 15))

        ttk.Button(top_btn_frame, text=_t('gui.pastoral.student_union_gui.academic.tutoring.buttons.become_a_tutor', default="🎓 Become a Tutor"),
                  command=self.become_tutor).pack(side='left', padx=(0, 10))
        ttk.Button(top_btn_frame, text=_t('gui.pastoral.student_union_gui.academic.tutoring.buttons.my_tutoring_schedule', default="📅 My Tutoring Schedule"),
                  command=self.view_schedule).pack(side='left', padx=(0, 10))
        ttk.Button(top_btn_frame, text=_t('gui.pastoral.student_union_gui.academic.tutoring.buttons.my_tutoring_hours', default="📊 My Tutoring Hours"),
                  command=self.view_hours).pack(side='left')

        # Filter frame
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(filter_frame, text=_t('gui.pastoral.student_union_gui.academic.tutoring.labels.subject', default="Subject:")).pack(side='left', padx=(0, 5))
        self.subject_var = tk.StringVar()
        subject_combo = ttk.Combobox(filter_frame, textvariable=self.subject_var, width=25, state='readonly')
        self.subject_combo = subject_combo
        subject_combo['values'] = ('All Subjects',)
        subject_combo.current(0)
        subject_combo.pack(side='left', padx=(0, 15))

        ttk.Button(filter_frame, text=_t('gui.pastoral.student_union_gui.academic.tutoring.buttons.filter', default="Filter"), command=self.load_tutors).pack(side='left')

        # Tutors list
        list_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.academic.tutoring.labels.available_tutors', default="Available Tutors"))
        list_frame.pack(fill='both', expand=True, pady=(0, 15))

        columns = ('Tutor', 'Subject', 'Rating', 'Sessions', 'Availability', 'Rate')
        self.tutors_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=12)

        for col in columns:
            self.tutors_tree.heading(col, text=col)
            if col == 'Tutor':
                self.tutors_tree.column(col, width=150)
            elif col == 'Subject':
                self.tutors_tree.column(col, width=180)
            else:
                self.tutors_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.tutors_tree.yview)
        self.tutors_tree.configure(yscrollcommand=scrollbar.set)

        self.tutors_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self.tutors_tree.bind('<<TreeviewSelect>>', self.on_select)

        # Details frame
        details_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.academic.tutoring.labels.tutor_details', default="Tutor Details"))
        details_frame.pack(fill='x', pady=(0, 15))

        self.details_text = scrolledtext.ScrolledText(details_frame, height=5, wrap=tk.WORD)
        self.details_text.pack(fill='both', expand=True, padx=5, pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.academic.tutoring.buttons.request_session', default="Request Session"), command=self.request_session).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.academic.tutoring.buttons.view_reviews', default="View Reviews"), command=self.view_reviews).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.academic.tutoring.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='right')

    def load_tutors(self):
        """List real tutoring offers; ratings/sessions come from booked sessions."""
        self._tutor_rows = {}
        subject = self.subject_var.get()
        subject = None if subject in ('', 'All Subjects') else subject
        try:
            with hub_conn() as conn:
                self.subject_combo['values'] = ('All Subjects',) + tuple(hub.tutoring_subjects(conn))
                offers = hub.list_tutor_offers(conn, subject)
        except Exception as e:
            report_error(self.dialog, e)
            return
        rows = []
        for o in offers:
            self._tutor_rows[o['offer_id']] = o
            subj = o['subject'] + (f" ({o['topic']})" if o.get('topic') else '')
            rate = f"£{o['hourly_rate']:.2f}/hr" if (o['hourly_rate'] or 0) > 0 else "Free"
            rows.append((o['offer_id'], (o['tutor_name'], subj, stars(o['avg_rating']),
                                         o['sessions_done'], o['availability'] or '-', rate)))
        fill_tree(self.tutors_tree, rows,
                  "No tutors are offering sessions yet - use 'Become a Tutor' to offer one.")
        self.details_text.delete(1.0, tk.END)

    def on_select(self, event):
        offer = self._tutor_rows.get(selected_id(self.tutors_tree))
        self.details_text.delete(1.0, tk.END)
        if not offer:
            return
        lines = [f"Experience: {offer['experience_level'] or 'Not stated'}",
                 offer['description'] or "No description given."]
        self.details_text.insert(1.0, "\n".join(lines))

    def _selected_offer(self):
        offer = self._tutor_rows.get(selected_id(self.tutors_tree))
        if not offer:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.academic.tutoring.dialogs.warning', default="Warning"), _t('gui.pastoral.student_union_gui.academic.tutoring.dialogs.please_select_a_tutor', default="Please select a tutor."), parent=self.dialog)
        return offer

    def request_session(self):
        offer = self._selected_offer()
        if not offer:
            return
        form = ask_form(self.dialog, _t('gui.pastoral.student_union_gui.academic.tutoring.dialogs.request_session', default="Request Session"), [
            ('when', "Proposed time (YYYY-MM-DD HH:MM):", 'entry', None, ''),
            ('message', "Message (topics, what you need help with):", 'text', None, ''),
        ], submit_text="Send Request")
        if not form:
            return
        try:
            with hub_conn() as conn:
                hub.request_tutoring(conn, offer['offer_id'], owner_id(conn, self.auth),
                                     form['message'], form['when'])
        except Exception as e:
            report_error(self.dialog, e)
            return
        messagebox.showinfo(_t('gui.pastoral.student_union_gui.academic.tutoring.dialogs.success', default="Success"),
                            f"Your request has been sent to {offer['tutor_name']}.\n"
                            "It appears in their tutoring schedule to accept or decline.",
                            parent=self.dialog)

    def view_reviews(self):
        offer = self._selected_offer()
        if not offer:
            return
        try:
            with hub_conn() as conn:
                reviews = hub.tutor_reviews(conn, offer['tutor_id'])
        except Exception as e:
            report_error(self.dialog, e)
            return
        rows = [(i, (f"{r['rating']}/5", r['subject'] or '', r['tutee_name'],
                     (r['completed_at'] or '')[:10], r['review'] or ''))
                for i, r in enumerate(reviews)]
        show_list(self.dialog, _t('gui.pastoral.student_union_gui.academic.tutoring.dialogs.tutor_reviews', default="Tutor Reviews") + f" - {offer['tutor_name']}",
                  ('Rating', 'Subject', 'Student', 'Date', 'Review'), rows,
                  "This tutor has no reviews yet.")

    def become_tutor(self):
        form = ask_form(self.dialog, _t('gui.pastoral.student_union_gui.academic.tutoring.dialogs.become_a_tutor', default="Become a Tutor"), [
            ('subject', "Subject:", 'combo', tuple(self.subject_combo['values'])[1:], ''),
            ('topic', "Specific topics:", 'entry', None, ''),
            ('rate', "Hourly rate (£, 0 for free):", 'entry', None, '0'),
            ('availability', "Availability:", 'entry', None, ''),
            ('level', "Experience level:", 'choice', ('Beginner', 'Intermediate', 'Advanced', 'Expert'), 'Intermediate'),
            ('description', "About you:", 'text', None, ''),
        ], submit_text="Offer Tutoring")
        if not form:
            return
        try:
            with hub_conn() as conn:
                hub.create_tutor_offer(conn, owner_id(conn, self.auth), subject=form['subject'],
                                       topic=form['topic'], hourly_rate=form['rate'] or 0,
                                       availability=form['availability'],
                                       experience_level=form['level'] or 'Intermediate',
                                       description=form['description'])
        except Exception as e:
            report_error(self.dialog, e)
            return
        messagebox.showinfo(_t('gui.pastoral.student_union_gui.academic.tutoring.dialogs.application', default="Application"),
                            "You are now listed as a peer tutor.", parent=self.dialog)
        self.load_tutors()

    def view_schedule(self):
        """Requests addressed to me plus every session I tutor or attend."""
        try:
            with hub_conn() as conn:
                me = owner_id(conn, self.auth)
                if not me:
                    raise hub.AcademicHubError("You must be signed in.")
                pending = hub.requests_for_tutor(conn, me)
                sessions = hub.my_sessions(conn, me)
        except Exception as e:
            report_error(self.dialog, e)
            return
        rows = [(f"r{r['request_id']}", ('Request', (r['created_at'] or '')[:16], r['subject'] or '',
                                         r['requester_name'], 'pending', (r['message'] or '').replace('\n', ' ')))
                for r in pending]
        rows += [(f"s{s['session_id']}", (f"Session ({s['my_role']})", s['scheduled_at'], s['subject'] or '',
                                          s['tutee_name'] if s['my_role'] == 'Tutor' else s['tutor_name'],
                                          s['status'], s['location'] or ''))
                 for s in sessions]

        def pick(tree):
            sel = tree.selection()
            return sel[0] if sel and sel[0] != '__empty__' else None

        def act(fn):
            def run(tree, win):
                key = pick(tree)
                if not key:
                    messagebox.showwarning("Select", "Select an entry first.", parent=win)
                    return
                try:
                    with hub_conn() as conn:
                        if fn(conn, owner_id(conn, self.auth), key[0], int(key[1:]), win) is False:
                            return
                except Exception as e:
                    report_error(win, e)
                    return
                win.destroy()
                self.view_schedule()
            return run

        def accept(conn, me, kind, rid, win):
            if kind != 'r':
                raise hub.AcademicHubError("Select a pending request to accept.")
            form = ask_form(win, "Accept Request", [
                ('when', "Session time (YYYY-MM-DD HH:MM):", 'entry', None, ''),
                ('location', "Location:", 'entry', None, '')], submit_text="Book Session")
            if not form:
                return False
            hub.accept_request(conn, rid, me, form['when'], form['location'])

        def decline(conn, me, kind, rid, win):
            if kind != 'r':
                raise hub.AcademicHubError("Select a pending request to decline.")
            hub.decline_request(conn, rid, me)

        def complete(conn, me, kind, rid, win):
            if kind != 's':
                raise hub.AcademicHubError("Select a session.")
            mins = simpledialog.askinteger("Complete Session", "Session length (minutes):",
                                           parent=win, minvalue=1, maxvalue=600)
            if not mins:
                return False
            hub.complete_session(conn, rid, me, mins)

        def rate(conn, me, kind, rid, win):
            if kind != 's':
                raise hub.AcademicHubError("Select a completed session.")
            form = ask_form(win, "Rate Session", [
                ('rating', "Rating (1-5):", 'spin', (1, 5), 5),
                ('review', "Review:", 'text', None, '')], submit_text="Submit")
            if not form:
                return False
            hub.rate_session(conn, rid, me, form['rating'], form['review'])

        def cancel(conn, me, kind, rid, win):
            if kind != 's':
                raise hub.AcademicHubError("Select a scheduled session.")
            hub.cancel_session(conn, rid, me)

        show_list(self.dialog, _t('gui.pastoral.student_union_gui.academic.tutoring.dialogs.my_schedule', default="My Schedule"),
                  ('Type', 'When', 'Subject', 'With', 'Status', 'Details'), rows,
                  "No tutoring requests or sessions yet.",
                  actions=(("Accept Request", act(accept)), ("Decline Request", act(decline)),
                           ("Mark Completed", act(complete)), ("Rate Session", act(rate)),
                           ("Cancel Session", act(cancel))))

    def view_hours(self):
        try:
            with hub_conn() as conn:
                stats = hub.tutoring_hours(conn, owner_id(conn, self.auth))
        except Exception as e:
            report_error(self.dialog, e)
            return
        if not stats['sessions'] and not stats['upcoming']:
            text = "You have not tutored any sessions yet."
        else:
            text = (f"Total Hours: {stats['hours']:.1f}\n"
                    f"Sessions Completed: {stats['sessions']}\n"
                    f"Upcoming Sessions: {stats['upcoming']}\n"
                    f"Average Rating: {stars(stats['avg_rating'])}\n"
                    f"Students Helped: {stats['students']}")
        messagebox.showinfo(_t('gui.pastoral.student_union_gui.academic.tutoring.dialogs.tutoring_hours', default="Tutoring Hours"),
                            text, parent=self.dialog)



class AcademicWorkshopsDialog:
    """Academic workshops and skill-building sessions"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.pastoral.student_union_gui.academic.tutoring.windows.academic_workshops', default="Academic Workshops"))
        self.dialog.geometry("1100x750")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_workshops()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.academic.tutoring.labels.academic_workshops', default="🎯 Academic Workshops"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Filter frame
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(filter_frame, text=_t('gui.pastoral.student_union_gui.academic.tutoring.labels.category', default="Category:")).pack(side='left', padx=(0, 5))
        self.category_var = tk.StringVar()
        category_combo = ttk.Combobox(filter_frame, textvariable=self.category_var, width=25, state='readonly')
        self.category_combo = category_combo
        category_combo['values'] = ('All Categories',) + hub.WORKSHOP_CATEGORIES
        category_combo.current(0)
        category_combo.pack(side='left', padx=(0, 15))

        ttk.Button(filter_frame, text=_t('gui.pastoral.student_union_gui.academic.tutoring.buttons.filter', default="Filter"), command=self.load_workshops).pack(side='left')

        # Workshops list
        list_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.academic.tutoring.labels.upcoming_workshops', default="Upcoming Workshops"))
        list_frame.pack(fill='both', expand=True, pady=(0, 15))

        columns = ('Workshop Title', 'Category', 'Date/Time', 'Location', 'Seats', 'Duration')
        self.workshops_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=12)

        for col in columns:
            self.workshops_tree.heading(col, text=col)
            if col == 'Workshop Title':
                self.workshops_tree.column(col, width=280)
            elif col == 'Category':
                self.workshops_tree.column(col, width=140)
            else:
                self.workshops_tree.column(col, width=130)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.workshops_tree.yview)
        self.workshops_tree.configure(yscrollcommand=scrollbar.set)

        self.workshops_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self.workshops_tree.bind('<<TreeviewSelect>>', self.on_select)

        # Details frame
        details_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.academic.tutoring.labels.workshop_description', default="Workshop Description"))
        details_frame.pack(fill='x', pady=(0, 15))

        self.details_text = scrolledtext.ScrolledText(details_frame, height=5, wrap=tk.WORD)
        self.details_text.pack(fill='both', expand=True, padx=5, pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.academic.tutoring.buttons.register', default="Register"), command=self.register).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.academic.tutoring.buttons.view_materials', default="View Materials"), command=self.view_materials).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.academic.tutoring.buttons.my_workshops', default="My Workshops"), command=self.my_workshops).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.academic.tutoring.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='right')

    def load_workshops(self):
        """Upcoming SU workshops from the union events calendar."""
        self._workshops = {}
        category = self.category_var.get()
        category = None if category in ('', 'All Categories') else category
        try:
            with hub_conn() as conn:
                cats = list(hub.WORKSHOP_CATEGORIES)
                for c in hub.workshop_categories(conn):
                    if c not in cats:
                        cats.append(c)
                self.category_combo['values'] = ['All Categories'] + cats
                workshops = hub.list_workshops(conn, category)
        except Exception as e:
            report_error(self.dialog, e)
            return
        rows = []
        for w in workshops:
            self._workshops[w['event_id']] = w
            when = f"{w['event_date'] or 'TBA'} {w['start_time'] or ''}".strip()
            seats = f"{w['registered']}/{w['max_capacity']}" if w['max_capacity'] else f"{w['registered']}/-"
            duration = (f"{w['start_time']}-{w['end_time']}" if w['start_time'] and w['end_time'] else '-')
            rows.append((w['event_id'], (w['title'], w['category'] or '', when,
                                         w['location'] or 'TBA', seats, duration)))
        fill_tree(self.workshops_tree, rows,
                  "No upcoming Student Union workshops are scheduled.")
        self.details_text.delete(1.0, tk.END)

    def on_select(self, event):
        w = self._workshops.get(selected_id(self.workshops_tree))
        self.details_text.delete(1.0, tk.END)
        if w:
            self.details_text.insert(1.0, w['description'] or "No description available.")

    def register(self):
        w = self._workshops.get(selected_id(self.workshops_tree))
        if not w:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.academic.tutoring.dialogs.warning', default="Warning"), _t('gui.pastoral.student_union_gui.academic.tutoring.dialogs.please_select_a_workshop', default="Please select a workshop."), parent=self.dialog)
            return
        if not messagebox.askyesno(_t('gui.pastoral.student_union_gui.academic.tutoring.dialogs.register', default="Register"), f"Register for '{w['title']}'?", parent=self.dialog):
            return
        try:
            with hub_conn() as conn:
                me = owner_id(conn, self.auth)
                hub.register_for_workshop(conn, w['event_id'], me, hub.display_name(conn, me))
        except Exception as e:
            report_error(self.dialog, e)
            return
        messagebox.showinfo(_t('gui.pastoral.student_union_gui.academic.tutoring.dialogs.success', default="Success"),
                            f"You are registered for '{w['title']}'.", parent=self.dialog)
        self.load_workshops()

    def view_materials(self):
        w = self._workshops.get(selected_id(self.workshops_tree))
        if not w:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.academic.tutoring.dialogs.warning', default="Warning"), _t('gui.pastoral.student_union_gui.academic.tutoring.dialogs.please_select_a_workshop', default="Please select a workshop."), parent=self.dialog)
            return
        try:
            with hub_conn() as conn:
                mats = hub.workshop_materials(conn, w['event_id'])
        except Exception as e:
            report_error(self.dialog, e)
            return
        rows = [(m['resource_id'], (m['resource_title'], m['resource_type'] or '', m['subject'] or ''))
                for m in mats]
        show_list(self.dialog, _t('gui.pastoral.student_union_gui.academic.tutoring.dialogs.workshop_materials', default="Workshop Materials"),
                  ('Resource', 'Type', 'Course'), rows,
                  "No materials have been shared for this workshop yet.")

    def my_workshops(self):
        try:
            with hub_conn() as conn:
                mine = hub.my_workshops(conn, owner_id(conn, self.auth))
        except Exception as e:
            report_error(self.dialog, e)
            return
        rows = [(m['event_id'], (m['title'], m['event_date'] or 'TBA', m['attendance_status'] or '',
                                 (m['registration_date'] or '')[:10])) for m in mine]
        show_list(self.dialog, _t('gui.pastoral.student_union_gui.academic.tutoring.dialogs.my_workshops', default="My Workshops"),
                  ('Workshop', 'Date', 'Status', 'Registered'), rows,
                  "You have not registered for any workshops.")
