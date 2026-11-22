
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
logger = logging.getLogger(__name__)
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


class StudyGroupsDialog:
    """Study group management platform"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.pastoral.student_union_gui.academic.study_groups.windows.study_groups', default="Study Groups"))
        self.dialog.geometry("1100x750")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_groups()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.academic.study_groups.labels.study_groups', default="📚 Study Groups"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Filter frame
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(filter_frame, text=_t('gui.pastoral.student_union_gui.academic.study_groups.labels.course', default="Course:")).pack(side='left', padx=(0, 5))
        self.course_var = tk.StringVar()
        course_combo = ttk.Combobox(filter_frame, textvariable=self.course_var, width=25, state='readonly')
        self.course_combo = course_combo
        course_combo['values'] = ('All Courses',)
        course_combo.current(0)
        course_combo.pack(side='left', padx=(0, 15))

        ttk.Button(filter_frame, text=_t('gui.pastoral.student_union_gui.academic.study_groups.buttons.filter', default="Filter"), command=self.load_groups).pack(side='left', padx=(0, 20))
        ttk.Button(filter_frame, text=_t('gui.pastoral.student_union_gui.academic.study_groups.buttons.create_study_group', default="➕ Create Study Group"),
                  command=self.create_group).pack(side='left')

        # Groups list
        list_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.academic.study_groups.labels.available_study_groups', default="Available Study Groups"))
        list_frame.pack(fill='both', expand=True, pady=(0, 15))

        columns = ('Course', 'Group Name', 'Members', 'Next Session', 'Location', 'Status')
        self.groups_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=12)

        for col in columns:
            self.groups_tree.heading(col, text=col)
            if col == 'Course':
                self.groups_tree.column(col, width=150)
            elif col == 'Group Name':
                self.groups_tree.column(col, width=180)
            else:
                self.groups_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.groups_tree.yview)
        self.groups_tree.configure(yscrollcommand=scrollbar.set)

        self.groups_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self.groups_tree.bind('<<TreeviewSelect>>', self.on_select)

        # Details frame
        details_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.academic.study_groups.labels.group_details', default="Group Details"))
        details_frame.pack(fill='x', pady=(0, 15))

        self.details_text = scrolledtext.ScrolledText(details_frame, height=5, wrap=tk.WORD)
        self.details_text.pack(fill='both', expand=True, padx=5, pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.academic.study_groups.buttons.join_group', default="Join Group"), command=self.join_group).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.academic.study_groups.buttons.schedule_session', default="Schedule Session"), command=self.schedule_session).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.academic.study_groups.buttons.share_materials', default="Share Materials"), command=self.share_materials).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.academic.study_groups.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='right')

    def _course_filter(self):
        course = self.course_var.get()
        return None if course in ('', 'All Courses') else course

    def load_groups(self):
        """Active study groups from study_groups (shared with Study Hub)."""
        self._groups = {}
        try:
            with hub_conn() as conn:
                self.course_combo['values'] = ['All Courses'] + hub.course_options(conn, owner_id(conn, self.auth))
                groups = hub.list_study_groups(conn, self._course_filter())
        except Exception as e:
            report_error(self.dialog, e)
            return
        rows = []
        for g in groups:
            self._groups[g['group_id']] = g
            full = g['max_members'] and g['members'] >= g['max_members']
            rows.append((g['group_id'], (g['course_id'], g['group_name'],
                                         f"{g['members']}/{g['max_members'] or '-'}",
                                         g['next_session'] or (g['meeting_schedule'] or 'None scheduled'),
                                         g['location'] or '-', 'Full' if full else 'Open')))
        fill_tree(self.groups_tree, rows,
                  "No study groups yet - use 'Create Study Group' to start one.")
        self.details_text.delete(1.0, tk.END)

    def on_select(self, event):
        g = self._groups.get(selected_id(self.groups_tree))
        self.details_text.delete(1.0, tk.END)
        if not g:
            return
        try:
            with hub_conn() as conn:
                members = hub.group_members(conn, g['group_id'])
                materials = hub.group_materials(conn, g['group_id'])
        except Exception as e:
            report_error(self.dialog, e)
            return
        lines = [g['description'] or "No description given."]
        if g['meeting_schedule']:
            lines.append(f"Meets: {g['meeting_schedule']}")
        lines.append("Members: " + (", ".join(m['name'] for m in members) or "none"))
        lines.append("Shared materials: " + (", ".join(m['resource_title'] for m in materials) or "none"))
        self.details_text.insert(1.0, "\n".join(lines))

    def _selected_group(self):
        g = self._groups.get(selected_id(self.groups_tree))
        if not g:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.academic.study_groups.dialogs.warning', default="Warning"), _t('gui.pastoral.student_union_gui.academic.study_groups.dialogs.please_select_a_study_group', default="Please select a study group."), parent=self.dialog)
        return g

    def join_group(self):
        g = self._selected_group()
        if not g:
            return
        if not messagebox.askyesno(_t('gui.pastoral.student_union_gui.academic.study_groups.dialogs.confirm', default="Confirm"), f"Join '{g['group_name']}'?", parent=self.dialog):
            return
        try:
            with hub_conn() as conn:
                hub.join_study_group(conn, g['group_id'], owner_id(conn, self.auth))
        except Exception as e:
            report_error(self.dialog, e)
            return
        messagebox.showinfo(_t('gui.pastoral.student_union_gui.academic.study_groups.dialogs.success', default="Success"),
                            f"You've joined '{g['group_name']}'.", parent=self.dialog)
        self.load_groups()

    def schedule_session(self):
        g = self._selected_group()
        if g:
            schedule_group_session(self.dialog, self.auth, g)
            self.load_groups()

    def share_materials(self):
        g = self._selected_group()
        if g:
            share_group_material(self.dialog, self.auth, g)

    def create_group(self):
        dialog = CreateStudyGroupDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)
        self.load_groups()


def schedule_group_session(parent, auth, group):
    """Members book a dated session for a group (mirrored to the calendar)."""
    form = ask_form(parent, _t('gui.pastoral.student_union_gui.academic.study_groups.dialogs.schedule_session', default="Schedule Session") + f" - {group['group_name']}", [
        ('when', "Date and time (YYYY-MM-DD HH:MM):", 'entry', None, ''),
        ('location', "Location:", 'entry', None, group.get('location') or ''),
        ('agenda', "Agenda / topics:", 'text', None, ''),
    ], submit_text="Schedule")
    if not form:
        return
    try:
        with hub_conn() as conn:
            hub.schedule_group_session(conn, group['group_id'], owner_id(conn, auth),
                                       form['when'], form['location'], form['agenda'])
    except Exception as e:
        report_error(parent, e)
        return
    messagebox.showinfo("Session Scheduled", "The session is booked and on the calendar.", parent=parent)


def share_group_material(parent, auth, group):
    """Members link one of the shared resources to the group."""
    try:
        with hub_conn() as conn:
            resources = hub.list_resources(conn, group['course_id']) or hub.list_resources(conn)
    except Exception as e:
        report_error(parent, e)
        return
    if not resources:
        messagebox.showinfo(_t('gui.pastoral.student_union_gui.academic.study_groups.dialogs.share_materials', default="Share Materials"),
                            "There are no shared resources yet. Upload one under Shared Resources first.",
                            parent=parent)
        return
    labels = {f"{r['resource_title']} ({r['subject'] or '-'}) #{r['resource_id']}": r['resource_id']
              for r in resources}
    form = ask_form(parent, _t('gui.pastoral.student_union_gui.academic.study_groups.dialogs.share_materials', default="Share Materials"), [
        ('res', "Resource:", 'choice', tuple(labels), next(iter(labels))),
    ], submit_text="Share")
    if not form or form['res'] not in labels:
        return
    try:
        with hub_conn() as conn:
            hub.share_material(conn, group['group_id'], labels[form['res']], owner_id(conn, auth))
    except Exception as e:
        report_error(parent, e)
        return
    messagebox.showinfo("Shared", "The resource is now shared with the group.", parent=parent)



class CreateStudyGroupDialog:
    """Create a new study group"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.pastoral.student_union_gui.academic.study_groups.windows.create_study_group', default="Create Study Group"))
        self.dialog.geometry("700x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.academic.study_groups.labels.create_new_study_group', default="➕ Create New Study Group"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Form
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill='both', expand=True, pady=(0, 15))

        ttk.Label(form_frame, text=_t('gui.pastoral.student_union_gui.academic.study_groups.labels.course', default="Course:")).grid(row=0, column=0, sticky='w', pady=5)
        self.course_combo = ttk.Combobox(form_frame, width=47)
        try:
            with hub_conn() as conn:
                self.course_combo['values'] = hub.course_options(conn, owner_id(conn, self.auth))
        except Exception:
            logger.debug("course options unavailable", exc_info=True)
        if self.course_combo['values']:
            self.course_combo.current(0)
        self.course_combo.grid(row=0, column=1, sticky='ew', pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t('gui.pastoral.student_union_gui.academic.study_groups.labels.group_name', default="Group Name:")).grid(row=1, column=0, sticky='w', pady=5)
        self.name_entry = ttk.Entry(form_frame, width=50)
        self.name_entry.grid(row=1, column=1, sticky='ew', pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t('gui.pastoral.student_union_gui.academic.study_groups.labels.description', default="Description:")).grid(row=2, column=0, sticky='nw', pady=5)
        self.desc_text = scrolledtext.ScrolledText(form_frame, width=50, height=3)
        self.desc_text.grid(row=2, column=1, sticky='ew', pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t('gui.pastoral.student_union_gui.academic.study_groups.labels.member_limit', default="Member Limit:")).grid(row=3, column=0, sticky='w', pady=5)
        self.limit_spin = ttk.Spinbox(form_frame, from_=3, to=20, width=10)
        self.limit_spin.grid(row=3, column=1, sticky='w', pady=5, padx=(10, 0))
        self.limit_spin.set(8)

        ttk.Label(form_frame, text="Meeting Schedule:").grid(row=4, column=0, sticky='w', pady=5)
        self.schedule_entry = ttk.Entry(form_frame, width=50)
        self.schedule_entry.grid(row=4, column=1, sticky='ew', pady=5, padx=(10, 0))

        ttk.Label(form_frame, text="Location:").grid(row=5, column=0, sticky='w', pady=5)
        self.location_entry = ttk.Entry(form_frame, width=50)
        self.location_entry.grid(row=5, column=1, sticky='ew', pady=5, padx=(10, 0))

        form_frame.columnconfigure(1, weight=1)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.academic.study_groups.buttons.create', default="Create"), command=self.create).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.academic.study_groups.buttons.cancel', default="Cancel"), command=self.dialog.destroy).pack(side='right')

    def create(self):
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.academic.study_groups.dialogs.warning', default="Warning"), _t('gui.pastoral.student_union_gui.academic.study_groups.dialogs.please_enter_a_group_name', default="Please enter a group name."), parent=self.dialog)
            return
        try:
            with hub_conn() as conn:
                hub.create_study_group(
                    conn, owner_id(conn, self.auth), course_id=self.course_combo.get(),
                    group_name=name, description=self.desc_text.get('1.0', 'end-1c').strip(),
                    max_members=self.limit_spin.get(), meeting_schedule=self.schedule_entry.get().strip(),
                    location=self.location_entry.get().strip())
        except Exception as e:
            report_error(self.dialog, e)
            return
        messagebox.showinfo(_t('gui.pastoral.student_union_gui.academic.study_groups.dialogs.success', default="Success"), _t('gui.pastoral.student_union_gui.academic.study_groups.dialogs.study_group_created_successfully', default="Study group created successfully!"), parent=self.dialog)
        self.dialog.destroy()



class ExamPrepGroupsDialog:
    """Exam preparation groups"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.pastoral.student_union_gui.academic.study_groups.windows.exam_preparation_groups', default="Exam Preparation Groups"))
        self.dialog.geometry("1100x750")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_groups()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.academic.study_groups.labels.exam_preparation_groups', default="📝 Exam Preparation Groups"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Info banner
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill='x', pady=(0, 15))

        info_text = ("Join exam-specific study groups to prepare together. Share practice materials, "
                    "quiz each other, and support your peers!")
        ttk.Label(info_frame, text=info_text, wraplength=1000).pack()

        # Filter frame
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(filter_frame, text=_t('gui.pastoral.student_union_gui.academic.study_groups.labels.course', default="Course:")).pack(side='left', padx=(0, 5))
        self.course_var = tk.StringVar()
        course_combo = ttk.Combobox(filter_frame, textvariable=self.course_var, width=25, state='readonly')
        self.course_combo = course_combo
        course_combo['values'] = ('All Courses',)
        course_combo.current(0)
        course_combo.pack(side='left', padx=(0, 15))

        ttk.Button(filter_frame, text=_t('gui.pastoral.student_union_gui.academic.study_groups.buttons.filter', default="Filter"), command=self.load_groups).pack(side='left', padx=(0, 20))
        ttk.Button(filter_frame, text=_t('gui.pastoral.student_union_gui.academic.study_groups.buttons.create_exam_prep_group', default="➕ Create Exam Prep Group"),
                  command=self.create_group).pack(side='left')

        # Groups list
        list_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.academic.study_groups.labels.upcoming_exam_prep_groups', default="Upcoming Exam Prep Groups"))
        list_frame.pack(fill='both', expand=True, pady=(0, 15))

        columns = ('Course', 'Exam Date', 'Group Name', 'Members', 'Next Session', 'Focus')
        self.groups_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=12)

        for col in columns:
            self.groups_tree.heading(col, text=col)
            if col == 'Group Name':
                self.groups_tree.column(col, width=180)
            elif col == 'Focus':
                self.groups_tree.column(col, width=200)
            else:
                self.groups_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.groups_tree.yview)
        self.groups_tree.configure(yscrollcommand=scrollbar.set)

        self.groups_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.academic.study_groups.buttons.join_group', default="Join Group"), command=self.join_group).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.academic.study_groups.buttons.view_study_schedule', default="View Study Schedule"), command=self.view_schedule).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.academic.study_groups.buttons.practice_tests', default="Practice Tests"), command=self.practice_tests).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.academic.study_groups.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='right')

    def load_groups(self):
        """Study groups with an exam date set (study_groups.study_date)."""
        self._groups = {}
        course = self.course_var.get()
        course = None if course in ('', 'All Courses') else course
        try:
            with hub_conn() as conn:
                self.course_combo['values'] = ['All Courses'] + hub.course_options(conn, owner_id(conn, self.auth))
                groups = hub.list_study_groups(conn, course, exam_prep=True)
        except Exception as e:
            report_error(self.dialog, e)
            return
        rows = []
        for g in groups:
            self._groups[g['group_id']] = g
            rows.append((g['group_id'], (g['course_id'], g['study_date'], g['group_name'],
                                         f"{g['members']}/{g['max_members'] or '-'}",
                                         g['next_session'] or 'None scheduled',
                                         g['topic'] or g['description'] or '-')))
        fill_tree(self.groups_tree, rows,
                  "No exam preparation groups yet - use 'Create Exam Prep Group'.")

    def _selected_group(self):
        g = self._groups.get(selected_id(self.groups_tree))
        if not g:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.academic.study_groups.dialogs.warning', default="Warning"), _t('gui.pastoral.student_union_gui.academic.study_groups.dialogs.please_select_an_exam_prep_group', default="Please select an exam prep group."), parent=self.dialog)
        return g

    def join_group(self):
        g = self._selected_group()
        if not g:
            return
        if not messagebox.askyesno(_t('gui.pastoral.student_union_gui.academic.study_groups.dialogs.confirm', default="Confirm"), f"Join '{g['group_name']}'?", parent=self.dialog):
            return
        try:
            with hub_conn() as conn:
                hub.join_study_group(conn, g['group_id'], owner_id(conn, self.auth))
        except Exception as e:
            report_error(self.dialog, e)
            return
        messagebox.showinfo(_t('gui.pastoral.student_union_gui.academic.study_groups.dialogs.success', default="Success"),
                            f"You've joined '{g['group_name']}'.", parent=self.dialog)
        self.load_groups()

    def create_group(self):
        try:
            with hub_conn() as conn:
                courses = hub.course_options(conn, owner_id(conn, self.auth))
        except Exception as e:
            report_error(self.dialog, e)
            return
        form = ask_form(self.dialog, _t('gui.pastoral.student_union_gui.academic.study_groups.dialogs.create_group', default="Create Group"), [
            ('course', "Course / module code:", 'combo', courses, courses[0] if courses else ''),
            ('exam', "Exam date (YYYY-MM-DD):", 'entry', None, ''),
            ('name', "Group name:", 'entry', None, ''),
            ('focus', "Focus topics:", 'entry', None, ''),
            ('schedule', "Meeting schedule:", 'entry', None, ''),
            ('location', "Location:", 'entry', None, ''),
            ('limit', "Member limit:", 'spin', (2, 30), 10),
        ], submit_text="Create")
        if not form:
            return
        if not form['exam']:
            messagebox.showwarning("Exam Date", "An exam prep group needs its exam date.", parent=self.dialog)
            return
        try:
            with hub_conn() as conn:
                hub.create_study_group(conn, owner_id(conn, self.auth), course_id=form['course'],
                                       group_name=form['name'], max_members=form['limit'],
                                       meeting_schedule=form['schedule'], location=form['location'],
                                       exam_date=form['exam'], focus=form['focus'])
        except Exception as e:
            report_error(self.dialog, e)
            return
        self.load_groups()

    def view_schedule(self):
        g = self._selected_group()
        if not g:
            return
        try:
            with hub_conn() as conn:
                sessions = hub.group_sessions(conn, g['group_id'])
        except Exception as e:
            report_error(self.dialog, e)
            return
        rows = [(s['session_id'], (s['session_at'], s['location'] or '-', s['agenda'] or ''))
                for s in sessions]

        def add(tree, win):
            win.destroy()
            schedule_group_session(self.dialog, self.auth, g)
            self.load_groups()

        show_list(self.dialog, _t('gui.pastoral.student_union_gui.academic.study_groups.dialogs.study_schedule', default="Study Schedule") + f" - {g['group_name']} (exam {g['study_date']})",
                  ('When', 'Location', 'Agenda'), rows,
                  "No sessions scheduled for this group yet.",
                  actions=(("Schedule Session", add),))

    def practice_tests(self):
        g = self._selected_group()
        if not g:
            return
        try:
            with hub_conn() as conn:
                res = hub.practice_resources(conn, g['course_id'])
        except Exception as e:
            report_error(self.dialog, e)
            return
        rows = [(r['resource_id'], (r['resource_title'], r['resource_type'], r['downloads'] or 0,
                                    stars(r['rating']))) for r in res]
        show_list(self.dialog, _t('gui.pastoral.student_union_gui.academic.study_groups.dialogs.practice_tests', default="Practice Tests") + f" - {g['course_id']}",
                  ('Resource', 'Type', 'Downloads', 'Rating'), rows,
                  f"No practice problems or past exams have been shared for {g['course_id']} yet.")
