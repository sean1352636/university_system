"""
Career Services Platform GUI

Comprehensive GUI for job postings, resume management, interview scheduling,
career events, alumni mentorship, and skills tracking.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from datetime import datetime
from typing import Optional
import traceback

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.domain.career.services.career_services_core import (
    JobManager, ResumeManager, InterviewManager, CareerEventManager,
    MentorshipManager, SkillsManager
)
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

# Import secure file upload handler
try:
    from education_system.university_system.infrastructure.security.file_upload import (
        validate_upload,
        secure_filename,
    )
    SECURE_UPLOAD_AVAILABLE = True
except ImportError:
    SECURE_UPLOAD_AVAILABLE = False
    validate_upload = None
    def secure_filename(x):
        return x

# Import internationalization (i18n) for multi-language support
try:
    from education_system.university_system.modules.shared.utils.i18n import (
        get_text as _t,
        get_current_language,
    )
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    _t = lambda key, **kwargs: kwargs.get("default", key)
    get_current_language = lambda: "en"

try:
    from education_system.university_system.infrastructure.email.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False


class CareerServicesGUI:
    """Main Career Services Platform GUI"""

    def __init__(self, root, auth):
        self.root = root
        self.auth = auth

        if not auth or not hasattr(auth, 'current_user') or not auth.current_user:
            messagebox.showerror(_t("common.error"), _t("careers.error.login_required"))
            return

        self.current_user = auth.current_user
        self.user_role = self.current_user.get('role', 'student')

        self.window = tk.Toplevel(root)
        self.window.title(_t("careers.window_title", default="Career Services Platform"))
        self.window.geometry("1000x650")
        self.window.minsize(900, 550)

        # Initialize database tables
        self._init_database()

        self.create_widgets()

        log_activity('Accessed Career Services Platform', user=self.current_user.get('username'))
        print("✅ Career Services Platform GUI opened successfully")

    def get_user_role(self):
        """Get the current user's role"""
        try:
            return self.user_role.lower() if self.user_role else None
        except Exception as e:
            print(f"Error getting user role: {e}")
            return None

    def is_admin(self):
        """Check if current user is admin"""
        role = self.get_user_role()
        return role == 'admin'

    def is_staff(self):
        """Check if current user is staff or career advisor"""
        role = self.get_user_role()
        return role in ['staff', 'career_advisor', 'career_services']

    def is_student(self):
        """Check if current user is student"""
        role = self.get_user_role()
        return role == 'student'

    def _init_database(self):
        """Initialize database tables for career services"""
        try:
            from education_system.university_system.infrastructure.database.schemas.career_alumni_schemas import init_career_services_system_db
            init_career_services_system_db()
        except ImportError as e:
            print(f"⚠️  Warning: Could not import database schemas: {e}")
        except Exception as e:
            print(f"⚠️  Warning: Database initialization error: {e}")
            messagebox.showwarning(_t("common.warning"), _t("careers.warning.db_init", error=str(e)))

    def create_widgets(self):
        """Create all GUI widgets"""
        # Main container
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(
            title_frame,
            text=_t("careers.title", default="Career Services Platform"),
            font=('Arial', 18, 'bold')
        ).pack(side=tk.LEFT)

        ttk.Label(
            title_frame,
            text=_t("careers.user_role_display", default="User: {username} | Role: {role}").format(
                username=self.current_user.get('username'), role=self.user_role
            ),
            font=('Arial', 10)
        ).pack(side=tk.RIGHT)

        # Bottom button frame - pack first to reserve space at bottom
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))

        ttk.Button(
            button_frame,
            text=_t("common.return_to_main_menu", default="Return to Homescreen"),
            command=self.return_to_homescreen
        ).pack(pady=5)

        # Notebook for different sections - pack after button so it fills remaining space
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        # Create tabs
        self.create_job_postings_tab()
        self.create_resume_management_tab()
        self.create_interviews_tab()
        self.create_career_events_tab()
        self.create_mentorship_tab()
        self.create_skills_tab()

    def create_job_postings_tab(self):
        """Create job postings tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("careers.tabs.job_postings", default="Job Postings"))

        # Split into left (list) and right (details/form)
        paned = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left: Job listings
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        ttk.Label(left_frame, text=_t("careers.active_job_postings"), font=('Arial', 12, 'bold')).pack(pady=5)

        # Filters
        filter_frame = ttk.LabelFrame(left_frame, text=_t("careers.filters"), padding="5")
        filter_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(filter_frame, text=_t("careers.labels.job_type") + ":").grid(row=0, column=0, sticky=tk.W, padx=2)
        self.job_type_filter = ttk.Combobox(filter_frame, values=[
            _t("common.all"), _t("careers.job_types.full_time"), _t("careers.job_types.part_time"),
            _t("careers.job_types.internship"), _t("careers.job_types.co_op")
        ], state='readonly', width=15)
        self.job_type_filter.set(_t("common.all"))
        self.job_type_filter.grid(row=0, column=1, padx=2)
        self.job_type_filter.bind('<<ComboboxSelected>>', lambda e: self.load_jobs())

        ttk.Label(filter_frame, text=_t("careers.labels.location") + ":").grid(row=0, column=2, sticky=tk.W, padx=2)
        self.location_filter = ttk.Entry(filter_frame, width=20)
        self.location_filter.grid(row=0, column=3, padx=2)

        ttk.Button(filter_frame, text=_t("common.search"), command=self.load_jobs).grid(row=0, column=4, padx=5)

        # Job list
        list_frame = ttk.Frame(left_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.jobs_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, font=('Arial', 10))
        self.jobs_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.jobs_listbox.yview)
        self.jobs_listbox.bind('<<ListboxSelect>>', self.on_job_select)

        # Right: Job details/form
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=1)

        if self.user_role in ['admin', 'staff']:
            # Form to create job posting
            form_frame = ttk.LabelFrame(right_frame, text=_t("careers.create_job_posting"), padding="10")
            form_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            # Job form fields
            ttk.Label(form_frame, text=_t("careers.labels.job_title") + ":").grid(row=0, column=0, sticky=tk.W, pady=2)
            self.job_title_entry = ttk.Entry(form_frame, width=40)
            self.job_title_entry.grid(row=0, column=1, pady=2, sticky=tk.EW)

            ttk.Label(form_frame, text=_t("careers.labels.company") + ":").grid(row=1, column=0, sticky=tk.W, pady=2)
            self.company_entry = ttk.Entry(form_frame, width=40)
            self.company_entry.grid(row=1, column=1, pady=2, sticky=tk.EW)

            ttk.Label(form_frame, text=_t("careers.labels.job_type") + ":").grid(row=2, column=0, sticky=tk.W, pady=2)
            self.job_type_combo = ttk.Combobox(form_frame, values=[
                _t("careers.job_types.full_time"), _t("careers.job_types.part_time"),
                _t("careers.job_types.internship"), _t("careers.job_types.co_op")
            ], state='readonly', width=37)
            self.job_type_combo.set(_t("careers.job_types.full_time"))
            self.job_type_combo.grid(row=2, column=1, pady=2, sticky=tk.EW)

            ttk.Label(form_frame, text=_t("careers.labels.location") + ":").grid(row=3, column=0, sticky=tk.W, pady=2)
            self.location_entry = ttk.Entry(form_frame, width=40)
            self.location_entry.grid(row=3, column=1, pady=2, sticky=tk.EW)

            ttk.Label(form_frame, text=_t("careers.labels.salary_range") + ":").grid(row=4, column=0, sticky=tk.W, pady=2)
            self.salary_entry = ttk.Entry(form_frame, width=40)
            self.salary_entry.grid(row=4, column=1, pady=2, sticky=tk.EW)

            ttk.Label(form_frame, text=_t("careers.labels.description") + ":").grid(row=5, column=0, sticky=tk.NW, pady=2)
            self.description_text = scrolledtext.ScrolledText(form_frame, width=40, height=5)
            self.description_text.grid(row=5, column=1, pady=2, sticky=tk.EW)

            ttk.Label(form_frame, text=_t("careers.labels.requirements") + ":").grid(row=6, column=0, sticky=tk.NW, pady=2)
            self.requirements_text = scrolledtext.ScrolledText(form_frame, width=40, height=5)
            self.requirements_text.grid(row=6, column=1, pady=2, sticky=tk.EW)

            ttk.Label(form_frame, text=_t("careers.labels.deadline") + ":").grid(row=7, column=0, sticky=tk.W, pady=2)
            self.deadline_entry = ttk.Entry(form_frame, width=40)
            self.deadline_entry.insert(0, _t("common.date_format"))
            self.deadline_entry.grid(row=7, column=1, pady=2, sticky=tk.EW)

            form_frame.columnconfigure(1, weight=1)

            ttk.Button(form_frame, text=_t("careers.btn.create_job_posting"), command=self.create_job_posting).grid(row=8, column=1, pady=10)
        else:
            # Job details for students
            details_frame = ttk.LabelFrame(right_frame, text=_t("careers.job_details"), padding="10")
            details_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            self.job_details_text = scrolledtext.ScrolledText(details_frame, wrap=tk.WORD, state='disabled')
            self.job_details_text.pack(fill=tk.BOTH, expand=True)

            # Application section
            apply_frame = ttk.Frame(details_frame)
            apply_frame.pack(fill=tk.X, pady=10)

            ttk.Button(apply_frame, text=_t("careers.btn.apply_for_job"), command=self.apply_for_job).pack(side=tk.LEFT, padx=5)

        # Load jobs
        self.load_jobs()

    def create_resume_management_tab(self):
        """Create resume management tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("careers.tabs.resume_management", default="Resume Management"))

        frame = ttk.Frame(tab, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=_t("careers.your_resumes", default="Your Resumes"), font=('Arial', 14, 'bold')).pack(pady=10)

        # Resume list
        list_frame = ttk.Frame(frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.resumes_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, height=10)
        self.resumes_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.resumes_listbox.yview)

        # Upload section
        upload_frame = ttk.LabelFrame(frame, text=_t("careers.upload_new_resume"), padding="10")
        upload_frame.pack(fill=tk.X, pady=10)

        ttk.Label(upload_frame, text=_t("careers.labels.resume_name") + ":").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.resume_name_entry = ttk.Entry(upload_frame, width=40)
        self.resume_name_entry.grid(row=0, column=1, pady=5)

        ttk.Label(upload_frame, text=_t("careers.labels.template_used") + ":").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.template_combo = ttk.Combobox(upload_frame, values=[
            _t("careers.templates.professional"), _t("careers.templates.academic"),
            _t("careers.templates.creative"), _t("careers.templates.technical"), _t("common.none")
        ], state='readonly', width=37)
        self.template_combo.set(_t("careers.templates.professional"))
        self.template_combo.grid(row=1, column=1, pady=5)

        ttk.Label(upload_frame, text=_t("careers.labels.file") + ":").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.file_path_var = tk.StringVar()
        ttk.Entry(upload_frame, textvariable=self.file_path_var, width=30, state='readonly').grid(row=2, column=1, sticky=tk.W, pady=5)
        ttk.Button(upload_frame, text=_t("common.browse"), command=self.browse_file).grid(row=2, column=2, padx=5)

        self.primary_var = tk.BooleanVar()
        ttk.Checkbutton(upload_frame, text=_t("careers.set_as_primary_resume"), variable=self.primary_var).grid(row=3, column=1, sticky=tk.W, pady=5)

        ttk.Button(upload_frame, text=_t("careers.btn.upload_resume"), command=self.upload_resume).grid(row=4, column=1, pady=10)

        # Load resumes
        self.load_resumes()

    def create_interviews_tab(self):
        """Create interview scheduling tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("careers.tabs.interviews", default="Interviews"))

        frame = ttk.Frame(tab, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=_t("careers.interview_schedules", default="Interview Schedules"), font=('Arial', 14, 'bold')).pack(pady=10)

        # Interview list
        columns = ('ID', 'Application', 'Type', 'Date', 'Time', 'Status')
        columns_headers = [
            _t("careers.columns.id"), _t("careers.columns.application"),
            _t("careers.columns.type"), _t("careers.columns.date"),
            _t("careers.columns.time"), _t("careers.columns.status")
        ]
        self.interviews_tree = ttk.Treeview(frame, columns=columns, show='headings', height=15)

        for col, header in zip(columns, columns_headers):
            self.interviews_tree.heading(col, text=header)
            self.interviews_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.interviews_tree.yview)
        self.interviews_tree.configure(yscroll=scrollbar.set)

        self.interviews_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        if self.user_role in ['admin', 'staff']:
            # Schedule interview form
            schedule_frame = ttk.LabelFrame(frame, text=_t("careers.schedule_interview"), padding="10")
            schedule_frame.pack(fill=tk.X, pady=10)

            ttk.Label(schedule_frame, text=_t("careers.labels.application_id") + ":").grid(row=0, column=0, sticky=tk.W, pady=2)
            self.app_id_entry = ttk.Entry(schedule_frame, width=20)
            self.app_id_entry.grid(row=0, column=1, pady=2)

            ttk.Button(schedule_frame, text=_t("careers.btn.schedule"), command=self.schedule_interview).grid(row=0, column=2, padx=10)

        self.load_interviews()

    def create_career_events_tab(self):
        """Create career events tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("careers.tabs.career_events", default="Career Events"))

        paned = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left: Event list
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        ttk.Label(left_frame, text=_t("careers.upcoming_events", default="Upcoming Events"), font=('Arial', 12, 'bold')).pack(pady=5)

        self.events_listbox = tk.Listbox(left_frame, font=('Arial', 10))
        self.events_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.events_listbox.bind('<<ListboxSelect>>', self.on_event_select)

        # Right: Event details/form
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=1)

        if self.user_role in ['admin', 'staff']:
            # Create event form
            form_frame = ttk.LabelFrame(right_frame, text=_t("careers.create_career_event"), padding="10")
            form_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            ttk.Label(form_frame, text=_t("careers.labels.event_name") + ":").grid(row=0, column=0, sticky=tk.W, pady=2)
            self.event_name_entry = ttk.Entry(form_frame, width=40)
            self.event_name_entry.grid(row=0, column=1, pady=2)

            ttk.Label(form_frame, text=_t("careers.labels.event_type") + ":").grid(row=1, column=0, sticky=tk.W, pady=2)
            self.event_type_combo = ttk.Combobox(form_frame, values=[
                _t("careers.event_types.career_fair"), _t("careers.event_types.networking"),
                _t("careers.event_types.workshop"), _t("careers.event_types.info_session")
            ], state='readonly', width=37)
            self.event_type_combo.set(_t("careers.event_types.career_fair"))
            self.event_type_combo.grid(row=1, column=1, pady=2)

            ttk.Label(form_frame, text=_t("careers.labels.date") + ":").grid(row=2, column=0, sticky=tk.W, pady=2)
            self.event_date_entry = ttk.Entry(form_frame, width=40)
            self.event_date_entry.insert(0, _t("common.date_format"))
            self.event_date_entry.grid(row=2, column=1, pady=2)

            ttk.Label(form_frame, text=_t("careers.labels.time") + ":").grid(row=3, column=0, sticky=tk.W, pady=2)
            self.event_time_entry = ttk.Entry(form_frame, width=40)
            self.event_time_entry.insert(0, _t("common.time_format"))
            self.event_time_entry.grid(row=3, column=1, pady=2)

            ttk.Label(form_frame, text=_t("careers.labels.location") + ":").grid(row=4, column=0, sticky=tk.W, pady=2)
            self.event_location_entry = ttk.Entry(form_frame, width=40)
            self.event_location_entry.grid(row=4, column=1, pady=2)

            ttk.Label(form_frame, text=_t("careers.labels.max_attendees") + ":").grid(row=5, column=0, sticky=tk.W, pady=2)
            self.max_attendees_entry = ttk.Entry(form_frame, width=40)
            self.max_attendees_entry.insert(0, "100")
            self.max_attendees_entry.grid(row=5, column=1, pady=2)

            ttk.Button(form_frame, text=_t("careers.btn.create_event"), command=self.create_event).grid(row=6, column=1, pady=10)
        else:
            # Event details and registration
            details_frame = ttk.LabelFrame(right_frame, text=_t("careers.event_details"), padding="10")
            details_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            self.event_details_text = scrolledtext.ScrolledText(details_frame, wrap=tk.WORD, state='disabled')
            self.event_details_text.pack(fill=tk.BOTH, expand=True)

            ttk.Button(details_frame, text=_t("careers.btn.register_for_event"), command=self.register_for_event).pack(pady=10)

        self.load_events()

    def create_mentorship_tab(self):
        """Create mentorship program tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("careers.tabs.mentorship", default="Mentorship"))

        frame = ttk.Frame(tab, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=_t("careers.alumni_mentorship_program", default="Alumni Mentorship Program"), font=('Arial', 14, 'bold')).pack(pady=10)

        # Mentor list
        ttk.Label(frame, text=_t("careers.available_mentors", default="Available Mentors"), font=('Arial', 11, 'bold')).pack(pady=5)

        columns = ('ID', 'Name', 'Job Title', 'Company', 'Industry', 'Expertise')
        columns_headers = [
            _t("careers.columns.id"), _t("careers.columns.name"),
            _t("careers.columns.job_title"), _t("careers.columns.company"),
            _t("careers.columns.industry"), _t("careers.columns.expertise")
        ]
        self.mentors_tree = ttk.Treeview(frame, columns=columns, show='headings', height=10)

        for col, header in zip(columns, columns_headers):
            self.mentors_tree.heading(col, text=header)
            self.mentors_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.mentors_tree.yview)
        self.mentors_tree.configure(yscroll=scrollbar.set)

        self.mentors_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=10)

        if self.user_role == 'student':
            ttk.Button(button_frame, text=_t("careers.btn.request_mentorship"), command=self.request_mentorship).pack(side=tk.LEFT, padx=5)

        self.load_mentors()

    def create_skills_tab(self):
        """Create skills tracking tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("careers.tabs.skills", default="Skills"))

        frame = ttk.Frame(tab, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=_t("careers.your_skills_profile", default="Your Skills Profile"), font=('Arial', 14, 'bold')).pack(pady=10)

        # Skills list
        columns = ('Skill', 'Category', 'Proficiency', 'Verified')
        columns_headers = [
            _t("careers.columns.skill"), _t("careers.columns.category"),
            _t("careers.columns.proficiency"), _t("careers.columns.verified")
        ]
        self.skills_tree = ttk.Treeview(frame, columns=columns, show='headings', height=12)

        for col, header in zip(columns, columns_headers):
            self.skills_tree.heading(col, text=header)
            self.skills_tree.column(col, width=150)

        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.skills_tree.yview)
        self.skills_tree.configure(yscroll=scrollbar.set)

        self.skills_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Add skill form
        add_frame = ttk.LabelFrame(frame, text=_t("careers.add_new_skill"), padding="10")
        add_frame.pack(fill=tk.X, pady=10)

        ttk.Label(add_frame, text=_t("careers.labels.skill_name") + ":").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.skill_name_entry = ttk.Entry(add_frame, width=30)
        self.skill_name_entry.grid(row=0, column=1, pady=2)

        ttk.Label(add_frame, text=_t("careers.labels.category") + ":").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.skill_category_combo = ttk.Combobox(add_frame, values=[
            _t("careers.skill_categories.technical"), _t("careers.skill_categories.soft_skills"),
            _t("careers.skill_categories.language"), _t("careers.skill_categories.tools"),
            _t("common.other")
        ], state='readonly', width=27)
        self.skill_category_combo.set(_t("careers.skill_categories.technical"))
        self.skill_category_combo.grid(row=1, column=1, pady=2)

        ttk.Label(add_frame, text=_t("careers.labels.proficiency") + ":").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.proficiency_combo = ttk.Combobox(add_frame, values=[
            _t("careers.proficiency.beginner"), _t("careers.proficiency.intermediate"),
            _t("careers.proficiency.advanced"), _t("careers.proficiency.expert")
        ], state='readonly', width=27)
        self.proficiency_combo.set(_t("careers.proficiency.intermediate"))
        self.proficiency_combo.grid(row=2, column=1, pady=2)

        ttk.Button(add_frame, text=_t("careers.btn.add_skill"), command=self.add_skill).grid(row=3, column=1, pady=10)

        self.load_skills()

    # Data loading methods
    def load_jobs(self):
        """Load job postings"""
        try:
            self.jobs_listbox.delete(0, tk.END)

            filters = {}
            # Compare against translated "All" text, not hardcoded string
            job_type = self.job_type_filter.get()
            all_text = _t("common.all")

            # Debug output
            print(f"🔍 Loading jobs - job_type: '{job_type}', all_text: '{all_text}'")

            if job_type and job_type != all_text:
                filters['job_type'] = job_type
                print(f"   Filtering by job_type: '{job_type}'")

            location = self.location_filter.get().strip()
            if location:
                filters['location'] = location
                print(f"   Filtering by location: '{location}'")

            print(f"   Filters being applied: {filters}")
            jobs = JobManager.get_active_jobs(filters)
            self.jobs_data = jobs

            print(f"   Found {len(jobs)} jobs")

            if not jobs:
                print("   ⚠️  No jobs found with current filters")

            for job in jobs:
                display_text = f"{job['job_title']} - {job['company_name']} ({job['location']})"
                self.jobs_listbox.insert(tk.END, display_text)
                print(f"   Added job: {display_text}")

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("careers.error.load_jobs", error=str(e)))
            print(f"❌ Error loading jobs: {traceback.format_exc()}")

    def load_resumes(self):
        """Load user resumes"""
        try:
            self.resumes_listbox.delete(0, tk.END)

            student_id = self.current_user.get('student_id') or self.current_user.get('username')
            resumes = ResumeManager.get_student_resumes(student_id)

            for resume in resumes:
                primary = " [PRIMARY]" if resume.get('is_primary') else ""
                display_text = f"{resume['resume_name']}{primary} - {resume['created_at']}"
                self.resumes_listbox.insert(tk.END, display_text)

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("careers.error.load_resumes", error=str(e)))
            print(f"❌ Error loading resumes: {traceback.format_exc()}")

    def load_interviews(self):
        """Load interview schedules"""
        try:
            for item in self.interviews_tree.get_children():
                self.interviews_tree.delete(item)

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT i.interview_id, i.application_id, i.interview_type,
                           i.interview_date, i.interview_time, i.status
                    FROM interview_schedules i
                    JOIN job_applications ja ON i.application_id = ja.application_id
                    WHERE ja.applicant_id = ?
                    ORDER BY i.interview_date, i.interview_time
                ''', (self.current_user.get('student_id') or self.current_user.get('username'),))

                for row in cursor.fetchall():
                    self.interviews_tree.insert('', tk.END, values=row)

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("careers.error.load_interviews", error=str(e)))
            print(f"❌ Error loading interviews: {traceback.format_exc()}")

    def load_events(self):
        """Load career events"""
        try:
            self.events_listbox.delete(0, tk.END)

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT event_id, title AS event_name, event_type, start_datetime AS event_date, start_datetime AS event_time, location
                    FROM unified_events
                    WHERE source_type = 'career'
                    AND start_datetime >= date('now')
                    ORDER BY start_datetime
                ''')

                self.events_data = [dict(row) for row in cursor.fetchall()]

                for event in self.events_data:
                    display_text = f"{event['event_name']} - {event['event_date']} {event['event_time']}"
                    self.events_listbox.insert(tk.END, display_text)

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("careers.error.load_events", error=str(e)))
            print(f"❌ Error loading events: {traceback.format_exc()}")

    def load_mentors(self):
        """Load available mentors"""
        try:
            for item in self.mentors_tree.get_children():
                self.mentors_tree.delete(item)

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT m.mentor_id, m.alumni_student_id, m.job_title, m.company,
                           m.industry, m.expertise_areas
                    FROM alumni_mentors m
                    WHERE m.is_active = 1
                    AND (SELECT COUNT(*) FROM mentorship_matches mm
                         WHERE mm.mentor_id = m.mentor_id AND mm.status = 'active') < m.max_mentees
                    ORDER BY m.industry, m.company
                ''')

                for row in cursor.fetchall():
                    self.mentors_tree.insert('', tk.END, values=row)

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("careers.error.load_mentors", error=str(e)))
            print(f"❌ Error loading mentors: {traceback.format_exc()}")

    def load_skills(self):
        """Load user skills"""
        try:
            for item in self.skills_tree.get_children():
                self.skills_tree.delete(item)

            student_id = self.current_user.get('student_id') or self.current_user.get('username')
            skills = SkillsManager.get_student_skills(student_id)

            for skill in skills:
                verified = "✓" if skill.get('verified') else ""
                self.skills_tree.insert('', tk.END, values=(
                    skill['skill_name'],
                    skill['skill_category'],
                    skill['proficiency_level'],
                    verified
                ))

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("careers.error.load_skills", error=str(e)))
            print(f"❌ Error loading skills: {traceback.format_exc()}")

    # Action methods
    def create_job_posting(self):
        """Create new job posting"""
        try:
            job_title = self.job_title_entry.get().strip()
            company = self.company_entry.get().strip()
            job_type = self.job_type_combo.get()
            location = self.location_entry.get().strip()
            salary = self.salary_entry.get().strip()
            description = self.description_text.get('1.0', tk.END).strip()
            requirements = self.requirements_text.get('1.0', tk.END).strip()
            deadline = self.deadline_entry.get().strip()

            if not all([job_title, company, location, description, requirements]):
                messagebox.showwarning(_t("common.warning"), _t("careers.warning.fill_required_fields"))
                return

            employer_id = getattr(self.current_user, 'user_id', None)

            print(f"🔨 Creating job with job_type: '{job_type}'")

            job_id = JobManager.create_job_posting(
                company_name=company,
                job_title=job_title,
                job_type=job_type,
                location=location,
                description=description,
                requirements=requirements,
                salary_range=salary,
                application_deadline=deadline if deadline != "YYYY-MM-DD" else "",
                employer_id=employer_id
            )

            print(f"✅ Job created successfully with ID: {job_id}")

            log_activity('create', 'job_posting', details={'job_id': job_id, 'title': job_title})

            messagebox.showinfo(_t("common.success"), _t("careers.messages.job_created", job_id=job_id))

            # Clear form
            self.job_title_entry.delete(0, tk.END)
            self.company_entry.delete(0, tk.END)
            self.location_entry.delete(0, tk.END)
            self.salary_entry.delete(0, tk.END)
            self.description_text.delete('1.0', tk.END)
            self.requirements_text.delete('1.0', tk.END)

            print(f"🔄 Calling load_jobs() to refresh the list...")
            self.load_jobs()

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("careers.error.create_job", error=str(e)))
            print(f"❌ Error creating job: {traceback.format_exc()}")

    def apply_for_job(self):
        """Apply for selected job"""
        try:
            selection = self.jobs_listbox.curselection()
            if not selection:
                messagebox.showwarning(_t("common.warning"), _t("careers.warning.select_job"))
                return

            job = self.jobs_data[selection[0]]
            student_id = self.current_user.get('student_id') or self.current_user.get('username')

            # Check if user is an alumni (required for job applications)
            from education_system.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.execute(
                    'SELECT alumni_id FROM alumni WHERE alumni_id = ? OR student_id = ?',
                    (student_id, student_id)
                )
                alumni_record = cursor.fetchone()
                if not alumni_record:
                    messagebox.showerror(
                        _t("careers.alumni_required_title"),
                        _t("careers.alumni_required_message")
                    )
                    return
                applicant_id = alumni_record[0]

            # Get primary resume
            resumes = ResumeManager.get_student_resumes(student_id)
            primary_resume = next((r for r in resumes if r.get('is_primary')), None)

            if not primary_resume:
                messagebox.showwarning(_t("common.warning"), _t("careers.warning.set_primary_resume"))
                return

            application_id = JobManager.apply_for_job(
                job_id=job['job_id'],
                student_id=applicant_id,  # Use alumni_id
                resume_id=primary_resume['resume_id']
            )

            log_activity('create', 'job_application', details={'application_id': application_id})

            messagebox.showinfo(_t("common.success"), _t("careers.messages.application_submitted", application_id=application_id))

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("careers.error.apply_job", error=str(e)))
            print(f"❌ Error applying for job: {traceback.format_exc()}")

    def upload_resume(self):
        """Upload new resume"""
        import os
        try:
            resume_name = self.resume_name_entry.get().strip()
            template = self.template_combo.get()
            file_path = self.file_path_var.get()
            is_primary = self.primary_var.get()

            if not resume_name or not file_path:
                messagebox.showwarning(_t("common.warning"), _t("careers.warning.provide_resume_info"))
                return

            # Security: Validate file before upload
            if SECURE_UPLOAD_AVAILABLE and validate_upload and os.path.exists(file_path):
                try:
                    with open(file_path, 'rb') as f:
                        file_content = f.read()
                    original_filename = os.path.basename(file_path)
                    validation = validate_upload(original_filename, file_content, category='documents')
                    if not validation['valid']:
                        messagebox.showerror(
                            _t("common.error"),
                            f"File validation failed: {validation['error']}"
                        )
                        log_activity(
                            'security_blocked',
                            'resume_upload',
                            filename=original_filename,
                            reason=validation['error']
                        )
                        return
                except Exception as e:
                    print(f"⚠️ File validation warning: {e}")

            student_id = self.current_user.get('student_id') or self.current_user.get('username')

            # Verify student exists in database
            from education_system.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.execute('SELECT student_id FROM students WHERE student_id = ?', (student_id,))
                if not cursor.fetchone():
                    messagebox.showerror(_t("common.error"), _t("careers.error.student_not_found"))
                    return

            resume_id = ResumeManager.upload_resume(
                student_id=student_id,
                resume_name=resume_name,
                file_url=file_path,
                template_used=template,
                is_primary=is_primary
            )

            log_activity('create', 'resume', details={'resume_id': resume_id})

            messagebox.showinfo(_t("common.success"), _t("careers.messages.resume_uploaded", resume_id=resume_id))

            # Clear form
            self.resume_name_entry.delete(0, tk.END)
            self.file_path_var.set("")
            self.primary_var.set(False)

            self.load_resumes()

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("careers.error.upload_resume", error=str(e)))
            print(f"❌ Error uploading resume: {traceback.format_exc()}")

    def browse_file(self):
        """Browse for file"""
        file_path = filedialog.askopenfilename(
            title=_t("careers.dialogs.select_resume"),
            filetypes=[
                (_t("careers.file_types.pdf"), "*.pdf"),
                (_t("careers.file_types.word"), "*.docx"),
                (_t("careers.file_types.all"), "*.*")
            ]
        )
        if file_path:
            self.file_path_var.set(file_path)

    def schedule_interview(self):
        """Schedule an interview"""
        try:
            app_id = self.app_id_entry.get().strip()
            if not app_id:
                messagebox.showwarning(_t("common.warning"), _t("careers.warning.enter_application_id"))
                return

            # Simple dialog for interview details
            dialog = tk.Toplevel(self.window)
            dialog.title(_t("careers.dialogs.schedule_interview"))
            dialog.geometry("400x300")

            ttk.Label(dialog, text=_t("careers.labels.interview_type") + ":").grid(row=0, column=0, pady=5, padx=5, sticky=tk.W)
            type_combo = ttk.Combobox(dialog, values=[
                _t("careers.interview_types.phone_screen"), _t("careers.interview_types.technical"),
                _t("careers.interview_types.behavioral"), _t("careers.interview_types.final")
            ], state='readonly')
            type_combo.set(_t("careers.interview_types.phone_screen"))
            type_combo.grid(row=0, column=1, pady=5, padx=5)

            ttk.Label(dialog, text=_t("careers.labels.date_format") + ":").grid(row=1, column=0, pady=5, padx=5, sticky=tk.W)
            date_entry = ttk.Entry(dialog)
            date_entry.grid(row=1, column=1, pady=5, padx=5)

            ttk.Label(dialog, text=_t("careers.labels.time_format") + ":").grid(row=2, column=0, pady=5, padx=5, sticky=tk.W)
            time_entry = ttk.Entry(dialog)
            time_entry.grid(row=2, column=1, pady=5, padx=5)

            def submit():
                try:
                    interview_id = InterviewManager.schedule_interview(
                        application_id=int(app_id),
                        interview_type=type_combo.get(),
                        interview_date=date_entry.get(),
                        interview_time=time_entry.get()
                    )

                    log_activity('create', 'interview', interview_id=interview_id)
                    messagebox.showinfo(_t("common.success"), _t("careers.messages.interview_scheduled", interview_id=interview_id))
                    dialog.destroy()
                    self.load_interviews()
                except Exception as e:
                    messagebox.showerror(_t("common.error"), _t("careers.error.schedule_interview", error=str(e)))

            ttk.Button(dialog, text=_t("careers.btn.schedule"), command=submit).grid(row=3, column=1, pady=20)

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("careers.error.schedule_interview", error=str(e)))
            print(f"❌ Error: {traceback.format_exc()}")

    def create_event(self):
        """Create career event"""
        try:
            event_name = self.event_name_entry.get().strip()
            event_type = self.event_type_combo.get()
            event_date = self.event_date_entry.get().strip()
            event_time = self.event_time_entry.get().strip()
            location = self.event_location_entry.get().strip()
            max_attendees = self.max_attendees_entry.get().strip()

            if not all([event_name, event_date, event_time, location]):
                messagebox.showwarning(_t("common.warning"), _t("careers.warning.fill_required_fields"))
                return

            event_id = CareerEventManager.create_event(
                event_name=event_name,
                event_type=event_type,
                event_date=event_date,
                event_time=event_time,
                location=location,
                max_attendees=int(max_attendees)
            )

            log_activity('create', 'career_event', details={'event_id': event_id})
            messagebox.showinfo(_t("common.success"), _t("careers.messages.event_created", event_id=event_id))

            # Clear form
            self.event_name_entry.delete(0, tk.END)
            self.event_date_entry.delete(0, tk.END)
            self.event_date_entry.insert(0, _t("common.date_format"))
            self.event_time_entry.delete(0, tk.END)
            self.event_time_entry.insert(0, _t("common.time_format"))
            self.event_location_entry.delete(0, tk.END)

            self.load_events()

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("careers.error.create_event", error=str(e)))
            print(f"❌ Error: {traceback.format_exc()}")

    def register_for_event(self):
        """Register for career event"""
        try:
            selection = self.events_listbox.curselection()
            if not selection:
                messagebox.showwarning(_t("common.warning"), _t("careers.warning.select_event"))
                return

            event = self.events_data[selection[0]]
            student_id = self.current_user.get('student_id') or self.current_user.get('username')

            registration_id = CareerEventManager.register_for_event(
                event_id=event['event_id'],
                student_id=student_id
            )

            log_activity('create', 'event_registration', registration_id=registration_id)
            messagebox.showinfo(_t("common.success"), _t("careers.messages.registered_successfully"))

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("careers.error.register_event", error=str(e)))
            print(f"❌ Error: {traceback.format_exc()}")

    def request_mentorship(self):
        """Request mentorship"""
        try:
            selection = self.mentors_tree.selection()
            if not selection:
                messagebox.showwarning(_t("common.warning"), _t("careers.warning.select_mentor"))
                return

            values = self.mentors_tree.item(selection[0])['values']
            mentor_id = values[0]
            student_id = self.current_user.get('student_id') or self.current_user.get('username')

            match_id = MentorshipManager.create_mentorship_match(
                mentor_id=mentor_id,
                mentee_student_id=student_id
            )

            log_activity('create', 'mentorship_match', match_id=match_id)
            messagebox.showinfo(_t("common.success"), _t("careers.messages.mentorship_requested"))

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("careers.error.request_mentorship", error=str(e)))
            print(f"❌ Error: {traceback.format_exc()}")

    def add_skill(self):
        """Add new skill"""
        try:
            skill_name = self.skill_name_entry.get().strip()
            category = self.skill_category_combo.get()
            proficiency = self.proficiency_combo.get()

            if not skill_name:
                messagebox.showwarning(_t("common.warning"), _t("careers.warning.enter_skill_name"))
                return

            student_id = self.current_user.get('student_id') or self.current_user.get('username')

            # Verify student exists in database
            from education_system.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.execute('SELECT student_id FROM students WHERE student_id = ?', (student_id,))
                if not cursor.fetchone():
                    messagebox.showerror(_t("common.error"), _t("careers.error.student_not_found_skills"))
                    return

            skill_id = SkillsManager.add_skill(
                student_id=student_id,
                skill_name=skill_name,
                skill_category=category,
                proficiency_level=proficiency
            )

            log_activity('create', 'skill', details={'skill_id': skill_id})
            messagebox.showinfo(_t("common.success"), _t("careers.messages.skill_added"))

            self.skill_name_entry.delete(0, tk.END)
            self.load_skills()

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("careers.error.add_skill", error=str(e)))
            print(f"❌ Error: {traceback.format_exc()}")

    def on_job_select(self, event):
        """Handle job selection"""
        if self.user_role not in ['student']:
            return

        try:
            selection = self.jobs_listbox.curselection()
            if not selection:
                return

            job = self.jobs_data[selection[0]]

            self.job_details_text.config(state='normal')
            self.job_details_text.delete('1.0', tk.END)

            details = f"""
Job Title: {job['job_title']}
Company: {job['company_name']}
Type: {job['job_type']}
Location: {job['location']}
Salary Range: {job.get('salary_range', 'Not specified')}

Description:
{job.get('description', '')}

Requirements:
{job.get('requirements', '')}

Application Deadline: {job.get('application_deadline', 'Not specified')}
Applications Received: {job.get('applications_count', 0)}
"""
            self.job_details_text.insert('1.0', details)
            self.job_details_text.config(state='disabled')

        except Exception as e:
            print(f"❌ Error showing job details: {e}")

    def on_event_select(self, event):
        """Handle event selection"""
        if self.user_role not in ['student']:
            return

        try:
            selection = self.events_listbox.curselection()
            if not selection:
                return

            event_data = self.events_data[selection[0]]

            self.event_details_text.config(state='normal')
            self.event_details_text.delete('1.0', tk.END)

            details = f"""
Event: {event_data['event_name']}
Type: {event_data['event_type']}
Date: {event_data['event_date']}
Time: {event_data['event_time']}
Location: {event_data['location']}
"""
            self.event_details_text.insert('1.0', details)
            self.event_details_text.config(state='disabled')

        except Exception as e:
            print(f"❌ Error showing event details: {e}")

    def return_to_homescreen(self):
        """Close this window and return to the main menu"""
        try:
            self.window.destroy()
        except Exception as e:
            print(f"Error returning to homescreen: {e}")


def launch_career_services_gui(root, auth):
    """Launch the Career Services Platform GUI"""
    try:
        CareerServicesGUI(root, auth)
    except Exception as e:
        messagebox.showerror(_t("common.error"), _t("careers.error.launch_gui", error=str(e)))
        print(f"❌ Career Services error: {traceback.format_exc()}")


__all__ = ['CareerServicesGUI', 'launch_career_services_gui']
