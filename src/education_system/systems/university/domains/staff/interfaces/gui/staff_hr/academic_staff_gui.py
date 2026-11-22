"""
Academic Staff Management GUI

Features:
- Teaching Portfolio - Teaching philosophy, courses, innovations
- Research Output - Publications, citations, h-index tracking
- Supervisions - PhD/Masters student supervision management
- External Examiners - Examiner appointments and assignments
- Peer Observations - Classroom observation records
"""

from __future__ import annotations

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional
from datetime import datetime

from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.activity_logger import log_activity
from education_system.systems.university.domains.staff.domain.staff_hr.services.managers.academic_staff_manager import (
    AcademicStaffManager,
)
from education_system.systems.university.domains.staff.interfaces.gui.staff_hr import _access as _hr

try:
    from education_system.systems.university.domains.staff.infrastructure.database.staff_hr_schemas_all import (
        get_program_types, get_observation_types
    )
except ImportError:
    get_program_types = lambda: ['phd', 'masters', 'undergraduate']
    get_observation_types = lambda: ['formal', 'informal', 'peer']


def _err():
    return _t('gui.staff.staff_hr.academic_staff.dialogs.error', default="Error")


def _warn():
    return _t('gui.staff.staff_hr.academic_staff.dialogs.warning', default="Warning")


def _ok():
    return _t('gui.staff.staff_hr.academic_staff.dialogs.success', default="Success")


class AcademicStaffGUI:
    """Academic Staff Management GUI with multiple tabs."""

    def __init__(self, root, auth: Optional[UserAuth] = None, parent_notebook=None):
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth and auth.current_user else None

        if not self.current_user:
            return

        self.manager = AcademicStaffManager()
        self.username = _hr.user_key(self)
        self.is_hr = _hr.can(self, 'hr')

        if parent_notebook:
            self.tab = ttk.Frame(parent_notebook)
            parent_notebook.add(self.tab, text=_t('gui.staff.staff_hr.academic_staff.tabs.academic_staff', default="Academic Staff"))
            self._create_content(self.tab)
        else:
            self._create_standalone_window()

    def _create_standalone_window(self):
        """Create standalone window when not embedded."""
        self.window = tk.Toplevel(self.root)
        self.window.title(_t('gui.staff.staff_hr.academic_staff.windows.academic_staff_management', default="Academic Staff Management"))
        self.window.geometry("1400x900")
        self.window.minsize(1200, 800)

        bottom_frame = ttk.Frame(self.window)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        ttk.Button(bottom_frame, text=_t('gui.staff.staff_hr.academic_staff.buttons.close', default="Close"), command=self.window.destroy).pack(side=tk.RIGHT, padx=5)

        self.status_bar = ttk.Label(self.window, text=_t('gui.staff.staff_hr.academic_staff.labels.ready', default="Ready"), relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self._create_content(self.window)

    def _create_content(self, parent):
        """Create the main content with notebook tabs."""
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._create_teaching_portfolio_tab()
        self._create_research_output_tab()
        self._create_supervisions_tab()
        self._create_examiners_tab()
        self._create_peer_observations_tab()

    # ================================================================
    # TEACHING PORTFOLIO TAB
    # ================================================================

    def _create_teaching_portfolio_tab(self):
        """Create Teaching Portfolio tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t('gui.staff.staff_hr.academic_staff.tabs.teaching_portfolio', default="Teaching Portfolio"))

        # Scrollable form
        canvas = tk.Canvas(tab)
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        form_frame = ttk.Frame(canvas)

        form_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=form_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y")

        # Teaching Philosophy
        philosophy_frame = ttk.LabelFrame(form_frame, text=_t('gui.staff.staff_hr.academic_staff.labels.teaching_philosophy', default="Teaching Philosophy"), padding=10)
        philosophy_frame.pack(fill=tk.X, padx=10, pady=5)

        self.philosophy_text = tk.Text(philosophy_frame, height=5, width=80)
        self.philosophy_text.pack(fill=tk.X, pady=5)

        # Teaching Interests
        interests_frame = ttk.LabelFrame(form_frame, text=_t('gui.staff.staff_hr.academic_staff.labels.teaching_interests', default="Teaching Interests"), padding=10)
        interests_frame.pack(fill=tk.X, padx=10, pady=5)

        self.interests_text = tk.Text(interests_frame, height=3, width=80)
        self.interests_text.pack(fill=tk.X, pady=5)

        # Courses Taught
        courses_frame = ttk.LabelFrame(form_frame, text=_t('gui.staff.staff_hr.academic_staff.labels.courses_taught', default="Courses Taught"), padding=10)
        courses_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(courses_frame, text=_t('gui.staff.staff_hr.academic_staff.labels.enter_courses_one_per_line', default="Enter courses (one per line):")).pack(anchor=tk.W)
        self.courses_text = tk.Text(courses_frame, height=5, width=80)
        self.courses_text.pack(fill=tk.X, pady=5)

        # Teaching Innovations
        innovations_frame = ttk.LabelFrame(form_frame, text=_t('gui.staff.staff_hr.academic_staff.labels.teaching_innovations_methods', default="Teaching Innovations & Methods"), padding=10)
        innovations_frame.pack(fill=tk.X, padx=10, pady=5)

        self.innovations_text = tk.Text(innovations_frame, height=4, width=80)
        self.innovations_text.pack(fill=tk.X, pady=5)

        # Awards & Recognition
        awards_frame = ttk.LabelFrame(form_frame, text=_t('gui.staff.staff_hr.academic_staff.labels.awards_recognition', default="Awards & Recognition"), padding=10)
        awards_frame.pack(fill=tk.X, padx=10, pady=5)

        self.awards_text = tk.Text(awards_frame, height=3, width=80)
        self.awards_text.pack(fill=tk.X, pady=5)

        # Professional Development
        pd_frame = ttk.LabelFrame(form_frame, text=_t('gui.staff.staff_hr.academic_staff.labels.professional_development', default="Professional Development"), padding=10)
        pd_frame.pack(fill=tk.X, padx=10, pady=5)

        self.pd_text = tk.Text(pd_frame, height=3, width=80)
        self.pd_text.pack(fill=tk.X, pady=5)

        # Buttons
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.academic_staff.buttons.save_portfolio', default="Save Portfolio"), command=self._save_teaching_portfolio).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.academic_staff.buttons.refresh', default="Refresh"), command=self._load_teaching_portfolio).pack(side=tk.LEFT, padx=5)

        self._load_teaching_portfolio()

    def _load_teaching_portfolio(self):
        """Load teaching portfolio data."""
        try:
            row = self.manager.get_teaching_portfolio(self.username, actor=_hr.actor(self))
        except Exception as e:
            messagebox.showerror(_err(), f"Failed to load portfolio: {e}")
            return
        if row:
            for widget, field in self._portfolio_widgets():
                widget.delete('1.0', tk.END)
                widget.insert('1.0', row.get(field) or '')

    def _portfolio_widgets(self):
        return ((self.philosophy_text, 'teaching_philosophy'),
                (self.interests_text, 'teaching_interests'),
                (self.courses_text, 'courses_taught'),
                (self.innovations_text, 'teaching_innovations'),
                (self.awards_text, 'awards_recognition'),
                (self.pd_text, 'professional_development'))

    def _save_teaching_portfolio(self):
        """Save teaching portfolio."""
        data = {field: widget.get('1.0', tk.END).strip() for widget, field in self._portfolio_widgets()}
        try:
            self.manager.update_teaching_portfolio(self.username, actor=_hr.actor(self), **data)
            log_activity('update', 'teaching_portfolio', user_id=self.username)
            messagebox.showinfo(_ok(), _t('gui.staff.staff_hr.academic_staff.dialogs.teaching_portfolio_saved_successfully', default="Teaching portfolio saved successfully"))
        except Exception as e:
            messagebox.showerror(_err(), f"Failed to save portfolio: {e}")

    # ================================================================
    # RESEARCH OUTPUT TAB
    # ================================================================

    def _create_research_output_tab(self):
        """Create Research Output tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t('gui.staff.staff_hr.academic_staff.tabs.research_output', default="Research Output"))

        # Profile frame
        profile_frame = ttk.LabelFrame(tab, text=_t('gui.staff.staff_hr.academic_staff.labels.research_profile', default="Research Profile"), padding=10)
        profile_frame.pack(fill=tk.X, padx=10, pady=5)

        # Metrics
        metrics_frame = ttk.Frame(profile_frame)
        metrics_frame.pack(fill=tk.X, pady=5)

        ttk.Label(metrics_frame, text=_t('gui.staff.staff_hr.academic_staff.labels.h_index', default="h-Index:")).grid(row=0, column=0, sticky=tk.W, padx=5)
        self.h_index_var = tk.StringVar(value="0")
        ttk.Entry(metrics_frame, textvariable=self.h_index_var, width=10).grid(row=0, column=1, sticky=tk.W, padx=5)

        ttk.Label(metrics_frame, text=_t('gui.staff.staff_hr.academic_staff.labels.total_citations', default="Total Citations:")).grid(row=0, column=2, sticky=tk.W, padx=5)
        self.citations_var = tk.StringVar(value="0")
        ttk.Entry(metrics_frame, textvariable=self.citations_var, width=10).grid(row=0, column=3, sticky=tk.W, padx=5)

        ttk.Label(metrics_frame, text=_t('gui.staff.staff_hr.academic_staff.labels.total_publications', default="Total Publications:")).grid(row=0, column=4, sticky=tk.W, padx=5)
        self.publications_var = tk.StringVar(value="0")
        ttk.Entry(metrics_frame, textvariable=self.publications_var, width=10).grid(row=0, column=5, sticky=tk.W, padx=5)

        # IDs frame
        ids_frame = ttk.Frame(profile_frame)
        ids_frame.pack(fill=tk.X, pady=5)

        ttk.Label(ids_frame, text=_t('gui.staff.staff_hr.academic_staff.labels.orcid', default="ORCID:")).grid(row=0, column=0, sticky=tk.W, padx=5)
        self.orcid_var = tk.StringVar()
        ttk.Entry(ids_frame, textvariable=self.orcid_var, width=25).grid(row=0, column=1, sticky=tk.W, padx=5)

        ttk.Label(ids_frame, text=_t('gui.staff.staff_hr.academic_staff.labels.google_scholar', default="Google Scholar:")).grid(row=0, column=2, sticky=tk.W, padx=5)
        self.scholar_var = tk.StringVar()
        ttk.Entry(ids_frame, textvariable=self.scholar_var, width=25).grid(row=0, column=3, sticky=tk.W, padx=5)

        ttk.Label(ids_frame, text=_t('gui.staff.staff_hr.academic_staff.labels.scopus_id', default="Scopus ID:")).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.scopus_var = tk.StringVar()
        ttk.Entry(ids_frame, textvariable=self.scopus_var, width=25).grid(row=1, column=1, sticky=tk.W, padx=5)

        ttk.Label(ids_frame, text=_t('gui.staff.staff_hr.academic_staff.labels.researchgate', default="ResearchGate:")).grid(row=1, column=2, sticky=tk.W, padx=5)
        self.rg_var = tk.StringVar()
        ttk.Entry(ids_frame, textvariable=self.rg_var, width=35).grid(row=1, column=3, sticky=tk.W, padx=5)

        # Research Interests
        interests_frame = ttk.LabelFrame(tab, text=_t('gui.staff.staff_hr.academic_staff.labels.research_interests', default="Research Interests"), padding=10)
        interests_frame.pack(fill=tk.X, padx=10, pady=5)

        self.research_interests_text = tk.Text(interests_frame, height=4, width=80)
        self.research_interests_text.pack(fill=tk.X, pady=5)

        # Buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.academic_staff.buttons.save_research_profile', default="Save Research Profile"), command=self._save_research_profile).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.academic_staff.buttons.refresh', default="Refresh"), command=self._load_research_profile).pack(side=tk.LEFT, padx=5)

        # Summary section
        summary_frame = ttk.LabelFrame(tab, text=_t('gui.staff.staff_hr.academic_staff.labels.publication_summary', default="Publication Summary"), padding=10)
        summary_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.research_summary = tk.Text(summary_frame, height=10, state=tk.DISABLED)
        self.research_summary.pack(fill=tk.BOTH, expand=True)

        self._load_research_profile()

    def _load_research_profile(self):
        """Load research profile data and the person's recorded outputs."""
        try:
            row = self.manager.get_research_profile(self.username, actor=_hr.actor(self))
            if row:
                self.research_interests_text.delete('1.0', tk.END)
                self.research_interests_text.insert('1.0', row.get('research_interests') or '')
                self.h_index_var.set(str(row.get('h_index') or 0))
                self.citations_var.set(str(row.get('total_citations') or 0))
                self.publications_var.set(str(row.get('total_publications') or 0))
                self.orcid_var.set(row.get('orcid_id') or '')
                self.scholar_var.set(row.get('google_scholar_id') or '')
                self.rg_var.set(row.get('researchgate_url') or '')
                self.scopus_var.set(row.get('scopus_id') or '')

            pubs = self.manager.get_publications(self.username, actor=_hr.actor(self), limit=10)
            self.research_summary.config(state=tk.NORMAL)
            self.research_summary.delete('1.0', tk.END)
            if pubs:
                for pub in pubs:
                    self.research_summary.insert(tk.END, f"- {pub['title']}\n")
                    self.research_summary.insert(
                        tk.END, f"  Type: {pub.get('publication_type') or '-'}, "
                                f"Date: {pub.get('publication_date') or '-'}, "
                                f"Citations: {pub.get('citation_count') or 0}\n\n")
            else:
                self.research_summary.insert(tk.END, "No publications found in the system.\n")
                self.research_summary.insert(tk.END, "Publications may be tracked in the Research module.")
            self.research_summary.config(state=tk.DISABLED)

        except Exception as e:
            messagebox.showerror(_err(), f"Failed to load research profile: {e}")

    def _save_research_profile(self):
        """Save research profile."""
        try:
            self.manager.update_research_profile(
                self.username, actor=_hr.actor(self),
                research_interests=self.research_interests_text.get('1.0', tk.END).strip(),
                h_index=self.h_index_var.get(),
                total_citations=self.citations_var.get(),
                total_publications=self.publications_var.get(),
                orcid_id=self.orcid_var.get().strip(), google_scholar_id=self.scholar_var.get().strip(),
                researchgate_url=self.rg_var.get().strip(), scopus_id=self.scopus_var.get().strip())
            log_activity('update', 'research_profile', user_id=self.username)
            messagebox.showinfo(_ok(), _t('gui.staff.staff_hr.academic_staff.dialogs.research_profile_saved_successfully', default="Research profile saved successfully"))
        except Exception as e:
            messagebox.showerror(_err(), f"Failed to save profile: {e}")

    # ================================================================
    # SUPERVISIONS TAB
    # ================================================================

    def _create_supervisions_tab(self):
        """Create Student Supervisions tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t('gui.staff.staff_hr.academic_staff.tabs.supervisions', default="Supervisions"))

        # Buttons frame
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.academic_staff.buttons.add_supervision', default="Add Supervision"), command=self._add_supervision).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.academic_staff.buttons.edit_supervision', default="Edit Supervision"), command=self._edit_supervision).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.academic_staff.buttons.update_progress', default="Update Progress"), command=self._update_supervision_progress).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.academic_staff.buttons.refresh', default="Refresh"), command=self._load_supervisions).pack(side=tk.LEFT, padx=5)

        # Filter frame
        filter_frame = ttk.Frame(tab)
        filter_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(filter_frame, text=_t('gui.staff.staff_hr.academic_staff.labels.status', default="Status:")).pack(side=tk.LEFT, padx=5)
        self.supervision_status_var = tk.StringVar(value=_t('gui.staff.staff_hr.academic_staff.values.all', default="All"))
        ttk.Combobox(filter_frame, textvariable=self.supervision_status_var,
                     values=["All", "requested", "active", "completed", "withdrawn", "declined"],
                     width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(filter_frame, text=_t('gui.staff.staff_hr.academic_staff.buttons.filter', default="Filter"), command=self._load_supervisions).pack(side=tk.LEFT, padx=5)

        # Supervisions list
        list_frame = ttk.Frame(tab)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ('ID', 'Student', 'Program', 'Thesis Title', 'Role', 'Start', 'Expected End', 'Status')
        self.supervisions_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.supervisions_tree.heading(col, text=col)
            self.supervisions_tree.column(col, width=100)

        self.supervisions_tree.column('ID', width=50)
        self.supervisions_tree.column('Thesis Title', width=200)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.supervisions_tree.yview)
        self.supervisions_tree.configure(yscrollcommand=scrollbar.set)

        self.supervisions_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Status tags
        self.supervisions_tree.tag_configure('active', background='#90EE90')
        self.supervisions_tree.tag_configure('completed', background='#87CEEB')
        self.supervisions_tree.tag_configure('withdrawn', background='#D3D3D3')

        self._load_supervisions()

    def _load_supervisions(self):
        """Load supervisions data."""
        status_filter = self.supervision_status_var.get()

        self.supervisions_tree.delete(*self.supervisions_tree.get_children())

        try:
            rows = self.manager.get_supervisions(
                self.username, None if status_filter == "All" else status_filter,
                actor=_hr.actor(self))
            for row in rows:
                status = row.get('status') or 'active'
                self.supervisions_tree.insert('', 'end', values=(
                    row['supervision_id'], row.get('student_name') or '', row.get('program_type') or '',
                    row.get('thesis_title') or '', row.get('supervision_role') or '',
                    row.get('start_date') or '', row.get('expected_end_date') or '', status),
                    tags=(status,))
        except Exception as e:
            messagebox.showerror(_err(), f"Failed to load supervisions: {e}")

    def _add_supervision(self):
        """Add new supervision."""
        self._supervision_dialog()

    def _edit_supervision(self):
        """Edit selected supervision."""
        selection = self.supervisions_tree.selection()
        if not selection:
            messagebox.showwarning(_warn(), _t('gui.staff.staff_hr.academic_staff.dialogs.please_select_a_supervision_to_edit', default="Please select a supervision to edit"))
            return

        item = self.supervisions_tree.item(selection[0])
        supervision_id = item['values'][0]
        self._supervision_dialog(supervision_id)

    def _supervision_dialog(self, supervision_id=None):
        """Show supervision add/edit dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Supervision" if supervision_id else "Add Supervision")
        dialog.geometry("500x500")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.academic_staff.labels.student_name', default="Student Name:")).pack(pady=5)
        student_name_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=student_name_var, width=40).pack(pady=5)

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.academic_staff.labels.student_id_optional', default="Student ID (optional):")).pack(pady=5)
        student_id_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=student_id_var, width=20).pack(pady=5)

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.academic_staff.labels.program_type', default="Program Type:")).pack(pady=5)
        program_var = tk.StringVar()
        ttk.Combobox(dialog, textvariable=program_var, values=get_program_types(), width=20).pack(pady=5)

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.academic_staff.labels.thesis_title', default="Thesis Title:")).pack(pady=5)
        thesis_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=thesis_var, width=50).pack(pady=5)

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.academic_staff.labels.supervision_role', default="Supervision Role:")).pack(pady=5)
        role_var = tk.StringVar(value=_t('gui.staff.staff_hr.academic_staff.values.primary', default="primary"))
        ttk.Combobox(dialog, textvariable=role_var,
                     values=['primary', 'secondary', 'advisor', 'co-supervisor'],
                     width=20).pack(pady=5)

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.academic_staff.labels.start_date_yyyy_mm_dd', default="Start Date (YYYY-MM-DD):")).pack(pady=5)
        start_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=start_var, width=15).pack(pady=5)

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.academic_staff.labels.expected_end_date_yyyy_mm_dd', default="Expected End Date (YYYY-MM-DD):")).pack(pady=5)
        end_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=end_var, width=15).pack(pady=5)

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.academic_staff.labels.status', default="Status:")).pack(pady=5)
        status_var = tk.StringVar(value=_t('gui.staff.staff_hr.academic_staff.values.active', default="active"))
        ttk.Combobox(dialog, textvariable=status_var,
                     values=['requested', 'active', 'completed', 'withdrawn', 'declined'],
                     width=15).pack(pady=5)

        # Load existing data if editing
        if supervision_id:
            try:
                row = self.manager.get_supervision(supervision_id, actor=_hr.actor(self))
                if row:
                    student_name_var.set(row.get('student_name') or '')
                    student_id_var.set(row.get('student_id') or '')
                    program_var.set(row.get('program_type') or '')
                    thesis_var.set(row.get('thesis_title') or '')
                    role_var.set(row.get('supervision_role') or 'primary')
                    start_var.set(row.get('start_date') or '')
                    end_var.set(row.get('expected_end_date') or '')
                    status_var.set(row.get('status') or 'active')
            except Exception as e:
                messagebox.showerror(_err(), f"Failed to load supervision: {e}", parent=dialog)

        def save():
            if not student_name_var.get().strip():
                messagebox.showwarning(_warn(), _t('gui.staff.staff_hr.academic_staff.dialogs.please_enter_student_name', default="Please enter student name"))
                return

            data = dict(student_name=student_name_var.get().strip(),
                        thesis_title=thesis_var.get().strip(), supervision_role=role_var.get(),
                        start_date=start_var.get().strip() or None,
                        expected_end_date=end_var.get().strip() or None, status=status_var.get())
            try:
                if supervision_id:
                    self.manager.update_supervision(
                        supervision_id, actor=_hr.actor(self), student_id=student_id_var.get().strip(),
                        program_type=program_var.get(), **data)
                else:
                    self.manager.add_supervision(
                        self.username, student_id_var.get().strip(), program_var.get(),
                        actor=_hr.actor(self), **data)

                log_activity('update' if supervision_id else 'create', 'student_supervision', user_id=self.username)
                messagebox.showinfo(_ok(), _t('gui.staff.staff_hr.academic_staff.dialogs.supervision_saved_successfully', default="Supervision saved successfully"))
                dialog.destroy()
                self._load_supervisions()
            except Exception as e:
                messagebox.showerror(_err(), f"Failed to save supervision: {e}", parent=dialog)

        ttk.Button(dialog, text=_t('gui.staff.staff_hr.academic_staff.buttons.save', default="Save"), command=save).pack(pady=20)

    def _update_supervision_progress(self):
        """Update progress notes for supervision."""
        selection = self.supervisions_tree.selection()
        if not selection:
            messagebox.showwarning(_warn(), _t('gui.staff.staff_hr.academic_staff.dialogs.please_select_a_supervision', default="Please select a supervision"))
            return

        item = self.supervisions_tree.item(selection[0])
        supervision_id = item['values'][0]
        student_name = item['values'][1]

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Progress Notes - {student_name}")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.academic_staff.labels.progress_notes', default="Progress Notes:")).pack(pady=5)
        notes_text = tk.Text(dialog, height=15, width=60)
        notes_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Load existing notes
        try:
            row = self.manager.get_supervision(supervision_id, actor=_hr.actor(self))
            if row and row.get('progress_notes'):
                notes_text.insert('1.0', row['progress_notes'])
        except Exception as e:
            messagebox.showerror(_err(), f"Failed to load notes: {e}", parent=dialog)

        def save_notes():
            try:
                self.manager.update_supervision(supervision_id, actor=_hr.actor(self),
                                                progress_notes=notes_text.get('1.0', tk.END).strip())
                messagebox.showinfo(_ok(), _t('gui.staff.staff_hr.academic_staff.dialogs.progress_notes_saved', default="Progress notes saved"))
                dialog.destroy()
            except Exception as e:
                messagebox.showerror(_err(), f"Failed to save notes: {e}", parent=dialog)

        ttk.Button(dialog, text=_t('gui.staff.staff_hr.academic_staff.buttons.save_notes', default="Save Notes"), command=save_notes).pack(pady=10)

    # ================================================================
    # EXTERNAL EXAMINERS TAB
    # ================================================================

    def _create_examiners_tab(self):
        """Create External Examiners tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t('gui.staff.staff_hr.academic_staff.tabs.external_examiners', default="External Examiners"))

        # Examiner appointments are HR's to record.
        is_admin = self.is_hr

        # Buttons frame
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)

        if is_admin:
            ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.academic_staff.buttons.add_examiner', default="Add Examiner"), command=self._add_examiner).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.academic_staff.buttons.edit_examiner', default="Edit Examiner"), command=self._edit_examiner).pack(side=tk.LEFT, padx=5)

        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.academic_staff.buttons.view_assignments', default="View Assignments"), command=self._view_examiner_assignments).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.academic_staff.buttons.refresh', default="Refresh"), command=self._load_examiners).pack(side=tk.LEFT, padx=5)

        # Examiners list
        list_frame = ttk.Frame(tab)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ('ID', 'Name', 'Institution', 'Expertise', 'Department', 'Start', 'End', 'Status')
        self.examiners_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.examiners_tree.heading(col, text=col)
            self.examiners_tree.column(col, width=100)

        self.examiners_tree.column('ID', width=50)
        self.examiners_tree.column('Name', width=150)
        self.examiners_tree.column('Institution', width=150)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.examiners_tree.yview)
        self.examiners_tree.configure(yscrollcommand=scrollbar.set)

        self.examiners_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_examiners()

    def _load_examiners(self):
        """Load external examiners."""
        self.examiners_tree.delete(*self.examiners_tree.get_children())

        try:
            for row in self.manager.get_external_examiners(active_only=False):
                self.examiners_tree.insert('', 'end', values=(
                    row['examiner_id'], row.get('name') or '', row.get('institution') or '',
                    row.get('expertise_area') or '', row.get('department') or '',
                    row.get('appointment_start') or '', row.get('appointment_end') or '',
                    row.get('status') or ''))
        except Exception as e:
            messagebox.showerror(_err(), f"Failed to load examiners: {e}")

    def _add_examiner(self):
        """Add new external examiner."""
        self._examiner_dialog()

    def _edit_examiner(self):
        """Edit selected examiner."""
        selection = self.examiners_tree.selection()
        if not selection:
            messagebox.showwarning(_warn(), _t('gui.staff.staff_hr.academic_staff.dialogs.please_select_an_examiner_to_edit', default="Please select an examiner to edit"))
            return

        item = self.examiners_tree.item(selection[0])
        examiner_id = item['values'][0]
        self._examiner_dialog(examiner_id)

    def _examiner_dialog(self, examiner_id=None):
        """Show examiner add/edit dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Examiner" if examiner_id else "Add Examiner")
        dialog.geometry("450x450")
        dialog.transient(self.root)
        dialog.grab_set()

        fields = {}

        for label, width in [
            ("Name:", 40), ("Institution:", 40), ("Email:", 30),
            ("Phone:", 20), ("Expertise Area:", 40), ("Department:", 30),
            ("Appointment Start (YYYY-MM-DD):", 15),
            ("Appointment End (YYYY-MM-DD):", 15)
        ]:
            ttk.Label(dialog, text=label).pack(pady=2)
            var = tk.StringVar()
            ttk.Entry(dialog, textvariable=var, width=width).pack(pady=2)
            fields[label.split(':')[0].lower().replace(' ', '_')] = var

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.academic_staff.labels.status', default="Status:")).pack(pady=2)
        status_var = tk.StringVar(value=_t('gui.staff.staff_hr.academic_staff.values.active', default="active"))
        ttk.Combobox(dialog, textvariable=status_var,
                     values=['active', 'inactive', 'expired'], width=15).pack(pady=2)

        if examiner_id:
            row = self.manager.get_external_examiner(examiner_id)
            if row:
                fields['name'].set(row.get('name') or '')
                fields['institution'].set(row.get('institution') or '')
                fields['email'].set(row.get('email') or '')
                fields['phone'].set(row.get('phone') or '')
                fields['expertise_area'].set(row.get('expertise_area') or '')
                fields['department'].set(row.get('department') or '')
                fields['appointment_start_(yyyy-mm-dd)'].set(row.get('appointment_start') or '')
                fields['appointment_end_(yyyy-mm-dd)'].set(row.get('appointment_end') or '')
                status_var.set(row.get('status') or 'active')

        def save():
            if not fields['name'].get().strip():
                messagebox.showwarning(_warn(), _t('gui.staff.staff_hr.academic_staff.dialogs.please_enter_examiner_name', default="Please enter examiner name"))
                return

            data = dict(institution=fields['institution'].get().strip(),
                        email=fields['email'].get().strip(), phone=fields['phone'].get().strip(),
                        expertise_area=fields['expertise_area'].get().strip(),
                        department=fields['department'].get().strip(),
                        appointment_start=fields['appointment_start_(yyyy-mm-dd)'].get().strip() or None,
                        appointment_end=fields['appointment_end_(yyyy-mm-dd)'].get().strip() or None,
                        status=status_var.get())
            try:
                if examiner_id:
                    self.manager.update_external_examiner(examiner_id, _hr.actor(self),
                                                          name=fields['name'].get().strip(), **data)
                else:
                    self.manager.add_external_examiner(fields['name'].get().strip(),
                                                       actor=_hr.actor(self), **data)

                log_activity('update' if examiner_id else 'create', 'external_examiner', user_id=self.username)
                messagebox.showinfo(_ok(), _t('gui.staff.staff_hr.academic_staff.dialogs.examiner_saved_successfully', default="Examiner saved successfully"))
                dialog.destroy()
                self._load_examiners()
            except Exception as e:
                messagebox.showerror(_err(), f"Failed to save examiner: {e}", parent=dialog)

        ttk.Button(dialog, text=_t('gui.staff.staff_hr.academic_staff.buttons.save', default="Save"), command=save).pack(pady=15)

    def _view_examiner_assignments(self):
        """View examiner assignments."""
        selection = self.examiners_tree.selection()
        if not selection:
            messagebox.showwarning(_warn(), _t('gui.staff.staff_hr.academic_staff.dialogs.please_select_an_examiner', default="Please select an examiner"))
            return

        item = self.examiners_tree.item(selection[0])
        examiner_id = item['values'][0]
        examiner_name = item['values'][1]

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Assignments - {examiner_name}")
        dialog.geometry("600x400")
        dialog.transient(self.root)

        columns = ('ID', 'Student', 'Type', 'Year', 'Report', 'Date')
        tree = ttk.Treeview(dialog, columns=columns, show='headings', height=15)

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=90)

        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        try:
            for row in self.manager.get_examiner_assignments(examiner_id):
                tree.insert('', 'end', values=(
                    row['assignment_id'], row.get('student_name') or 'N/A',
                    row.get('assignment_type') or 'N/A', row.get('academic_year') or 'N/A',
                    'Yes' if row.get('report_submitted') else 'No', row.get('report_date') or 'N/A'
                ))
        except Exception as e:
            messagebox.showerror(_err(), f"Failed to load assignments: {e}", parent=dialog)

        ttk.Button(dialog, text=_t('gui.staff.staff_hr.academic_staff.buttons.close', default="Close"), command=dialog.destroy).pack(pady=10)

    # ================================================================
    # PEER OBSERVATIONS TAB
    # ================================================================

    def _create_peer_observations_tab(self):
        """Create Peer Observations tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t('gui.staff.staff_hr.academic_staff.tabs.peer_observations', default="Peer Observations"))

        # Buttons frame
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.academic_staff.buttons.new_observation', default="New Observation"), command=self._add_observation).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.academic_staff.buttons.view_edit', default="View/Edit"), command=self._edit_observation).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.academic_staff.buttons.refresh', default="Refresh"), command=self._load_observations).pack(side=tk.LEFT, padx=5)

        # Filter frame
        filter_frame = ttk.Frame(tab)
        filter_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(filter_frame, text=_t('gui.staff.staff_hr.academic_staff.labels.show', default="Show:")).pack(side=tk.LEFT, padx=5)
        self.obs_view_var = tk.StringVar(value=_t('gui.staff.staff_hr.academic_staff.values.my_observations', default="my_observations"))
        ttk.Combobox(filter_frame, textvariable=self.obs_view_var,
                     values=["my_observations", "observations_of_me", "all"],
                     width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(filter_frame, text=_t('gui.staff.staff_hr.academic_staff.buttons.apply', default="Apply"), command=self._load_observations).pack(side=tk.LEFT, padx=5)

        # Observations list
        list_frame = ttk.Frame(tab)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ('ID', 'Observer', 'Observee', 'Course', 'Date', 'Type', 'Rating', 'Status')
        self.obs_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.obs_tree.heading(col, text=col)
            self.obs_tree.column(col, width=100)

        self.obs_tree.column('ID', width=50)
        self.obs_tree.column('Rating', width=60)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.obs_tree.yview)
        self.obs_tree.configure(yscrollcommand=scrollbar.set)

        self.obs_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Status tags
        self.obs_tree.tag_configure('draft', background='#FFFFE0')
        self.obs_tree.tag_configure('submitted', background='#90EE90')
        self.obs_tree.tag_configure('acknowledged', background='#87CEEB')

        self._load_observations()

    def _load_observations(self):
        """Load peer observations."""
        view = self.obs_view_var.get()

        self.obs_tree.delete(*self.obs_tree.get_children())

        try:
            if view == "my_observations":
                rows = self.manager.get_peer_observations(self.username, 'observer', actor=_hr.actor(self))
            elif view == "observations_of_me":
                rows = self.manager.get_peer_observations(self.username, 'observee', actor=_hr.actor(self))
            else:
                # HR sees every observation; others their own and their reports'.
                rows = self.manager.list_observations(_hr.actor(self))

            for row in rows:
                status = row.get('status') or 'draft'
                self.obs_tree.insert('', 'end', values=(
                    row['observation_id'], row.get('observer_name') or 'N/A',
                    row.get('observee_name') or 'N/A', row.get('course_name') or 'N/A',
                    row.get('observation_date') or 'N/A', row.get('observation_type') or 'N/A',
                    row.get('overall_rating') or 'N/A', status
                ), tags=(status,))
        except Exception as e:
            messagebox.showerror(_err(), f"Failed to load observations: {e}")

    def _add_observation(self):
        """Add new peer observation."""
        self._observation_dialog()

    def _edit_observation(self):
        """Edit selected observation."""
        selection = self.obs_tree.selection()
        if not selection:
            messagebox.showwarning(_warn(), _t('gui.staff.staff_hr.academic_staff.dialogs.please_select_an_observation', default="Please select an observation"))
            return

        item = self.obs_tree.item(selection[0])
        obs_id = item['values'][0]
        self._observation_dialog(obs_id)

    def _observation_dialog(self, obs_id=None):
        """Show observation add/edit dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Observation" if obs_id else "New Peer Observation")
        dialog.geometry("600x700")
        dialog.transient(self.root)
        dialog.grab_set()

        # Scrollable form
        canvas = tk.Canvas(dialog)
        scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
        form_frame = ttk.Frame(canvas)

        form_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=form_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y")

        # Basic info
        basic_frame = ttk.LabelFrame(form_frame, text=_t('gui.staff.staff_hr.academic_staff.labels.basic_information', default="Basic Information"), padding=10)
        basic_frame.pack(fill=tk.X, pady=5)

        ttk.Label(basic_frame, text=_t('gui.staff.staff_hr.academic_staff.labels.observee_staff_being_observed', default="Observee (Staff being observed):")).pack(anchor=tk.W)
        observee_var = tk.StringVar()
        observee_entry = ttk.Entry(basic_frame, textvariable=observee_var, width=40)
        observee_entry.pack(pady=2)
        ttk.Label(basic_frame, text="(their username or staff number)", font=('Arial', 8)).pack(anchor=tk.W)

        ttk.Label(basic_frame, text=_t('gui.staff.staff_hr.academic_staff.labels.course_code_name', default="Course Code/Name:")).pack(anchor=tk.W)
        course_var = tk.StringVar()
        ttk.Entry(basic_frame, textvariable=course_var, width=40).pack(pady=2)

        ttk.Label(basic_frame, text=_t('gui.staff.staff_hr.academic_staff.labels.observation_date_yyyy_mm_dd', default="Observation Date (YYYY-MM-DD):")).pack(anchor=tk.W)
        date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(basic_frame, textvariable=date_var, width=15).pack(pady=2)

        ttk.Label(basic_frame, text=_t('gui.staff.staff_hr.academic_staff.labels.observation_type', default="Observation Type:")).pack(anchor=tk.W)
        type_var = tk.StringVar(value=_t('gui.staff.staff_hr.academic_staff.values.peer', default="peer"))
        ttk.Combobox(basic_frame, textvariable=type_var,
                     values=get_observation_types(), width=20).pack(pady=2)

        ttk.Label(basic_frame, text=_t('gui.staff.staff_hr.academic_staff.labels.class_size', default="Class Size:")).pack(anchor=tk.W)
        size_var = tk.StringVar()
        ttk.Entry(basic_frame, textvariable=size_var, width=10).pack(pady=2)

        ttk.Label(basic_frame, text=_t('gui.staff.staff_hr.academic_staff.labels.duration_minutes', default="Duration (minutes):")).pack(anchor=tk.W)
        duration_var = tk.StringVar()
        ttk.Entry(basic_frame, textvariable=duration_var, width=10).pack(pady=2)

        # Feedback
        feedback_frame = ttk.LabelFrame(form_frame, text=_t('gui.staff.staff_hr.academic_staff.labels.feedback', default="Feedback"), padding=10)
        feedback_frame.pack(fill=tk.X, pady=5)

        ttk.Label(feedback_frame, text=_t('gui.staff.staff_hr.academic_staff.labels.strengths', default="Strengths:")).pack(anchor=tk.W)
        strengths_text = tk.Text(feedback_frame, height=4, width=60)
        strengths_text.pack(pady=2)

        ttk.Label(feedback_frame, text=_t('gui.staff.staff_hr.academic_staff.labels.areas_for_development', default="Areas for Development:")).pack(anchor=tk.W)
        areas_text = tk.Text(feedback_frame, height=4, width=60)
        areas_text.pack(pady=2)

        ttk.Label(feedback_frame, text=_t('gui.staff.staff_hr.academic_staff.labels.action_points', default="Action Points:")).pack(anchor=tk.W)
        actions_text = tk.Text(feedback_frame, height=3, width=60)
        actions_text.pack(pady=2)

        ttk.Label(feedback_frame, text=_t('gui.staff.staff_hr.academic_staff.labels.overall_rating_1_5', default="Overall Rating (1-5):")).pack(anchor=tk.W)
        rating_var = tk.StringVar()
        ttk.Combobox(feedback_frame, textvariable=rating_var,
                     values=['1', '2', '3', '4', '5'], width=5).pack(pady=2)

        ttk.Label(feedback_frame, text=_t('gui.staff.staff_hr.academic_staff.labels.status', default="Status:")).pack(anchor=tk.W)
        status_var = tk.StringVar(value=_t('gui.staff.staff_hr.academic_staff.values.draft', default="draft"))
        ttk.Combobox(feedback_frame, textvariable=status_var,
                     values=['draft', 'submitted'], width=15, state='readonly').pack(pady=2)

        # Load existing data
        record = None
        if obs_id:
            try:
                record = self.manager.get_observation(obs_id, actor=_hr.actor(self))
            except Exception as e:
                messagebox.showerror(_err(), f"Failed to load observation: {e}", parent=dialog)
                dialog.destroy()
                return
            if record:
                observee_var.set(record.get('observee_name') or record.get('observee_id') or '')
                observee_entry.config(state='readonly')
                course_var.set(record.get('course_name') or '')
                date_var.set(record.get('observation_date') or '')
                type_var.set(record.get('observation_type') or 'peer')
                size_var.set(str(record.get('class_size') or ''))
                duration_var.set(str(record.get('duration_minutes') or ''))
                strengths_text.insert('1.0', record.get('strengths') or '')
                areas_text.insert('1.0', record.get('areas_for_development') or '')
                actions_text.insert('1.0', record.get('action_points') or '')
                rating_var.set(str(record.get('overall_rating') or ''))
                status_var.set(record.get('status') or 'draft')

        def save():
            if not observee_var.get().strip():
                messagebox.showwarning(_warn(), _t('gui.staff.staff_hr.academic_staff.dialogs.please_enter_observee_name', default="Please enter observee name"))
                return

            data = dict(course_name=course_var.get().strip(), observation_type=type_var.get(),
                        class_size=size_var.get().strip(), duration_minutes=duration_var.get().strip(),
                        strengths=strengths_text.get('1.0', tk.END).strip(),
                        areas_for_development=areas_text.get('1.0', tk.END).strip(),
                        action_points=actions_text.get('1.0', tk.END).strip(),
                        overall_rating=rating_var.get().strip(), status=status_var.get())
            try:
                if obs_id:
                    self.manager.update_observation(obs_id, _hr.actor(self),
                                                    observation_date=date_var.get().strip(), **data)
                else:
                    self.manager.create_observation(self.username, observee_var.get().strip(),
                                                    date_var.get().strip(), actor=_hr.actor(self), **data)

                log_activity('update' if obs_id else 'create', 'peer_observation', user_id=self.username)
                messagebox.showinfo(_ok(), _t('gui.staff.staff_hr.academic_staff.dialogs.observation_saved_successfully', default="Observation saved successfully"))
                dialog.destroy()
                self._load_observations()
            except Exception as e:
                messagebox.showerror(_err(), f"Failed to save observation: {e}", parent=dialog)

        def acknowledge():
            try:
                self.manager.acknowledge_observation(obs_id, actor=_hr.actor(self))
            except Exception as e:
                messagebox.showerror(_err(), f"Failed to acknowledge: {e}", parent=dialog)
                return
            dialog.destroy()
            self._load_observations()

        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        save_btn = ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.academic_staff.buttons.save', default="Save"), command=save)
        save_btn.pack(side=tk.LEFT, padx=5)
        if record is not None and not record.get('can_edit'):
            # Only the observer edits, and not once it is acknowledged.
            save_btn.config(state=tk.DISABLED)
        if record is not None and record.get('can_acknowledge'):
            ttk.Button(btn_frame, text="Acknowledge", command=acknowledge).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.academic_staff.buttons.cancel', default="Cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)
