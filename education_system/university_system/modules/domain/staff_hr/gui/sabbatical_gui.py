"""
Sabbatical / Study Leave GUI

Provides interface for:
- Sabbatical applications
- Eligibility checking
- Approval workflows
- Progress reporting
- Return planning
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
from typing import Optional

from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.sabbatical_manager import SabbaticalManager
from education_system.university_system.modules.domain.staff_comms.staff_hr.gui.validators import (
    FormValidator, ValidationError, validate_entry, validate_date_entry,
    validate_currency_entry, validate_combobox, show_validation_error
)


class SabbaticalGUI:
    """GUI for sabbatical and study leave management."""

    def __init__(self, root, auth: Optional[UserAuth] = None, parent_notebook: Optional[ttk.Notebook] = None):
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth and auth.current_user else None
        self.parent_notebook = parent_notebook
        self.window = None

        if not self.current_user:
            messagebox.showerror("Error", "Login required to access Sabbatical Management")
            return

        if parent_notebook:
            self.create_as_tab(parent_notebook)
        else:
            self.create_main_window()

    def _get_user_id(self):
        """Get user ID from current user dict."""
        return self.current_user.get('id') or self.current_user.get('username')

    def create_as_tab(self, notebook: ttk.Notebook):
        """Create as a tab in parent notebook."""
        self.tab_frame = ttk.Frame(notebook)
        notebook.add(self.tab_frame, text="Sabbatical")
        self._build_interface(self.tab_frame)

    def create_main_window(self):
        """Create as standalone window."""
        self.window = tk.Toplevel(self.root)
        self.window.title("Sabbatical / Study Leave")
        self.window.geometry("1200x700")
        self.window.minsize(1000, 600)

        bottom_frame = ttk.Frame(self.window)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        ttk.Button(bottom_frame, text="Close", command=self.window.destroy).pack(side=tk.RIGHT, padx=5)

        self.status_bar = ttk.Label(self.window, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self._build_interface(self.window)

    def _build_interface(self, parent):
        """Build the main interface."""
        style = ttk.Style()
        style.configure('Header.TLabel', font=('Arial', 14, 'bold'))

        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._create_applications_tab()
        self._create_apply_tab()
        self._create_progress_tab()

        if self.current_user.get('role') in ['admin', 'Admin', 'administrator', 'staff']:
            self._create_approvals_tab()
            self._create_return_tab()
            self._create_reports_tab()

    # ==================== TAB 1: MY APPLICATIONS ====================

    def _create_applications_tab(self):
        """Create my applications tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="My Applications")

        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="My Sabbatical Applications", style='Header.TLabel').pack(side=tk.LEFT)

        # Filter
        filter_frame = ttk.Frame(header_frame)
        filter_frame.pack(side=tk.RIGHT)
        ttk.Label(filter_frame, text="Status:").pack(side=tk.LEFT, padx=5)
        self.app_status_filter = ttk.Combobox(filter_frame,
            values=['All', 'Draft', 'Pending', 'Approved', 'Active', 'Completed', 'Rejected'],
            width=12, state='readonly')
        self.app_status_filter.set('All')
        self.app_status_filter.pack(side=tk.LEFT, padx=5)
        self.app_status_filter.bind('<<ComboboxSelected>>', lambda e: self._load_applications())
        ttk.Button(filter_frame, text="Refresh", command=self._load_applications).pack(side=tk.LEFT, padx=10)

        # Applications list
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        columns = ('ID', 'Title', 'Type', 'Start', 'End', 'Host Institution', 'Pay %', 'Status')
        self.applications_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                               yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.applications_tree.yview)

        widths = {'ID': 50, 'Title': 200, 'Type': 100, 'Start': 100, 'End': 100,
                  'Host Institution': 180, 'Pay %': 60, 'Status': 100}
        for col in columns:
            self.applications_tree.heading(col, text=col)
            self.applications_tree.column(col, width=widths.get(col, 100))

        self.applications_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.applications_tree.tag_configure('draft', background='#f0f0f0')
        self.applications_tree.tag_configure('pending', background='#fff3cd')
        self.applications_tree.tag_configure('pending_approval', background='#fff3cd')
        self.applications_tree.tag_configure('approved', background='#d4edda')
        self.applications_tree.tag_configure('rejected', background='#f8d7da')
        self.applications_tree.tag_configure('active', background='#cce5ff')
        self.applications_tree.tag_configure('completed', background='#e2e3e5')

        self._load_applications()

    def _load_applications(self):
        """Load user's sabbatical applications."""
        for item in self.applications_tree.get_children():
            self.applications_tree.delete(item)

        status = self.app_status_filter.get().lower()
        if status == 'all':
            status = None
        elif status == 'pending':
            status = 'pending_approval'

        try:
            applications = SabbaticalManager.get_user_applications(self._get_user_id(), status=status)

            for app in applications:
                app_status = app.get('status', '').lower()
                display_status = app_status.replace('_', ' ').title()
                sab_type = app.get('sabbatical_type', '').replace('_', ' ').title()

                self.applications_tree.insert('', tk.END, values=(
                    app.get('application_id'),
                    app.get('title', ''),
                    sab_type,
                    app.get('start_date', ''),
                    app.get('end_date', ''),
                    app.get('host_institution', ''),
                    f"{app.get('pay_percentage', 100)}%",
                    display_status
                ), tags=(app_status,))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load applications: {e}")

    # ==================== TAB 2: APPLY ====================

    def _create_apply_tab(self):
        """Create apply for sabbatical tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Apply")

        # Scrollable canvas for long form
        canvas = tk.Canvas(tab)
        scrollbar = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=scroll_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        header_frame = ttk.Frame(scroll_frame)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Apply for Sabbatical", style='Header.TLabel').pack(side=tk.LEFT)

        # Eligibility status frame
        elig_frame = ttk.LabelFrame(scroll_frame, text="Eligibility Status", padding=15)
        elig_frame.pack(fill=tk.X, padx=10, pady=10)

        elig_info_frame = ttk.Frame(elig_frame)
        elig_info_frame.pack(fill=tk.X)

        self.elig_labels = {}
        for key, label_text in [('years', 'Years of Service:'), ('last', 'Last Sabbatical:'),
                                ('status', 'Eligibility Status:')]:
            row_frame = ttk.Frame(elig_info_frame)
            row_frame.pack(fill=tk.X, pady=3)
            ttk.Label(row_frame, text=label_text, font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=10)
            self.elig_labels[key] = ttk.Label(row_frame, text="--")
            self.elig_labels[key].pack(side=tk.LEFT, padx=10)

        ttk.Button(elig_frame, text="Check Eligibility", command=self._check_eligibility).pack(pady=10)

        self._check_eligibility()

        # Application form
        form_frame = ttk.LabelFrame(scroll_frame, text="Application Details", padding=15)
        form_frame.pack(fill=tk.X, padx=10, pady=10)

        # Row 0: Type
        ttk.Label(form_frame, text="Type:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        self.type_combo = ttk.Combobox(form_frame, width=25, state='readonly',
            values=['research', 'teaching_development', 'industry', 'study'])
        self.type_combo.set('research')
        self.type_combo.grid(row=0, column=1, padx=10, pady=8, sticky='w')

        # Row 1: Title
        ttk.Label(form_frame, text="Title:").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        self.title_entry = ttk.Entry(form_frame, width=50)
        self.title_entry.grid(row=1, column=1, columnspan=3, padx=10, pady=8, sticky='w')

        # Row 2: Research Proposal
        ttk.Label(form_frame, text="Research Proposal:").grid(row=2, column=0, sticky='ne', padx=10, pady=8)
        self.proposal_text = scrolledtext.ScrolledText(form_frame, width=60, height=8)
        self.proposal_text.grid(row=2, column=1, columnspan=3, padx=10, pady=8, sticky='w')

        # Row 3: Host Institution
        ttk.Label(form_frame, text="Host Institution:").grid(row=3, column=0, sticky='e', padx=10, pady=8)
        self.institution_entry = ttk.Entry(form_frame, width=50)
        self.institution_entry.grid(row=3, column=1, columnspan=3, padx=10, pady=8, sticky='w')

        # Row 4: Start Date and End Date
        ttk.Label(form_frame, text="Start Date:").grid(row=4, column=0, sticky='e', padx=10, pady=8)
        self.start_date_entry = ttk.Entry(form_frame, width=15)
        self.start_date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        self.start_date_entry.grid(row=4, column=1, padx=10, pady=8, sticky='w')

        ttk.Label(form_frame, text="End Date:").grid(row=4, column=2, sticky='e', padx=10, pady=8)
        self.end_date_entry = ttk.Entry(form_frame, width=15)
        self.end_date_entry.grid(row=4, column=3, padx=10, pady=8, sticky='w')

        # Row 5: Pay Percentage
        ttk.Label(form_frame, text="Pay Percentage:").grid(row=5, column=0, sticky='e', padx=10, pady=8)
        self.pay_combo = ttk.Combobox(form_frame, width=10, state='readonly',
            values=['100', '80', '60', '50', '0'])
        self.pay_combo.set('100')
        self.pay_combo.grid(row=5, column=1, padx=10, pady=8, sticky='w')

        # Row 6: Cover Arrangements
        ttk.Label(form_frame, text="Cover Arrangements:").grid(row=6, column=0, sticky='ne', padx=10, pady=8)
        self.cover_text = scrolledtext.ScrolledText(form_frame, width=60, height=4)
        self.cover_text.grid(row=6, column=1, columnspan=3, padx=10, pady=8, sticky='w')

        # Row 7: Funding Details
        ttk.Label(form_frame, text="Funding Details:").grid(row=7, column=0, sticky='e', padx=10, pady=8)
        self.funding_entry = ttk.Entry(form_frame, width=50)
        self.funding_entry.grid(row=7, column=1, columnspan=3, padx=10, pady=8, sticky='w')

        # Buttons
        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=8, column=0, columnspan=4, pady=15)
        ttk.Button(btn_frame, text="Save Draft", command=self._save_draft).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="Submit", command=self._submit_application).pack(side=tk.LEFT, padx=10)

    def _check_eligibility(self):
        """Check and display eligibility status."""
        try:
            eligibility = SabbaticalManager.check_eligibility(self._get_user_id())

            years = eligibility.get('years_of_service', 0)
            self.elig_labels['years'].config(text=f"{years:.1f} years")

            last_sab = eligibility.get('last_sabbatical_end')
            self.elig_labels['last'].config(text=last_sab if last_sab else "None")

            is_eligible = eligibility.get('is_eligible', False)
            reason = eligibility.get('reason', '')
            if is_eligible:
                self.elig_labels['status'].config(text="Eligible", foreground='green')
            else:
                self.elig_labels['status'].config(text=f"Not Eligible - {reason}", foreground='red')
        except Exception as e:
            self.elig_labels['status'].config(text=f"Error: {e}", foreground='red')

    def _get_form_data(self):
        """Gather application form data with validation."""
        try:
            title = validate_entry(self.title_entry, "Title")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return None

        try:
            sab_type = validate_combobox(self.type_combo, "Type")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return None

        try:
            start_date = validate_date_entry(self.start_date_entry, "Start Date")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return None

        try:
            end_date = validate_date_entry(self.end_date_entry, "End Date")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return None

        proposal = self.proposal_text.get("1.0", "end-1c").strip()
        institution = self.institution_entry.get().strip()
        pay_pct = int(self.pay_combo.get())
        cover = self.cover_text.get("1.0", "end-1c").strip()
        funding = self.funding_entry.get().strip()

        return {
            'title': title,
            'sabbatical_type': sab_type,
            'research_proposal': proposal or None,
            'host_institution': institution or None,
            'start_date': start_date,
            'end_date': end_date,
            'pay_percentage': pay_pct,
            'cover_arrangements': cover or None,
            'funding_details': funding or None,
        }

    def _save_draft(self):
        """Save application as draft."""
        data = self._get_form_data()
        if not data:
            return

        try:
            app_id = SabbaticalManager.create_application(
                self._get_user_id(),
                title=data['title'],
                sabbatical_type=data['sabbatical_type'],
                research_proposal=data['research_proposal'],
                host_institution=data['host_institution'],
                start_date=data['start_date'],
                end_date=data['end_date'],
                pay_percentage=data['pay_percentage'],
                cover_arrangements=data['cover_arrangements'],
                funding_details=data['funding_details'],
            )
            messagebox.showinfo("Success", f"Draft saved successfully. Application ID: {app_id}")
            self._clear_apply_form()
            self._load_applications()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _submit_application(self):
        """Submit application for approval."""
        data = self._get_form_data()
        if not data:
            return

        if not messagebox.askyesno("Confirm",
                "Are you sure you want to submit this application for approval?\n\n"
                "Once submitted, the application cannot be edited."):
            return

        try:
            app_id = SabbaticalManager.create_application(
                self._get_user_id(),
                title=data['title'],
                sabbatical_type=data['sabbatical_type'],
                research_proposal=data['research_proposal'],
                host_institution=data['host_institution'],
                start_date=data['start_date'],
                end_date=data['end_date'],
                pay_percentage=data['pay_percentage'],
                cover_arrangements=data['cover_arrangements'],
                funding_details=data['funding_details'],
            )

            SabbaticalManager.submit_application(app_id, self._get_user_id())
            messagebox.showinfo("Success",
                f"Application submitted successfully. Application ID: {app_id}\n\n"
                "Your application will be reviewed through the approval workflow.")
            self._clear_apply_form()
            self._load_applications()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _clear_apply_form(self):
        """Clear the application form fields."""
        self.type_combo.set('research')
        self.title_entry.delete(0, tk.END)
        self.proposal_text.delete("1.0", tk.END)
        self.institution_entry.delete(0, tk.END)
        self.start_date_entry.delete(0, tk.END)
        self.start_date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        self.end_date_entry.delete(0, tk.END)
        self.pay_combo.set('100')
        self.cover_text.delete("1.0", tk.END)
        self.funding_entry.delete(0, tk.END)

    # ==================== TAB 3: PROGRESS REPORTS ====================

    def _create_progress_tab(self):
        """Create progress reports tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Progress Reports")

        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Progress Reports", style='Header.TLabel').pack(side=tk.LEFT)

        # Application selector
        selector_frame = ttk.LabelFrame(tab, text="Select Sabbatical", padding=10)
        selector_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(selector_frame, text="Application:").pack(side=tk.LEFT, padx=10)
        self.progress_app_combo = ttk.Combobox(selector_frame, width=50, state='readonly')
        self.progress_app_combo.pack(side=tk.LEFT, padx=10)
        self.progress_app_combo.bind('<<ComboboxSelected>>', lambda e: self._load_progress_reports())
        ttk.Button(selector_frame, text="Refresh", command=self._refresh_progress_tab).pack(side=tk.RIGHT, padx=10)

        self._progress_app_map = {}
        self._load_progress_applications()

        # Existing reports
        reports_frame = ttk.LabelFrame(tab, text="Existing Reports", padding=10)
        reports_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        y_scroll = ttk.Scrollbar(reports_frame, orient=tk.VERTICAL)
        columns = ('ID', 'Type', 'Date', 'Status', 'Reviewer Comments')
        self.progress_tree = ttk.Treeview(reports_frame, columns=columns, show='headings',
                                           height=6, yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.progress_tree.yview)

        widths = {'ID': 50, 'Type': 80, 'Date': 120, 'Status': 100, 'Reviewer Comments': 300}
        for col in columns:
            self.progress_tree.heading(col, text=col)
            self.progress_tree.column(col, width=widths.get(col, 100))

        self.progress_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Submit report form
        form_frame = ttk.LabelFrame(tab, text="Submit New Report", padding=10)
        form_frame.pack(fill=tk.X, padx=10, pady=5)

        # Report type
        type_row = ttk.Frame(form_frame)
        type_row.pack(fill=tk.X, pady=5)
        ttk.Label(type_row, text="Report Type:").pack(side=tk.LEFT, padx=10)
        self.report_type_combo = ttk.Combobox(type_row, width=15, state='readonly',
            values=['interim', 'final'])
        self.report_type_combo.set('interim')
        self.report_type_combo.pack(side=tk.LEFT, padx=10)

        # Content
        content_row = ttk.Frame(form_frame)
        content_row.pack(fill=tk.X, pady=5)
        ttk.Label(content_row, text="Content:").pack(anchor='nw', padx=10)
        self.report_content_text = scrolledtext.ScrolledText(content_row, width=60, height=6)
        self.report_content_text.pack(padx=10, fill=tk.X)

        # Achievements
        ach_row = ttk.Frame(form_frame)
        ach_row.pack(fill=tk.X, pady=5)
        ttk.Label(ach_row, text="Achievements:").pack(anchor='nw', padx=10)
        self.report_achievements_text = scrolledtext.ScrolledText(ach_row, width=60, height=4)
        self.report_achievements_text.pack(padx=10, fill=tk.X)

        # Challenges
        ch_row = ttk.Frame(form_frame)
        ch_row.pack(fill=tk.X, pady=5)
        ttk.Label(ch_row, text="Challenges:").pack(anchor='nw', padx=10)
        self.report_challenges_text = scrolledtext.ScrolledText(ch_row, width=60, height=4)
        self.report_challenges_text.pack(padx=10, fill=tk.X)

        # Submit button
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        ttk.Button(btn_frame, text="Submit Report", command=self._submit_progress_report).pack(padx=10)

    def _load_progress_applications(self):
        """Load active/approved sabbaticals into the progress application selector."""
        self._progress_app_map = {}
        try:
            all_apps = SabbaticalManager.get_user_applications(self._get_user_id())
            active_apps = [a for a in all_apps
                           if a.get('status') in ('approved', 'active')]

            display_values = []
            for app in active_apps:
                display = f"#{app['application_id']} - {app.get('title', 'Untitled')} ({app.get('status', '').title()})"
                self._progress_app_map[display] = app['application_id']
                display_values.append(display)

            self.progress_app_combo['values'] = display_values
            if display_values:
                self.progress_app_combo.set(display_values[0])
        except Exception:
            self.progress_app_combo['values'] = []

    def _get_selected_progress_app_id(self):
        """Get the application ID from the progress application selector."""
        selection = self.progress_app_combo.get()
        return self._progress_app_map.get(selection)

    def _load_progress_reports(self):
        """Load progress reports for selected application."""
        for item in self.progress_tree.get_children():
            self.progress_tree.delete(item)

        app_id = self._get_selected_progress_app_id()
        if not app_id:
            return

        try:
            reports = SabbaticalManager.get_progress_reports(app_id)
            for r in reports:
                self.progress_tree.insert('', tk.END, values=(
                    r.get('report_id'),
                    r.get('report_type', '').title(),
                    r.get('report_date', ''),
                    r.get('status', '').title(),
                    r.get('review_comments', '') or ''
                ))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load progress reports: {e}")

    def _refresh_progress_tab(self):
        """Refresh the progress tab data."""
        self._load_progress_applications()
        self._load_progress_reports()

    def _submit_progress_report(self):
        """Submit a progress report."""
        app_id = self._get_selected_progress_app_id()
        if not app_id:
            messagebox.showinfo("Info", "Please select a sabbatical application")
            return

        content = self.report_content_text.get("1.0", "end-1c").strip()
        if not content:
            messagebox.showerror("Validation Error", "Report content is required.")
            return

        report_type = self.report_type_combo.get()
        achievements = self.report_achievements_text.get("1.0", "end-1c").strip() or None
        challenges = self.report_challenges_text.get("1.0", "end-1c").strip() or None

        try:
            report_id = SabbaticalManager.submit_progress_report(
                application_id=app_id,
                report_type=report_type,
                content=content,
                achievements=achievements,
                challenges=challenges,
            )
            messagebox.showinfo("Success", f"Progress report submitted. Report ID: {report_id}")

            # Clear form
            self.report_content_text.delete("1.0", tk.END)
            self.report_achievements_text.delete("1.0", tk.END)
            self.report_challenges_text.delete("1.0", tk.END)
            self.report_type_combo.set('interim')
            self._load_progress_reports()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ==================== TAB 4: APPROVALS (ADMIN) ====================

    def _create_approvals_tab(self):
        """Create sabbatical approvals tab (admin)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Approvals")

        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Sabbatical Approvals", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh", command=self._load_sabbatical_approvals).pack(side=tk.RIGHT)

        # Pending approvals list
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        columns = ('Approval ID', 'Applicant', 'Title', 'Type', 'Dates', 'Level', 'Status')
        self.sabbatical_approvals_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                                       yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.sabbatical_approvals_tree.yview)

        widths = {'Approval ID': 80, 'Applicant': 120, 'Title': 200, 'Type': 100,
                  'Dates': 180, 'Level': 100, 'Status': 80}
        for col in columns:
            self.sabbatical_approvals_tree.heading(col, text=col)
            self.sabbatical_approvals_tree.column(col, width=widths.get(col, 100))

        self.sabbatical_approvals_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Action buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(btn_frame, text="Approve Selected", command=self._approve_sabbatical).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Reject Selected", command=self._reject_sabbatical).pack(side=tk.LEFT, padx=5)

        self._load_sabbatical_approvals()

    def _load_sabbatical_approvals(self):
        """Load pending sabbatical approvals."""
        for item in self.sabbatical_approvals_tree.get_children():
            self.sabbatical_approvals_tree.delete(item)

        try:
            approvals = SabbaticalManager.get_pending_approvals()

            for a in approvals:
                start = a.get('start_date', '')
                end = a.get('end_date', '')
                dates = f"{start} - {end}" if start and end else start or end or ''
                sab_type = a.get('sabbatical_type', '').replace('_', ' ').title()

                self.sabbatical_approvals_tree.insert('', tk.END, values=(
                    a.get('approval_id'),
                    a.get('user_id', ''),
                    a.get('title', ''),
                    sab_type,
                    dates,
                    a.get('approval_level', '').title(),
                    a.get('status', '').title()
                ))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load approvals: {e}")

    def _approve_sabbatical(self):
        """Approve selected sabbatical application."""
        selection = self.sabbatical_approvals_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select an approval to approve")
            return

        item = self.sabbatical_approvals_tree.item(selection[0])
        approval_id = item['values'][0]

        comments = tk.simpledialog.askstring("Comments", "Enter approval comments (optional):", parent=self.root)

        try:
            SabbaticalManager.approve_application(approval_id, self._get_user_id(), comments or '')
            messagebox.showinfo("Success", "Sabbatical application approved at this level")
            self._load_sabbatical_approvals()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _reject_sabbatical(self):
        """Reject selected sabbatical application."""
        selection = self.sabbatical_approvals_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select an approval to reject")
            return

        item = self.sabbatical_approvals_tree.item(selection[0])
        approval_id = item['values'][0]

        comments = tk.simpledialog.askstring("Reason", "Enter rejection reason:", parent=self.root)
        if not comments:
            messagebox.showerror("Error", "Rejection reason is required")
            return

        try:
            SabbaticalManager.reject_application(approval_id, self._get_user_id(), comments)
            messagebox.showinfo("Success", "Sabbatical application rejected")
            self._load_sabbatical_approvals()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ==================== TAB 5: RETURN PLANNING ====================

    def _create_return_tab(self):
        """Create return planning tab (admin)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Return Planning")

        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Return Planning", style='Header.TLabel').pack(side=tk.LEFT)

        # Application selector
        selector_frame = ttk.LabelFrame(tab, text="Select Sabbatical", padding=10)
        selector_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(selector_frame, text="Application:").pack(side=tk.LEFT, padx=10)
        self.return_app_combo = ttk.Combobox(selector_frame, width=50, state='readonly')
        self.return_app_combo.pack(side=tk.LEFT, padx=10)
        self.return_app_combo.bind('<<ComboboxSelected>>', lambda e: self._load_return_plan())

        self._return_app_map = {}
        self._load_return_applications()

        # Existing plan display
        self.existing_plan_frame = ttk.LabelFrame(tab, text="Current Return Plan", padding=10)
        self.existing_plan_frame.pack(fill=tk.X, padx=10, pady=5)
        self.existing_plan_label = ttk.Label(self.existing_plan_frame, text="No return plan found for this application.")
        self.existing_plan_label.pack(padx=10, pady=5, anchor='w')

        # Return plan form
        form_frame = ttk.LabelFrame(tab, text="Return Plan Details", padding=15)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Return Date
        ttk.Label(form_frame, text="Return Date:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        self.return_date_entry = ttk.Entry(form_frame, width=15)
        self.return_date_entry.grid(row=0, column=1, padx=10, pady=8, sticky='w')

        # Transition Period
        ttk.Label(form_frame, text="Transition Period (weeks):").grid(row=0, column=2, sticky='e', padx=10, pady=8)
        self.transition_spinbox = ttk.Spinbox(form_frame, from_=1, to=26, width=5)
        self.transition_spinbox.set(4)
        self.transition_spinbox.grid(row=0, column=3, padx=10, pady=8, sticky='w')

        # Research Outputs
        ttk.Label(form_frame, text="Research Outputs:").grid(row=1, column=0, sticky='ne', padx=10, pady=8)
        self.research_outputs_text = scrolledtext.ScrolledText(form_frame, width=60, height=5)
        self.research_outputs_text.grid(row=1, column=1, columnspan=3, padx=10, pady=8, sticky='w')

        # Knowledge Sharing Plan
        ttk.Label(form_frame, text="Knowledge Sharing Plan:").grid(row=2, column=0, sticky='ne', padx=10, pady=8)
        self.knowledge_plan_text = scrolledtext.ScrolledText(form_frame, width=60, height=5)
        self.knowledge_plan_text.grid(row=2, column=1, columnspan=3, padx=10, pady=8, sticky='w')

        # Buttons
        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=3, column=0, columnspan=4, pady=15)
        ttk.Button(btn_frame, text="Create/Update Plan",
                   command=self._save_return_plan).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="Complete Return",
                   command=self._complete_return).pack(side=tk.LEFT, padx=10)

    def _load_return_applications(self):
        """Load approved/active sabbaticals into the return application selector."""
        self._return_app_map = {}
        try:
            all_apps = SabbaticalManager.get_user_applications(self._get_user_id())
            # For admin, we show all approved/active applications
            # In a full system you would query all users, but here we follow the pattern
            eligible_apps = [a for a in all_apps
                             if a.get('status') in ('approved', 'active')]

            display_values = []
            for app in eligible_apps:
                display = (f"#{app['application_id']} - {app.get('title', 'Untitled')} "
                           f"({app.get('user_id', '')} - {app.get('status', '').title()})")
                self._return_app_map[display] = app
                display_values.append(display)

            self.return_app_combo['values'] = display_values
            if display_values:
                self.return_app_combo.set(display_values[0])
                self._load_return_plan()
        except Exception:
            self.return_app_combo['values'] = []

    def _get_selected_return_app(self):
        """Get the application dict from the return application selector."""
        selection = self.return_app_combo.get()
        return self._return_app_map.get(selection)

    def _load_return_plan(self):
        """Load existing return plan for selected application."""
        app = self._get_selected_return_app()
        if not app:
            self.existing_plan_label.config(text="No application selected.")
            return

        app_id = app['application_id']

        try:
            plan = SabbaticalManager.get_return_plan(app_id)
            if plan:
                info_parts = [
                    f"Plan ID: {plan.get('plan_id')}",
                    f"Return Date: {plan.get('return_date', 'N/A')}",
                    f"Transition: {plan.get('transition_period_weeks', 'N/A')} weeks",
                    f"Status: {plan.get('status', 'N/A').title()}",
                ]
                self.existing_plan_label.config(text="  |  ".join(info_parts))

                # Pre-fill form with existing data
                self.return_date_entry.delete(0, tk.END)
                if plan.get('return_date'):
                    self.return_date_entry.insert(0, plan['return_date'])

                self.transition_spinbox.delete(0, tk.END)
                self.transition_spinbox.insert(0, str(plan.get('transition_period_weeks', 4)))

                self.research_outputs_text.delete("1.0", tk.END)
                if plan.get('research_outputs'):
                    self.research_outputs_text.insert("1.0", plan['research_outputs'])

                self.knowledge_plan_text.delete("1.0", tk.END)
                if plan.get('knowledge_sharing_plan'):
                    self.knowledge_plan_text.insert("1.0", plan['knowledge_sharing_plan'])

                # Store plan_id for updates
                self._current_plan_id = plan.get('plan_id')
            else:
                self.existing_plan_label.config(text="No return plan found for this application.")
                self._current_plan_id = None
        except Exception as e:
            self.existing_plan_label.config(text=f"Error loading plan: {e}")
            self._current_plan_id = None

    def _save_return_plan(self):
        """Create or update a return plan."""
        app = self._get_selected_return_app()
        if not app:
            messagebox.showinfo("Info", "Please select a sabbatical application")
            return

        try:
            return_date = validate_date_entry(self.return_date_entry, "Return Date")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        try:
            transition_weeks = int(self.transition_spinbox.get())
        except (ValueError, TypeError):
            messagebox.showerror("Validation Error", "Transition period must be a valid number of weeks.")
            return

        research_outputs = self.research_outputs_text.get("1.0", "end-1c").strip() or None
        knowledge_plan = self.knowledge_plan_text.get("1.0", "end-1c").strip() or None

        app_id = app['application_id']

        try:
            existing_plan = SabbaticalManager.get_return_plan(app_id)

            if existing_plan:
                # Update existing plan
                plan_id = existing_plan['plan_id']
                SabbaticalManager.update_return_plan(
                    plan_id,
                    return_date=return_date,
                    transition_period_weeks=transition_weeks,
                    research_outputs=research_outputs,
                    knowledge_sharing_plan=knowledge_plan,
                )
                messagebox.showinfo("Success", f"Return plan updated. Plan ID: {plan_id}")
            else:
                # Create new plan
                plan_id = SabbaticalManager.create_return_plan(
                    application_id=app_id,
                    return_date=return_date,
                    transition_period_weeks=transition_weeks,
                    research_outputs=research_outputs,
                    knowledge_sharing_plan=knowledge_plan,
                )
                messagebox.showinfo("Success", f"Return plan created. Plan ID: {plan_id}")

            self._load_return_plan()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _complete_return(self):
        """Complete the return from sabbatical."""
        app = self._get_selected_return_app()
        if not app:
            messagebox.showinfo("Info", "Please select a sabbatical application")
            return

        if not messagebox.askyesno("Confirm",
                "Are you sure you want to mark this sabbatical return as complete?\n\n"
                "This will update the application status to 'completed' and reset eligibility."):
            return

        try:
            SabbaticalManager.complete_return(app['application_id'], app.get('user_id', self._get_user_id()))
            messagebox.showinfo("Success", "Sabbatical return completed successfully.")
            self._load_return_applications()
            self._load_applications()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ==================== TAB 6: REPORTS (ADMIN) ====================

    def _create_reports_tab(self):
        """Create sabbatical reports tab (admin)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Reports")

        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Sabbatical Reports", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh", command=self._load_sabbatical_stats).pack(side=tk.RIGHT)

        # Statistics
        stats_frame = ttk.LabelFrame(tab, text="Overview", padding=15)
        stats_frame.pack(fill=tk.X, padx=10, pady=10)

        self.sabbatical_stats = {}
        for key, label in [('total', 'Total Applications'), ('active', 'Active Sabbaticals'),
                           ('completed', 'Completed')]:
            frame = ttk.Frame(stats_frame)
            frame.pack(side=tk.LEFT, padx=30, pady=10)
            self.sabbatical_stats[key] = ttk.Label(frame, text="0", font=('Arial', 18, 'bold'))
            self.sabbatical_stats[key].pack()
            ttk.Label(frame, text=label).pack()

        # Eligibility list
        elig_frame = ttk.LabelFrame(tab, text="Staff Eligibility", padding=10)
        elig_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(elig_frame, orient=tk.VERTICAL)
        columns = ('User', 'Years of Service', 'Last Sabbatical', 'Eligible', 'Next Eligible')
        self.elig_tree = ttk.Treeview(elig_frame, columns=columns, show='headings',
                                       yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.elig_tree.yview)

        widths = {'User': 150, 'Years of Service': 120, 'Last Sabbatical': 120,
                  'Eligible': 80, 'Next Eligible': 120}
        for col in columns:
            self.elig_tree.heading(col, text=col)
            self.elig_tree.column(col, width=widths.get(col, 100))

        self.elig_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.elig_tree.tag_configure('eligible', background='#d4edda')
        self.elig_tree.tag_configure('not_eligible', background='#f8d7da')

        self._load_sabbatical_stats()

    def _load_sabbatical_stats(self):
        """Load sabbatical statistics and eligibility data."""
        from education_system.university_system.infrastructure.database.db import get_connection

        try:
            with get_connection() as conn:
                # Total applications
                row = conn.execute(
                    'SELECT COUNT(*) as cnt FROM sabbatical_applications'
                ).fetchone()
                total = row['cnt'] if row else 0
                self.sabbatical_stats['total'].config(text=str(total))

                # Active sabbaticals
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM sabbatical_applications WHERE status = 'active'"
                ).fetchone()
                active = row['cnt'] if row else 0
                self.sabbatical_stats['active'].config(text=str(active))

                # Completed sabbaticals
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM sabbatical_applications WHERE status = 'completed'"
                ).fetchone()
                completed = row['cnt'] if row else 0
                self.sabbatical_stats['completed'].config(text=str(completed))

                # Eligibility list
                for item in self.elig_tree.get_children():
                    self.elig_tree.delete(item)

                elig_rows = conn.execute(
                    'SELECT * FROM sabbatical_eligibility ORDER BY user_id'
                ).fetchall()

                for er in elig_rows:
                    record = dict(er)
                    is_elig = bool(record.get('is_eligible'))
                    tag = 'eligible' if is_elig else 'not_eligible'

                    self.elig_tree.insert('', tk.END, values=(
                        record.get('user_id', ''),
                        f"{record.get('years_of_service', 0):.1f}" if record.get('years_of_service') else 'N/A',
                        record.get('last_sabbatical_end', 'None') or 'None',
                        'Yes' if is_elig else 'No',
                        record.get('next_eligible_date', 'N/A') or 'N/A'
                    ), tags=(tag,))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load sabbatical statistics: {e}")


# Add simpledialog import for the approval dialogs
try:
    from tkinter import simpledialog
    tk.simpledialog = simpledialog
except ImportError:
    pass
