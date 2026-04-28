"""
Student Jobs GUI Interface

Tkinter-based graphical user interface for the Student Job Board system.
Features tabbed interface for job browsing, applications, work hours, and skills.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime, timedelta
from typing import Optional

from education_system.university_system.infrastructure.shared_context import get_auth
from education_system.university_system.modules.domain.career.student_jobs.services.job_service import (
    JobPostingManager,
    JobApplicationManager,
    EmploymentManager,
    WorkHoursManager,
    SkillMatchingManager,
    PerformanceManager,
)


class StudentJobsGUI:
    """Graphical user interface for Student Job Board"""

    def __init__(self, parent=None, auth=None):
        """Initialize the GUI"""
        if parent is None:
            self.root = tk.Tk()
            self.root.title("Student Job Board")
        else:
            self.root = tk.Toplevel(parent)
            self.root.title("Student Job Board")

        self.root.geometry("1400x900")
        self.root.configure(bg='#f0f0f0')

        # Authentication
        self.auth = auth if auth else get_auth()
        self.current_user = None
        if self.auth and self.auth.current_user:
            self.current_user = self.auth.get_current_user()

        # Initialize data storage
        self.jobs_list = []
        self.applications_list = []
        self.employment_list = []
        self.hours_list = []
        self.skills_list = []

        # Create UI
        self.create_menu()
        self.create_main_interface()
        self.create_status_bar()

        # Load initial data
        self.refresh_all_data()

    def run(self):
        """Start the GUI main loop"""
        self.root.mainloop()

    def create_menu(self):
        """Create menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Refresh All", command=self.refresh_all_data)
        file_menu.add_separator()
        file_menu.add_command(label="Close", command=self.root.destroy)

        # Jobs menu
        jobs_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Jobs", menu=jobs_menu)
        jobs_menu.add_command(label="Browse All Jobs", command=lambda: self.notebook.select(0))
        jobs_menu.add_command(label="View My Applications", command=lambda: self.notebook.select(1))
        jobs_menu.add_command(label="My Jobs & Hours", command=lambda: self.notebook.select(2))

        # Skills menu
        skills_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Skills", menu=skills_menu)
        skills_menu.add_command(label="Manage Skills", command=lambda: self.notebook.select(3))
        skills_menu.add_command(label="Find Matching Jobs", command=self.find_matching_jobs)

        # Admin menu (if applicable)
        if self._is_admin_or_staff():
            admin_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label="Administration", menu=admin_menu)
            admin_menu.add_command(label="Post New Job", command=self.show_post_job_dialog)
            admin_menu.add_command(label="Manage Postings", command=lambda: self.notebook.select(4))
            admin_menu.add_command(label="Review Applications", command=self.show_review_applications)
            admin_menu.add_command(label="Approve Hours", command=self.show_approve_hours)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="User Guide", command=self.show_help)
        help_menu.add_command(label="About", command=self.show_about)

    def create_main_interface(self):
        """Create main tabbed interface"""
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Create tabs
        self.create_job_search_tab()
        self.create_applications_tab()
        self.create_my_jobs_tab()
        self.create_skills_tab()

        if self._is_admin_or_staff():
            self.create_admin_tab()

    def create_job_search_tab(self):
        """Create job search and browse tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Browse Jobs")

        # Search and filter frame
        search_frame = ttk.LabelFrame(tab, text="Search & Filter", padding=10)
        search_frame.pack(fill=tk.X, padx=10, pady=5)

        # Search fields
        ttk.Label(search_frame, text="Category:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.search_category = ttk.Entry(search_frame, width=20)
        self.search_category.grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(search_frame, text="Type:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=2)
        self.search_type = ttk.Combobox(search_frame, width=18, state='readonly')
        self.search_type['values'] = ('All', 'work-study', 'part-time', 'internship', 'temp')
        self.search_type.current(0)
        self.search_type.grid(row=0, column=3, padx=5, pady=2)

        ttk.Label(search_frame, text="Location:").grid(row=0, column=4, sticky=tk.W, padx=5, pady=2)
        self.search_location = ttk.Entry(search_frame, width=20)
        self.search_location.grid(row=0, column=5, padx=5, pady=2)

        ttk.Button(search_frame, text="Search", command=self.search_jobs).grid(row=0, column=6, padx=10, pady=2)
        ttk.Button(search_frame, text="Clear", command=self.clear_job_search).grid(row=0, column=7, padx=5, pady=2)

        # Work-study only checkbox
        self.work_study_only = tk.BooleanVar()
        ttk.Checkbutton(search_frame, text="Work-Study Only", variable=self.work_study_only,
                       command=self.search_jobs).grid(row=1, column=0, columnspan=2, sticky=tk.W, padx=5, pady=2)

        # Job listings frame
        listings_frame = ttk.LabelFrame(tab, text="Available Jobs", padding=10)
        listings_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Create treeview for job listings
        columns = ('ID', 'Title', 'Employer', 'Category', 'Type', 'Rate', 'Location', 'Positions', 'Deadline')
        self.jobs_tree = ttk.Treeview(listings_frame, columns=columns, show='headings', height=15)

        # Configure columns
        self.jobs_tree.heading('ID', text='Job ID')
        self.jobs_tree.heading('Title', text='Job Title')
        self.jobs_tree.heading('Employer', text='Employer')
        self.jobs_tree.heading('Category', text='Category')
        self.jobs_tree.heading('Type', text='Type')
        self.jobs_tree.heading('Rate', text='Rate/Hr')
        self.jobs_tree.heading('Location', text='Location')
        self.jobs_tree.heading('Positions', text='Positions')
        self.jobs_tree.heading('Deadline', text='Deadline')

        self.jobs_tree.column('ID', width=60)
        self.jobs_tree.column('Title', width=200)
        self.jobs_tree.column('Employer', width=150)
        self.jobs_tree.column('Category', width=100)
        self.jobs_tree.column('Type', width=100)
        self.jobs_tree.column('Rate', width=80)
        self.jobs_tree.column('Location', width=120)
        self.jobs_tree.column('Positions', width=80)
        self.jobs_tree.column('Deadline', width=100)

        # Scrollbars
        vsb = ttk.Scrollbar(listings_frame, orient="vertical", command=self.jobs_tree.yview)
        hsb = ttk.Scrollbar(listings_frame, orient="horizontal", command=self.jobs_tree.xview)
        self.jobs_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.jobs_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        listings_frame.grid_rowconfigure(0, weight=1)
        listings_frame.grid_columnconfigure(0, weight=1)

        # Buttons frame
        buttons_frame = ttk.Frame(tab)
        buttons_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(buttons_frame, text="View Details", command=self.view_job_details).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Apply for Job", command=self.apply_for_job_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Refresh", command=self.refresh_jobs).pack(side=tk.LEFT, padx=5)

    def create_applications_tab(self):
        """Create my applications tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="My Applications")

        # Filter frame
        filter_frame = ttk.LabelFrame(tab, text="Filter", padding=10)
        filter_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(filter_frame, text="Status:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.app_status_filter = ttk.Combobox(filter_frame, width=20, state='readonly')
        self.app_status_filter['values'] = ('All', 'pending', 'reviewed', 'interview', 'offered', 'accepted', 'rejected')
        self.app_status_filter.current(0)
        self.app_status_filter.grid(row=0, column=1, padx=5)
        self.app_status_filter.bind('<<ComboboxSelected>>', lambda e: self.refresh_applications())

        # Applications list
        list_frame = ttk.LabelFrame(tab, text="My Applications", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ('App ID', 'Job Title', 'Employer', 'Rate', 'Applied Date', 'Status')
        self.apps_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

        self.apps_tree.heading('App ID', text='Application ID')
        self.apps_tree.heading('Job Title', text='Job Title')
        self.apps_tree.heading('Employer', text='Employer')
        self.apps_tree.heading('Rate', text='Rate/Hr')
        self.apps_tree.heading('Applied Date', text='Applied Date')
        self.apps_tree.heading('Status', text='Status')

        self.apps_tree.column('App ID', width=100)
        self.apps_tree.column('Job Title', width=250)
        self.apps_tree.column('Employer', width=200)
        self.apps_tree.column('Rate', width=100)
        self.apps_tree.column('Applied Date', width=120)
        self.apps_tree.column('Status', width=120)

        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.apps_tree.yview)
        hsb = ttk.Scrollbar(list_frame, orient="horizontal", command=self.apps_tree.xview)
        self.apps_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.apps_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        # Buttons
        buttons_frame = ttk.Frame(tab)
        buttons_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(buttons_frame, text="View Details", command=self.view_application_details).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Withdraw", command=self.withdraw_application).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Refresh", command=self.refresh_applications).pack(side=tk.LEFT, padx=5)

    def create_my_jobs_tab(self):
        """Create my jobs and work hours tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="My Jobs & Hours")

        # Create sub-notebook
        sub_notebook = ttk.Notebook(tab)
        sub_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Current jobs sub-tab
        jobs_tab = ttk.Frame(sub_notebook)
        sub_notebook.add(jobs_tab, text="Current Jobs")

        jobs_frame = ttk.LabelFrame(jobs_tab, text="My Current Jobs", padding=10)
        jobs_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ('Emp ID', 'Position', 'Employer', 'Rate', 'Max Hours', 'Start Date', 'Status')
        self.employment_tree = ttk.Treeview(jobs_frame, columns=columns, show='headings', height=10)

        for col in columns:
            self.employment_tree.heading(col, text=col)
            self.employment_tree.column(col, width=120)

        vsb = ttk.Scrollbar(jobs_frame, orient="vertical", command=self.employment_tree.yview)
        self.employment_tree.configure(yscrollcommand=vsb.set)

        self.employment_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # Work hours sub-tab
        hours_tab = ttk.Frame(sub_notebook)
        sub_notebook.add(hours_tab, text="Work Hours")

        # Date range filter
        filter_frame = ttk.Frame(hours_tab)
        filter_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(filter_frame, text="From:").pack(side=tk.LEFT, padx=5)
        self.hours_start_date = ttk.Entry(filter_frame, width=12)
        self.hours_start_date.pack(side=tk.LEFT, padx=5)

        ttk.Label(filter_frame, text="To:").pack(side=tk.LEFT, padx=5)
        self.hours_end_date = ttk.Entry(filter_frame, width=12)
        self.hours_end_date.pack(side=tk.LEFT, padx=5)

        ttk.Button(filter_frame, text="Filter", command=self.refresh_hours).pack(side=tk.LEFT, padx=5)
        ttk.Button(filter_frame, text="This Week", command=self.filter_hours_this_week).pack(side=tk.LEFT, padx=5)

        # Hours list
        hours_frame = ttk.LabelFrame(hours_tab, text="Work Hours Log", padding=10)
        hours_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ('Log ID', 'Date', 'Position', 'Clock In', 'Clock Out', 'Hours', 'Earnings', 'Status')
        self.hours_tree = ttk.Treeview(hours_frame, columns=columns, show='headings', height=12)

        for col in columns:
            self.hours_tree.heading(col, text=col)
            self.hours_tree.column(col, width=100)

        vsb = ttk.Scrollbar(hours_frame, orient="vertical", command=self.hours_tree.yview)
        self.hours_tree.configure(yscrollcommand=vsb.set)

        self.hours_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # Summary frame
        summary_frame = ttk.LabelFrame(hours_tab, text="Summary", padding=10)
        summary_frame.pack(fill=tk.X, padx=10, pady=5)

        self.hours_summary_label = ttk.Label(summary_frame, text="Total Hours: 0.00 | Total Earnings: £0.00")
        self.hours_summary_label.pack()

        # Buttons
        buttons_frame = ttk.Frame(hours_tab)
        buttons_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(buttons_frame, text="Clock In", command=self.clock_in_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Clock Out", command=self.clock_out_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Weekly Summary", command=self.show_weekly_summary).pack(side=tk.LEFT, padx=5)

        # Work-Study sub-tab
        ws_tab = ttk.Frame(sub_notebook)
        sub_notebook.add(ws_tab, text="Work-Study")

        ws_info_frame = ttk.LabelFrame(ws_tab, text="Work-Study Information", padding=10)
        ws_info_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.ws_info_text = scrolledtext.ScrolledText(ws_info_frame, height=20, wrap=tk.WORD)
        self.ws_info_text.pack(fill=tk.BOTH, expand=True)

        ttk.Button(ws_tab, text="Refresh", command=self.refresh_work_study_info).pack(pady=5)

    def create_skills_tab(self):
        """Create skills management tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Skills & Matching")

        # My skills section
        skills_frame = ttk.LabelFrame(tab, text="My Skills", padding=10)
        skills_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ('Skill ID', 'Skill Name', 'Category', 'Proficiency', 'Experience', 'Verified')
        self.skills_tree = ttk.Treeview(skills_frame, columns=columns, show='headings', height=10)

        self.skills_tree.heading('Skill ID', text='ID')
        self.skills_tree.heading('Skill Name', text='Skill Name')
        self.skills_tree.heading('Category', text='Category')
        self.skills_tree.heading('Proficiency', text='Proficiency')
        self.skills_tree.heading('Experience', text='Experience (yrs)')
        self.skills_tree.heading('Verified', text='Verified')

        self.skills_tree.column('Skill ID', width=60)
        self.skills_tree.column('Skill Name', width=200)
        self.skills_tree.column('Category', width=120)
        self.skills_tree.column('Proficiency', width=120)
        self.skills_tree.column('Experience', width=120)
        self.skills_tree.column('Verified', width=100)

        vsb = ttk.Scrollbar(skills_frame, orient="vertical", command=self.skills_tree.yview)
        self.skills_tree.configure(yscrollcommand=vsb.set)

        self.skills_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # Buttons
        buttons_frame = ttk.Frame(tab)
        buttons_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(buttons_frame, text="Add Skill", command=self.add_skill_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Find Matching Jobs", command=self.find_matching_jobs).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Refresh", command=self.refresh_skills).pack(side=tk.LEFT, padx=5)

    def create_admin_tab(self):
        """Create admin management tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Administration")

        # Admin functions frame
        functions_frame = ttk.LabelFrame(tab, text="Administrative Functions", padding=20)
        functions_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create buttons in a grid
        ttk.Button(functions_frame, text="Post New Job", command=self.show_post_job_dialog,
                  width=25).grid(row=0, column=0, padx=10, pady=10)
        ttk.Button(functions_frame, text="Manage Job Postings", command=self.show_manage_postings,
                  width=25).grid(row=0, column=1, padx=10, pady=10)

        ttk.Button(functions_frame, text="Review Applications", command=self.show_review_applications,
                  width=25).grid(row=1, column=0, padx=10, pady=10)
        ttk.Button(functions_frame, text="Hire Student", command=self.show_hire_student_dialog,
                  width=25).grid(row=1, column=1, padx=10, pady=10)

        ttk.Button(functions_frame, text="Approve Work Hours", command=self.show_approve_hours,
                  width=25).grid(row=2, column=0, padx=10, pady=10)
        ttk.Button(functions_frame, text="Create Performance Review", command=self.show_performance_review_dialog,
                  width=25).grid(row=2, column=1, padx=10, pady=10)

        ttk.Button(functions_frame, text="Manage Employment Records", command=self.show_manage_employment,
                  width=25).grid(row=3, column=0, padx=10, pady=10)
        ttk.Button(functions_frame, text="View Reports", command=self.show_reports,
                  width=25).grid(row=3, column=1, padx=10, pady=10)

    def create_status_bar(self):
        """Create status bar"""
        self.status_bar = ttk.Label(self.root, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    # ======================== DATA LOADING METHODS ========================

    def refresh_all_data(self):
        """Refresh all data"""
        self.update_status("Refreshing all data...")
        self.refresh_jobs()
        self.refresh_applications()
        self.refresh_employment()
        self.refresh_hours()
        self.refresh_skills()
        self.refresh_work_study_info()
        self.update_status("All data refreshed")

    def refresh_jobs(self):
        """Refresh job listings"""
        try:
            self.jobs_list = JobPostingManager.get_active_jobs()
            self.update_jobs_tree()
            self.update_status(f"Loaded {len(self.jobs_list)} active jobs")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load jobs: {e}")

    def refresh_applications(self):
        """Refresh applications"""
        if not self.current_user or self.current_user.get('role') != 'student':
            return

        try:
            student_id = self.current_user.get('username', '')
            status = self.app_status_filter.get() if hasattr(self, 'app_status_filter') else 'All'

            if status == 'All':
                self.applications_list = JobApplicationManager.get_student_applications(student_id)
            else:
                self.applications_list = JobApplicationManager.get_student_applications(student_id, status)

            self.update_applications_tree()
            self.update_status(f"Loaded {len(self.applications_list)} applications")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load applications: {e}")

    def refresh_employment(self):
        """Refresh employment records"""
        if not self.current_user or self.current_user.get('role') != 'student':
            return

        try:
            student_id = self.current_user.get('username', '')
            self.employment_list = EmploymentManager.get_student_employment(student_id, active_only=True)
            self.update_employment_tree()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load employment: {e}")

    def refresh_hours(self):
        """Refresh work hours"""
        if not self.current_user or self.current_user.get('role') != 'student':
            return

        try:
            student_id = self.current_user.get('username', '')
            start_date = self.hours_start_date.get() if hasattr(self, 'hours_start_date') and self.hours_start_date.get() else None
            end_date = self.hours_end_date.get() if hasattr(self, 'hours_end_date') and self.hours_end_date.get() else None

            self.hours_list = WorkHoursManager.get_student_hours(student_id, start_date, end_date)
            self.update_hours_tree()
            self.update_hours_summary()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load hours: {e}")

    def refresh_skills(self):
        """Refresh skills"""
        if not self.current_user or self.current_user.get('role') != 'student':
            return

        try:
            student_id = self.current_user.get('username', '')
            self.skills_list = SkillMatchingManager.get_student_skills(student_id)
            self.update_skills_tree()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load skills: {e}")

    def refresh_work_study_info(self):
        """Refresh work-study information"""
        if not hasattr(self, 'ws_info_text'):
            return

        if not self.current_user or self.current_user.get('role') != 'student':
            return

        try:
            student_id = self.current_user.get('username', '')
            jobs = EmploymentManager.get_student_employment(student_id, active_only=True)
            ws_jobs = [j for j in jobs if j.get('is_work_study')]

            self.ws_info_text.delete(1.0, tk.END)

            if not ws_jobs:
                self.ws_info_text.insert(tk.END, "You don't have any work-study positions.\n")
                return

            for job in ws_jobs:
                self.ws_info_text.insert(tk.END, f"\n{'=' * 60}\n")
                self.ws_info_text.insert(tk.END, f"Position: {job['position_title']}\n")
                self.ws_info_text.insert(tk.END, f"Employer: {job['employer_name']}\n")
                self.ws_info_text.insert(tk.END, f"Location: {job['location']}\n")
                self.ws_info_text.insert(tk.END, f"\nWork-Study Allocation: £{job['work_study_allocation']:.2f}\n")
                self.ws_info_text.insert(tk.END, f"Amount Used: £{job['work_study_used']:.2f}\n")
                remaining = job['work_study_allocation'] - job['work_study_used']
                self.ws_info_text.insert(tk.END, f"Remaining: £{remaining:.2f}\n")

                if job['hourly_rate']:
                    remaining_hours = remaining / job['hourly_rate']
                    self.ws_info_text.insert(tk.END, f"Remaining Hours (approx): {remaining_hours:.1f} hours\n")

        except Exception as e:
            self.ws_info_text.delete(1.0, tk.END)
            self.ws_info_text.insert(tk.END, f"Error loading work-study info: {e}")

    # ======================== TREE UPDATE METHODS ========================

    def update_jobs_tree(self):
        """Update jobs tree view"""
        # Clear existing items
        for item in self.jobs_tree.get_children():
            self.jobs_tree.delete(item)

        # Add jobs
        for job in self.jobs_list:
            available = job['total_positions'] - job['filled_positions']
            values = (
                job['job_id'],
                job['job_title'][:30],
                job['employer_name'][:20],
                job['job_category'][:15],
                job['employment_type'],
                f"£{job['hourly_rate']:.2f}",
                job['location'][:20],
                f"{available}/{job['total_positions']}",
                job.get('application_deadline', 'N/A')
            )
            self.jobs_tree.insert('', tk.END, values=values)

    def update_applications_tree(self):
        """Update applications tree view"""
        for item in self.apps_tree.get_children():
            self.apps_tree.delete(item)

        for app in self.applications_list:
            values = (
                app['application_id'],
                app['job_title'][:35],
                app['employer_name'][:25],
                f"£{app['hourly_rate']:.2f}",
                app['application_date'],
                app['status'].upper()
            )
            self.apps_tree.insert('', tk.END, values=values)

    def update_employment_tree(self):
        """Update employment tree view"""
        if not hasattr(self, 'employment_tree'):
            return

        for item in self.employment_tree.get_children():
            self.employment_tree.delete(item)

        for job in self.employment_list:
            values = (
                job['employment_id'],
                job['position_title'][:25],
                job['employer_name'][:20],
                f"£{job['hourly_rate']:.2f}",
                job['max_hours_per_week'],
                job['start_date'],
                job['employment_status'].upper()
            )
            self.employment_tree.insert('', tk.END, values=values)

    def update_hours_tree(self):
        """Update hours tree view"""
        if not hasattr(self, 'hours_tree'):
            return

        for item in self.hours_tree.get_children():
            self.hours_tree.delete(item)

        for record in self.hours_list:
            values = (
                record['log_id'],
                record['work_date'],
                record['position_title'][:20],
                record['clock_in_time'],
                record['clock_out_time'] or 'Active',
                f"{record['total_hours'] or 0:.2f}",
                f"£{record['earnings'] or 0:.2f}",
                record['status'].upper()
            )
            self.hours_tree.insert('', tk.END, values=values)

    def update_hours_summary(self):
        """Update hours summary label"""
        if not hasattr(self, 'hours_summary_label'):
            return

        total_hours = sum(h['total_hours'] or 0 for h in self.hours_list)
        total_earnings = sum(h['earnings'] or 0 for h in self.hours_list)

        self.hours_summary_label.config(
            text=f"Total Hours: {total_hours:.2f} | Total Earnings: £{total_earnings:.2f}"
        )

    def update_skills_tree(self):
        """Update skills tree view"""
        for item in self.skills_tree.get_children():
            self.skills_tree.delete(item)

        for skill in self.skills_list:
            verified = "✓ Yes" if skill['verified'] else "No"
            values = (
                skill['skill_id'],
                skill['skill_name'],
                skill['skill_category'],
                skill['proficiency_level'],
                f"{skill['years_experience'] or 0:.1f}",
                verified
            )
            self.skills_tree.insert('', tk.END, values=values)

    # ======================== SEARCH AND FILTER METHODS ========================

    def search_jobs(self):
        """Search jobs with filters"""
        try:
            filters = {}

            category = self.search_category.get().strip()
            if category:
                filters['job_category'] = category

            job_type = self.search_type.get()
            if job_type != 'All':
                filters['employment_type'] = job_type

            location = self.search_location.get().strip()
            if location:
                filters['location'] = location

            if self.work_study_only.get():
                filters['is_work_study'] = 1

            self.jobs_list = JobPostingManager.get_active_jobs(filters if filters else None)
            self.update_jobs_tree()
            self.update_status(f"Found {len(self.jobs_list)} matching jobs")
        except Exception as e:
            messagebox.showerror("Error", f"Search failed: {e}")

    def clear_job_search(self):
        """Clear job search filters"""
        self.search_category.delete(0, tk.END)
        self.search_type.current(0)
        self.search_location.delete(0, tk.END)
        self.work_study_only.set(False)
        self.refresh_jobs()

    def filter_hours_this_week(self):
        """Filter hours for current week"""
        today = datetime.now()
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)

        self.hours_start_date.delete(0, tk.END)
        self.hours_start_date.insert(0, monday.strftime('%Y-%m-%d'))

        self.hours_end_date.delete(0, tk.END)
        self.hours_end_date.insert(0, sunday.strftime('%Y-%m-%d'))

        self.refresh_hours()

    # ======================== DIALOG METHODS ========================

    def view_job_details(self):
        """View detailed job information"""
        selected = self.jobs_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a job to view.")
            return

        values = self.jobs_tree.item(selected[0])['values']
        job_id = values[0]

        try:
            job = JobPostingManager.get_job_details(job_id)
            if not job:
                messagebox.showerror("Error", "Job not found.")
                return

            # Create details window
            details_window = tk.Toplevel(self.root)
            details_window.title(f"Job Details - {job['job_title']}")
            details_window.geometry("700x800")

            # Create scrolled text widget
            text = scrolledtext.ScrolledText(details_window, wrap=tk.WORD, padx=10, pady=10)
            text.pack(fill=tk.BOTH, expand=True)

            # Add job details
            text.insert(tk.END, f"{'=' * 60}\n")
            text.insert(tk.END, f"{job['job_title']}\n")
            text.insert(tk.END, f"{'=' * 60}\n\n")

            text.insert(tk.END, f"Job ID: {job['job_id']}\n")
            text.insert(tk.END, f"Employer: {job['employer_name']}\n")
            text.insert(tk.END, f"Category: {job['job_category']}\n")
            text.insert(tk.END, f"Type: {job['employment_type']}\n")
            text.insert(tk.END, f"Hourly Rate: £{job['hourly_rate']:.2f}\n")

            if job.get('hours_per_week'):
                text.insert(tk.END, f"Hours per Week: {job['hours_per_week']}\n")

            text.insert(tk.END, f"Location: {job['location']}\n")

            available = job['total_positions'] - job['filled_positions']
            text.insert(tk.END, f"Positions Available: {available}/{job['total_positions']}\n")

            if job.get('minimum_gpa'):
                text.insert(tk.END, f"Minimum GPA: {job['minimum_gpa']}\n")

            text.insert(tk.END, f"\nDescription:\n{job['job_description']}\n")

            if job.get('required_skills'):
                text.insert(tk.END, f"\nRequired Skills:\n{job['required_skills']}\n")

            if job.get('preferred_skills'):
                text.insert(tk.END, f"\nPreferred Skills:\n{job['preferred_skills']}\n")

            if job.get('start_date'):
                text.insert(tk.END, f"\nStart Date: {job['start_date']}\n")

            if job.get('end_date'):
                text.insert(tk.END, f"End Date: {job['end_date']}\n")

            if job.get('application_deadline'):
                text.insert(tk.END, f"Application Deadline: {job['application_deadline']}\n")

            if job.get('contact_email'):
                text.insert(tk.END, f"\nContact Email: {job['contact_email']}\n")

            if job.get('contact_phone'):
                text.insert(tk.END, f"Contact Phone: {job['contact_phone']}\n")

            text.insert(tk.END, f"\nPosted: {job['posted_date']}\n")
            text.insert(tk.END, f"Total Applications: {job.get('total_applications', 0)}\n")

            text.config(state=tk.DISABLED)

            # Apply button
            if self.current_user and self.current_user.get('role') == 'student':
                ttk.Button(details_window, text="Apply for this Job",
                          command=lambda: self.apply_for_specific_job(job_id, details_window)).pack(pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load job details: {e}")

    def apply_for_job_dialog(self):
        """Show apply for job dialog"""
        selected = self.jobs_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a job to apply for.")
            return

        values = self.jobs_tree.item(selected[0])['values']
        job_id = values[0]

        self.apply_for_specific_job(job_id)

    def apply_for_specific_job(self, job_id, parent_window=None):
        """Apply for a specific job"""
        if not self.current_user or self.current_user.get('role') != 'student':
            messagebox.showerror("Error", "Only students can apply for jobs.")
            return

        # Create application dialog
        dialog = tk.Toplevel(parent_window if parent_window else self.root)
        dialog.title("Apply for Job")
        dialog.geometry("600x500")

        # Form fields
        ttk.Label(dialog, text="Cover Letter (optional):").pack(padx=10, pady=(10, 0), anchor=tk.W)
        cover_letter_text = scrolledtext.ScrolledText(dialog, height=8, wrap=tk.WORD)
        cover_letter_text.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

        ttk.Label(dialog, text="Resume URL (optional):").pack(padx=10, pady=(5, 0), anchor=tk.W)
        resume_entry = ttk.Entry(dialog, width=60)
        resume_entry.pack(padx=10, pady=5)

        ttk.Label(dialog, text="Availability:").pack(padx=10, pady=(5, 0), anchor=tk.W)
        availability_entry = ttk.Entry(dialog, width=60)
        availability_entry.pack(padx=10, pady=5)

        ttk.Label(dialog, text="Expected Hours per Week:").pack(padx=10, pady=(5, 0), anchor=tk.W)
        hours_entry = ttk.Entry(dialog, width=20)
        hours_entry.pack(padx=10, pady=5)

        ttk.Label(dialog, text="References (optional):").pack(padx=10, pady=(5, 0), anchor=tk.W)
        references_entry = ttk.Entry(dialog, width=60)
        references_entry.pack(padx=10, pady=5)

        def submit_application():
            try:
                student_id = self.current_user.get('username', '')
                cover_letter = cover_letter_text.get(1.0, tk.END).strip()
                resume_url = resume_entry.get().strip()
                availability = availability_entry.get().strip()
                expected_hours = hours_entry.get().strip()
                references = references_entry.get().strip()

                if not expected_hours.isdigit():
                    expected_hours = "0"

                application_id = JobApplicationManager.apply_for_job(
                    student_id=student_id,
                    job_id=job_id,
                    cover_letter=cover_letter,
                    resume_url=resume_url,
                    availability=availability,
                    expected_hours=int(expected_hours),
                    references=references
                )

                messagebox.showinfo("Success", f"Application submitted successfully!\nApplication ID: {application_id}")
                dialog.destroy()
                if parent_window:
                    parent_window.destroy()
                self.refresh_applications()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to submit application: {e}")

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Submit Application", command=submit_application).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def view_application_details(self):
        """View application details"""
        selected = self.apps_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select an application to view.")
            return

        values = self.apps_tree.item(selected[0])['values']
        app_id = values[0]

        app = next((a for a in self.applications_list if a['application_id'] == app_id), None)

        if not app:
            messagebox.showerror("Error", "Application not found.")
            return

        # Create details window
        details_window = tk.Toplevel(self.root)
        details_window.title(f"Application Details - {app['job_title']}")
        details_window.geometry("600x600")

        text = scrolledtext.ScrolledText(details_window, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True)

        text.insert(tk.END, f"{'=' * 60}\n")
        text.insert(tk.END, f"APPLICATION DETAILS\n")
        text.insert(tk.END, f"{'=' * 60}\n\n")

        text.insert(tk.END, f"Application ID: {app['application_id']}\n")
        text.insert(tk.END, f"Job: {app['job_title']}\n")
        text.insert(tk.END, f"Employer: {app['employer_name']}\n")
        text.insert(tk.END, f"Rate: £{app['hourly_rate']:.2f}/hour\n")
        text.insert(tk.END, f"Location: {app['location']}\n")
        text.insert(tk.END, f"Applied: {app['application_date']}\n")
        text.insert(tk.END, f"Status: {app['status'].upper()}\n")

        if app.get('expected_hours_per_week'):
            text.insert(tk.END, f"Expected Hours/Week: {app['expected_hours_per_week']}\n")

        if app.get('availability'):
            text.insert(tk.END, f"\nAvailability:\n{app['availability']}\n")

        if app.get('cover_letter'):
            text.insert(tk.END, f"\nCover Letter:\n{app['cover_letter']}\n")

        if app.get('resume_url'):
            text.insert(tk.END, f"\nResume: {app['resume_url']}\n")

        if app.get('references'):
            text.insert(tk.END, f"\nReferences:\n{app['references']}\n")

        if app.get('notes'):
            text.insert(tk.END, f"\nNotes:\n{app['notes']}\n")

        if app.get('interview_date'):
            text.insert(tk.END, f"\nInterview Scheduled: {app['interview_date']}\n")

        text.config(state=tk.DISABLED)

    def withdraw_application(self):
        """Withdraw an application"""
        selected = self.apps_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select an application to withdraw.")
            return

        values = self.apps_tree.item(selected[0])['values']
        app_id = values[0]

        if not messagebox.askyesno("Confirm", f"Are you sure you want to withdraw application {app_id}?"):
            return

        try:
            JobApplicationManager.update_application_status(app_id, 'withdrawn', 'Withdrawn by student')
            messagebox.showinfo("Success", "Application withdrawn successfully.")
            self.refresh_applications()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to withdraw application: {e}")

    def clock_in_dialog(self):
        """Clock in dialog"""
        if not self.current_user or self.current_user.get('role') != 'student':
            messagebox.showerror("Error", "Only students can clock in.")
            return

        if not self.employment_list:
            messagebox.showwarning("Warning", "You don't have any active jobs.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Clock In")
        dialog.geometry("400x300")

        ttk.Label(dialog, text="Select Job:").pack(padx=10, pady=(10, 0))

        job_var = tk.StringVar()
        job_combo = ttk.Combobox(dialog, textvariable=job_var, state='readonly', width=50)
        job_combo['values'] = [f"{j['employment_id']} - {j['position_title']} at {j['employer_name']}"
                                for j in self.employment_list]
        job_combo.pack(padx=10, pady=5)

        if job_combo['values']:
            job_combo.current(0)

        ttk.Label(dialog, text="Work Date (YYYY-MM-DD):").pack(padx=10, pady=(10, 0))
        date_entry = ttk.Entry(dialog, width=20)
        date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        date_entry.pack(padx=10, pady=5)

        ttk.Label(dialog, text="Clock In Time (HH:MM):").pack(padx=10, pady=(10, 0))
        time_entry = ttk.Entry(dialog, width=20)
        time_entry.insert(0, datetime.now().strftime('%H:%M'))
        time_entry.pack(padx=10, pady=5)

        ttk.Label(dialog, text="Task Description (optional):").pack(padx=10, pady=(10, 0))
        task_entry = ttk.Entry(dialog, width=50)
        task_entry.pack(padx=10, pady=5)

        def submit():
            try:
                employment_id = int(job_var.get().split(' - ')[0])
                student_id = self.current_user.get('username', '')
                work_date = date_entry.get()
                clock_in_time = time_entry.get()
                task_description = task_entry.get()

                log_id = WorkHoursManager.clock_in(
                    employment_id=employment_id,
                    student_id=student_id,
                    work_date=work_date,
                    clock_in_time=clock_in_time,
                    task_description=task_description
                )

                messagebox.showinfo("Success", f"Clocked in successfully!\nLog ID: {log_id}")
                dialog.destroy()
                self.refresh_hours()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to clock in: {e}")

        ttk.Button(dialog, text="Clock In", command=submit).pack(pady=20)

    def clock_out_dialog(self):
        """Clock out dialog"""
        if not self.current_user or self.current_user.get('role') != 'student':
            messagebox.showerror("Error", "Only students can clock out.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Clock Out")
        dialog.geometry("400x250")

        ttk.Label(dialog, text="Log ID (from when you clocked in):").pack(padx=10, pady=(10, 0))
        log_id_entry = ttk.Entry(dialog, width=20)
        log_id_entry.pack(padx=10, pady=5)

        ttk.Label(dialog, text="Clock Out Time (HH:MM):").pack(padx=10, pady=(10, 0))
        time_entry = ttk.Entry(dialog, width=20)
        time_entry.insert(0, datetime.now().strftime('%H:%M'))
        time_entry.pack(padx=10, pady=5)

        ttk.Label(dialog, text="Break Duration (minutes):").pack(padx=10, pady=(10, 0))
        break_entry = ttk.Entry(dialog, width=20)
        break_entry.insert(0, "0")
        break_entry.pack(padx=10, pady=5)

        def submit():
            try:
                log_id = int(log_id_entry.get())
                clock_out_time = time_entry.get()
                break_duration = int(break_entry.get())

                WorkHoursManager.clock_out(
                    log_id=log_id,
                    clock_out_time=clock_out_time,
                    break_duration_minutes=break_duration
                )

                messagebox.showinfo("Success", "Clocked out successfully!")
                dialog.destroy()
                self.refresh_hours()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to clock out: {e}")

        ttk.Button(dialog, text="Clock Out", command=submit).pack(pady=20)

    def show_weekly_summary(self):
        """Show weekly hours summary"""
        if not self.current_user or self.current_user.get('role') != 'student':
            messagebox.showerror("Error", "Only students can view weekly summary.")
            return

        # Get Monday of current week
        today = datetime.now()
        monday = today - timedelta(days=today.weekday())
        week_start = monday.strftime('%Y-%m-%d')

        try:
            student_id = self.current_user.get('username', '')
            summary = WorkHoursManager.get_weekly_summary(student_id, week_start)

            dialog = tk.Toplevel(self.root)
            dialog.title("Weekly Hours Summary")
            dialog.geometry("500x400")

            text = scrolledtext.ScrolledText(dialog, wrap=tk.WORD, padx=10, pady=10)
            text.pack(fill=tk.BOTH, expand=True)

            text.insert(tk.END, "=" * 60 + "\n")
            text.insert(tk.END, "WEEKLY HOURS SUMMARY\n")
            text.insert(tk.END, "=" * 60 + "\n\n")

            text.insert(tk.END, f"Week: {summary['week_start']} to {summary['week_end']}\n\n")
            text.insert(tk.END, f"Total Shifts: {summary['total_shifts'] or 0}\n")
            text.insert(tk.END, f"Total Hours: {summary['total_hours'] or 0:.2f}\n")
            text.insert(tk.END, f"Approved Hours: {summary['approved_hours'] or 0:.2f}\n")
            text.insert(tk.END, f"Pending Hours: {summary['pending_hours'] or 0:.2f}\n")
            text.insert(tk.END, f"Total Earnings: £{summary['total_earnings'] or 0:.2f}\n")

            if summary.get('total_work_study'):
                text.insert(tk.END, f"Work-Study Deduction: £{summary['total_work_study']:.2f}\n")

            text.config(state=tk.DISABLED)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load weekly summary: {e}")

    def add_skill_dialog(self):
        """Add skill dialog"""
        if not self.current_user or self.current_user.get('role') != 'student':
            messagebox.showerror("Error", "Only students can add skills.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Add Skill")
        dialog.geometry("400x400")

        ttk.Label(dialog, text="Skill Name:").pack(padx=10, pady=(10, 0))
        skill_entry = ttk.Entry(dialog, width=40)
        skill_entry.pack(padx=10, pady=5)

        ttk.Label(dialog, text="Category:").pack(padx=10, pady=(10, 0))
        category_combo = ttk.Combobox(dialog, width=38, state='readonly')
        category_combo['values'] = ('technical', 'language', 'software', 'certification', 'soft-skill', 'other')
        category_combo.current(0)
        category_combo.pack(padx=10, pady=5)

        ttk.Label(dialog, text="Proficiency Level:").pack(padx=10, pady=(10, 0))
        proficiency_combo = ttk.Combobox(dialog, width=38, state='readonly')
        proficiency_combo['values'] = ('beginner', 'intermediate', 'advanced', 'expert')
        proficiency_combo.current(0)
        proficiency_combo.pack(padx=10, pady=5)

        ttk.Label(dialog, text="Years of Experience:").pack(padx=10, pady=(10, 0))
        years_entry = ttk.Entry(dialog, width=20)
        years_entry.insert(0, "0")
        years_entry.pack(padx=10, pady=5)

        def submit():
            try:
                student_id = self.current_user.get('username', '')
                skill_name = skill_entry.get().strip()
                skill_category = category_combo.get()
                proficiency_level = proficiency_combo.get()
                years_experience = float(years_entry.get())

                if not skill_name:
                    messagebox.showwarning("Warning", "Skill name is required.")
                    return

                skill_id = SkillMatchingManager.add_student_skill(
                    student_id=student_id,
                    skill_name=skill_name,
                    skill_category=skill_category,
                    proficiency_level=proficiency_level,
                    years_experience=years_experience
                )

                messagebox.showinfo("Success", f"Skill added successfully!\nSkill ID: {skill_id}")
                dialog.destroy()
                self.refresh_skills()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to add skill: {e}")

        ttk.Button(dialog, text="Add Skill", command=submit).pack(pady=20)

    def find_matching_jobs(self):
        """Find jobs matching student's skills"""
        if not self.current_user or self.current_user.get('role') != 'student':
            messagebox.showerror("Error", "Only students can use skill matching.")
            return

        # Ask for minimum match percentage
        min_match = tk.simpledialog.askinteger("Skill Matching",
                                                "Minimum match percentage (0-100):",
                                                initialvalue=50, minvalue=0, maxvalue=100)

        if min_match is None:
            return

        try:
            student_id = self.current_user.get('username', '')
            matching_jobs = SkillMatchingManager.find_matching_jobs(student_id, min_match)

            if not matching_jobs:
                messagebox.showinfo("No Matches", f"No jobs found matching your skills (minimum {min_match}% match).")
                return

            # Create results window
            results_window = tk.Toplevel(self.root)
            results_window.title(f"Matching Jobs (≥{min_match}% match)")
            results_window.geometry("1000x600")

            # Create treeview
            columns = ('Job ID', 'Match %', 'Title', 'Employer', 'Rate', 'Skills Matched')
            tree = ttk.Treeview(results_window, columns=columns, show='headings')

            for col in columns:
                tree.heading(col, text=col)

            tree.column('Job ID', width=80)
            tree.column('Match %', width=80)
            tree.column('Title', width=250)
            tree.column('Employer', width=200)
            tree.column('Rate', width=100)
            tree.column('Skills Matched', width=150)

            for job in matching_jobs:
                values = (
                    job['job_id'],
                    f"{job['match_percentage']:.1f}%",
                    job['job_title'],
                    job['employer_name'],
                    f"£{job['hourly_rate']:.2f}",
                    f"{job['required_skills_matched']}/{job['total_required_skills']}"
                )
                tree.insert('', tk.END, values=values)

            vsb = ttk.Scrollbar(results_window, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=vsb.set)

            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
            vsb.pack(side=tk.RIGHT, fill=tk.Y, pady=10)

            # Double-click to view details
            def on_double_click(event):
                selected = tree.selection()
                if selected:
                    job_id = tree.item(selected[0])['values'][0]
                    self.view_specific_job_details(job_id)

            tree.bind('<Double-Button-1>', on_double_click)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to find matching jobs: {e}")

    def view_specific_job_details(self, job_id):
        """View details for a specific job ID"""
        try:
            job = JobPostingManager.get_job_details(job_id)
            if not job:
                messagebox.showerror("Error", "Job not found.")
                return

            # Create details window (similar to view_job_details but standalone)
            details_window = tk.Toplevel(self.root)
            details_window.title(f"Job Details - {job['job_title']}")
            details_window.geometry("700x800")

            text = scrolledtext.ScrolledText(details_window, wrap=tk.WORD, padx=10, pady=10)
            text.pack(fill=tk.BOTH, expand=True)

            text.insert(tk.END, f"{'=' * 60}\n{job['job_title']}\n{'=' * 60}\n\n")
            text.insert(tk.END, f"Job ID: {job['job_id']}\n")
            text.insert(tk.END, f"Employer: {job['employer_name']}\n")
            text.insert(tk.END, f"Category: {job['job_category']}\n")
            text.insert(tk.END, f"Type: {job['employment_type']}\n")
            text.insert(tk.END, f"Rate: £{job['hourly_rate']:.2f}/hour\n")
            text.insert(tk.END, f"Location: {job['location']}\n\n")
            text.insert(tk.END, f"Description:\n{job['job_description']}\n")

            text.config(state=tk.DISABLED)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load job details: {e}")

    # ======================== ADMIN METHODS ========================

    def show_post_job_dialog(self):
        """Show post job dialog (admin only)"""
        if not self._is_admin_or_staff():
            messagebox.showerror("Error", "You don't have permission to post jobs.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Post New Job")
        dialog.geometry("600x700")

        # Create scrollable frame
        canvas = tk.Canvas(dialog)
        scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Form fields
        fields = {}

        ttk.Label(scrollable_frame, text="Employer/Department Name:").grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)
        fields['employer_name'] = ttk.Entry(scrollable_frame, width=40)
        fields['employer_name'].grid(row=0, column=1, padx=10, pady=5)

        ttk.Label(scrollable_frame, text="Job Title:").grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)
        fields['job_title'] = ttk.Entry(scrollable_frame, width=40)
        fields['job_title'].grid(row=1, column=1, padx=10, pady=5)

        ttk.Label(scrollable_frame, text="Job Category:").grid(row=2, column=0, sticky=tk.W, padx=10, pady=5)
        fields['job_category'] = ttk.Entry(scrollable_frame, width=40)
        fields['job_category'].grid(row=2, column=1, padx=10, pady=5)

        ttk.Label(scrollable_frame, text="Employment Type:").grid(row=3, column=0, sticky=tk.W, padx=10, pady=5)
        fields['employment_type'] = ttk.Combobox(scrollable_frame, width=38, state='readonly')
        fields['employment_type']['values'] = ('work-study', 'part-time', 'internship', 'temp')
        fields['employment_type'].current(1)
        fields['employment_type'].grid(row=3, column=1, padx=10, pady=5)

        ttk.Label(scrollable_frame, text="Hourly Rate ($):").grid(row=4, column=0, sticky=tk.W, padx=10, pady=5)
        fields['hourly_rate'] = ttk.Entry(scrollable_frame, width=20)
        fields['hourly_rate'].grid(row=4, column=1, padx=10, pady=5, sticky=tk.W)

        ttk.Label(scrollable_frame, text="Hours per Week:").grid(row=5, column=0, sticky=tk.W, padx=10, pady=5)
        fields['hours_per_week'] = ttk.Entry(scrollable_frame, width=20)
        fields['hours_per_week'].grid(row=5, column=1, padx=10, pady=5, sticky=tk.W)

        ttk.Label(scrollable_frame, text="Number of Positions:").grid(row=6, column=0, sticky=tk.W, padx=10, pady=5)
        fields['total_positions'] = ttk.Entry(scrollable_frame, width=20)
        fields['total_positions'].insert(0, "1")
        fields['total_positions'].grid(row=6, column=1, padx=10, pady=5, sticky=tk.W)

        ttk.Label(scrollable_frame, text="Location:").grid(row=7, column=0, sticky=tk.W, padx=10, pady=5)
        fields['location'] = ttk.Entry(scrollable_frame, width=40)
        fields['location'].grid(row=7, column=1, padx=10, pady=5)

        ttk.Label(scrollable_frame, text="Job Description:").grid(row=8, column=0, sticky=tk.W, padx=10, pady=5)
        fields['job_description'] = scrolledtext.ScrolledText(scrollable_frame, width=40, height=6)
        fields['job_description'].grid(row=8, column=1, padx=10, pady=5)

        ttk.Label(scrollable_frame, text="Contact Email:").grid(row=9, column=0, sticky=tk.W, padx=10, pady=5)
        fields['contact_email'] = ttk.Entry(scrollable_frame, width=40)
        fields['contact_email'].grid(row=9, column=1, padx=10, pady=5)

        ttk.Label(scrollable_frame, text="Application Deadline:").grid(row=10, column=0, sticky=tk.W, padx=10, pady=5)
        fields['application_deadline'] = ttk.Entry(scrollable_frame, width=20)
        fields['application_deadline'].grid(row=10, column=1, padx=10, pady=5, sticky=tk.W)

        def submit():
            try:
                employer_name = fields['employer_name'].get().strip()
                job_title = fields['job_title'].get().strip()
                job_category = fields['job_category'].get().strip()
                employment_type = fields['employment_type'].get()
                hourly_rate = float(fields['hourly_rate'].get())
                job_description = fields['job_description'].get(1.0, tk.END).strip()
                location = fields['location'].get().strip()

                if not all([employer_name, job_title, job_category, job_description, location]):
                    messagebox.showwarning("Warning", "Please fill in all required fields.")
                    return

                kwargs = {}
                if fields['hours_per_week'].get().strip():
                    kwargs['hours_per_week'] = int(fields['hours_per_week'].get())
                if fields['total_positions'].get().strip():
                    kwargs['total_positions'] = int(fields['total_positions'].get())
                if fields['contact_email'].get().strip():
                    kwargs['contact_email'] = fields['contact_email'].get().strip()
                if fields['application_deadline'].get().strip():
                    kwargs['application_deadline'] = fields['application_deadline'].get().strip()

                kwargs['is_work_study'] = 1 if employment_type == 'work-study' else 0

                job_id = JobPostingManager.post_job(
                    employer_name=employer_name,
                    job_title=job_title,
                    job_category=job_category,
                    employment_type=employment_type,
                    hourly_rate=hourly_rate,
                    job_description=job_description,
                    location=location,
                    **kwargs
                )

                messagebox.showinfo("Success", f"Job posted successfully!\nJob ID: {job_id}")
                dialog.destroy()
                self.refresh_jobs()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to post job: {e}")

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        ttk.Button(dialog, text="Post Job", command=submit).pack(pady=10)

    def show_manage_postings(self):
        """Show manage postings dialog"""
        messagebox.showinfo("Manage Postings", "This feature allows you to update and deactivate job postings.\n\nSelect a job from the Browse Jobs tab and use the admin functions.")

    def show_review_applications(self):
        """Show review applications dialog"""
        messagebox.showinfo("Review Applications", "This feature allows you to review and process applications.\n\nImplement application review interface as needed.")

    def show_hire_student_dialog(self):
        """Show hire student dialog"""
        messagebox.showinfo("Hire Student", "This feature allows you to hire students for positions.\n\nImplement hiring interface as needed.")

    def show_approve_hours(self):
        """Show approve hours dialog"""
        messagebox.showinfo("Approve Hours", "This feature allows you to approve work hours.\n\nImplement hours approval interface as needed.")

    def show_performance_review_dialog(self):
        """Show performance review dialog"""
        messagebox.showinfo("Performance Review", "This feature allows you to create performance reviews.\n\nImplement review interface as needed.")

    def show_manage_employment(self):
        """Show manage employment dialog"""
        messagebox.showinfo("Manage Employment", "This feature allows you to manage employment records.\n\nImplement employment management interface as needed.")

    def show_reports(self):
        """Show reports dialog"""
        messagebox.showinfo("Reports", "This feature provides various reports and analytics.\n\nImplement reporting interface as needed.")

    # ======================== HELPER METHODS ========================

    def _is_admin_or_staff(self) -> bool:
        """Check if current user is admin or staff"""
        if not self.current_user:
            return False
        role = self.current_user.get('role', '').lower()
        return role in ['admin', 'staff', 'instructor']

    def update_status(self, message: str):
        """Update status bar message"""
        self.status_bar.config(text=message)
        self.root.update_idletasks()

    def show_help(self):
        """Show help dialog"""
        help_text = """
        STUDENT JOB BOARD - User Guide

        BROWSE JOBS:
        - View all available job postings
        - Filter by category, type, location
        - View detailed job information
        - Apply for jobs directly

        MY APPLICATIONS:
        - Track application status
        - View application details
        - Withdraw applications

        MY JOBS & HOURS:
        - View current employment
        - Clock in/out for work
        - Track work hours and earnings
        - View work-study information

        SKILLS & MATCHING:
        - Add and manage your skills
        - Find jobs matching your skills
        - View skill requirements for jobs

        For more help, contact support.
        """
        messagebox.showinfo("User Guide", help_text)

    def show_about(self):
        """Show about dialog"""
        about_text = """
        Student Job Board System
        Version 1.0.0

        A comprehensive job board system for managing
        on-campus employment, work-study programs,
        and student job applications.

        Features:
        • Job posting and search
        • Application management
        • Work hour tracking
        • Skill-based job matching
        • Work-study management
        • Performance reviews
        """
        messagebox.showinfo("About", about_text)


def main():
    """Entry point for the GUI"""
    gui = StudentJobsGUI()
    gui.run()


if __name__ == "__main__":
    main()
