"""
Research & Grants Management GUI

Comprehensive Tkinter interface for managing research projects, grant applications,
publications, milestones, equipment tracking, and IRB/ethics reviews.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
from typing import Optional
import random
import string

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.infrastructure.shared_context import get_auth
from education_system.university_system.modules.shared.utils.activity_logger import log_activity
from education_system.university_system.modules.domain.research.services.research_grants_core import (
    ResearchProjectManager,
    GrantApplicationManager,
    PublicationManager,
    MilestoneManager,
    EquipmentManager,
    EthicsReviewManager
)

# Import i18n for language support
from education_system.university_system.modules.shared.utils.i18n import (
    get_text as _, init_i18n, get_current_language, get_current_language_name
)
from education_system.university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector
init_i18n()


class ResearchGrantsGUI:
    """Research & Grants Management GUI Application"""

    def __init__(self, root, auth):
        """Initialize the Research & Grants GUI"""
        self.root = root
        self.auth = auth

        if not self.auth or not hasattr(self.auth, 'current_user') or not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("research_grants.errors.login_required"))
            return

        self.window = tk.Toplevel(root)
        self.window.title(_("research_grants.title"))
        self.window.geometry("1200x800")
        self.window.minsize(1000, 600)

        # Initialize database tables
        self._init_database()

        # Setup UI
        self._create_widgets()

        # Log activity
        log_activity('Accessed research_grants', user=self.auth.current_user.get('username') if self.auth.current_user else None)
        print("✅ Research & Grants Management GUI opened successfully")

    def _init_database(self):
        """Initialize database tables if they don't exist"""
        try:
            from education_system.university_system.infrastructure.database.schemas.research_integration_schemas import init_research_grants_system_db
            init_research_grants_system_db()
        except ImportError as e:
            print(f"⚠️  Warning: Could not import database schemas: {e}")
        except Exception as e:
            print(f"⚠️  Warning: Database initialization error: {e}")
            messagebox.showwarning(_("common.warning"), _("research_grants.errors.db_init_issue").format(error=e))

    def _create_widgets(self):
        """Create all GUI widgets"""
        # Main container
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(
            header_frame,
            text=_("research_grants.header_title"),
            font=('Arial', 18, 'bold')
        ).pack(side=tk.LEFT)

        # Language change button
        ttk.Button(
            header_frame,
            text=_("research_grants.buttons.change_language").format(lang=get_current_language_name()),
            command=self._on_language_change
        ).pack(side=tk.RIGHT, padx=5)

        user_label = ttk.Label(
            header_frame,
            text=_("research_grants.labels.user").format(username=self.auth.current_user.get('username', 'Unknown')),
            font=('Arial', 10)
        )
        user_label.pack(side=tk.RIGHT, padx=10)

        # Notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Create tabs
        self._create_projects_tab()
        self._create_grants_tab()
        self._create_publications_tab()
        self._create_milestones_tab()
        self._create_equipment_tab()
        self._create_irb_tab()

        # Close button
        ttk.Button(
            main_frame,
            text=_("common.close"),
            command=self.window.destroy
        ).pack(pady=(10, 0))

    def _create_projects_tab(self):
        """Create Research Projects tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_("research_grants.tabs.research_projects"))

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text=_("research_grants.buttons.create_project"), command=self._create_project).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("research_grants.buttons.add_team_member"), command=self._add_team_member).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("common.refresh"), command=self._load_projects).pack(side=tk.LEFT, padx=5)

        # Projects list
        list_frame = ttk.LabelFrame(tab, text=_("research_grants.frames.active_projects"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Title', 'PI', 'Department', 'Type', 'Start Date', 'Budget', 'Status')
        column_headers = {
            'ID': _("research_grants.columns.id"),
            'Title': _("research_grants.columns.title"),
            'PI': _("research_grants.columns.pi"),
            'Department': _("research_grants.columns.department"),
            'Type': _("research_grants.columns.type"),
            'Start Date': _("research_grants.columns.start_date"),
            'Budget': _("research_grants.columns.budget"),
            'Status': _("research_grants.columns.status")
        }
        self.projects_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.projects_tree.heading('#0', text='')
        self.projects_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.projects_tree.heading(col, text=column_headers.get(col, col))
            if col == 'ID':
                self.projects_tree.column(col, width=50)
            elif col in ['Type', 'Budget', 'Status']:
                self.projects_tree.column(col, width=100)
            elif col == 'Title':
                self.projects_tree.column(col, width=250)
            else:
                self.projects_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.projects_tree.yview)
        self.projects_tree.configure(yscrollcommand=scrollbar.set)

        self.projects_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_projects()

    def _create_grants_tab(self):
        """Create Grant Applications tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_("research_grants.tabs.grant_applications"))

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text=_("research_grants.buttons.submit_application"), command=self._submit_grant).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("research_grants.buttons.update_decision"), command=self._update_grant_decision).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("common.refresh"), command=self._load_grants).pack(side=tk.LEFT, padx=5)

        # Grants list
        list_frame = ttk.LabelFrame(tab, text=_("research_grants.frames.grant_applications"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Grant Name', 'Agency', 'PI', 'Requested', 'Awarded', 'Status', 'Deadline')
        column_headers = {
            'ID': _("research_grants.columns.id"),
            'Grant Name': _("research_grants.columns.grant_name"),
            'Agency': _("research_grants.columns.agency"),
            'PI': _("research_grants.columns.pi"),
            'Requested': _("research_grants.columns.requested"),
            'Awarded': _("research_grants.columns.awarded"),
            'Status': _("research_grants.columns.status"),
            'Deadline': _("research_grants.columns.deadline")
        }
        self.grants_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.grants_tree.heading('#0', text='')
        self.grants_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.grants_tree.heading(col, text=column_headers.get(col, col))
            if col == 'ID':
                self.grants_tree.column(col, width=50)
            elif col in ['Requested', 'Awarded', 'Status']:
                self.grants_tree.column(col, width=100)
            elif col == 'Grant Name':
                self.grants_tree.column(col, width=220)
            else:
                self.grants_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.grants_tree.yview)
        self.grants_tree.configure(yscrollcommand=scrollbar.set)

        self.grants_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_grants()

    def _create_publications_tab(self):
        """Create Publications tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_("research_grants.tabs.publications"))

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text=_("research_grants.buttons.add_publication"), command=self._add_publication).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("common.refresh"), command=self._load_publications).pack(side=tk.LEFT, padx=5)

        # Publications list
        list_frame = ttk.LabelFrame(tab, text=_("research_grants.frames.research_publications"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Title', 'Authors', 'Publication Type', 'Journal', 'Year', 'Citations')
        column_headers = {
            'ID': _("research_grants.columns.id"),
            'Title': _("research_grants.columns.title"),
            'Authors': _("research_grants.columns.authors"),
            'Publication Type': _("research_grants.columns.publication_type"),
            'Journal': _("research_grants.columns.journal"),
            'Year': _("research_grants.columns.year"),
            'Citations': _("research_grants.columns.citations")
        }
        self.publications_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.publications_tree.heading('#0', text='')
        self.publications_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.publications_tree.heading(col, text=column_headers.get(col, col))
            if col in ['ID', 'Year', 'Citations']:
                self.publications_tree.column(col, width=60)
            elif col == 'Title':
                self.publications_tree.column(col, width=300)
            else:
                self.publications_tree.column(col, width=150)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.publications_tree.yview)
        self.publications_tree.configure(yscrollcommand=scrollbar.set)

        self.publications_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_publications()

    def _create_milestones_tab(self):
        """Create Project Milestones tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_("research_grants.tabs.milestones"))

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text=_("research_grants.buttons.add_milestone"), command=self._add_milestone).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("research_grants.buttons.update_status"), command=self._update_milestone).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("common.refresh"), command=self._load_milestones).pack(side=tk.LEFT, padx=5)

        # Milestones list
        list_frame = ttk.LabelFrame(tab, text=_("research_grants.frames.project_milestones"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Project', 'Milestone', 'Due Date', 'Completed', 'Status')
        column_headers = {
            'ID': _("research_grants.columns.id"),
            'Project': _("research_grants.columns.project"),
            'Milestone': _("research_grants.columns.milestone"),
            'Due Date': _("research_grants.columns.due_date"),
            'Completed': _("research_grants.columns.completed"),
            'Status': _("research_grants.columns.status")
        }
        self.milestones_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.milestones_tree.heading('#0', text='')
        self.milestones_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.milestones_tree.heading(col, text=column_headers.get(col, col))
            if col == 'ID':
                self.milestones_tree.column(col, width=50)
            elif col in ['Due Date', 'Completed', 'Status']:
                self.milestones_tree.column(col, width=120)
            else:
                self.milestones_tree.column(col, width=200)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.milestones_tree.yview)
        self.milestones_tree.configure(yscrollcommand=scrollbar.set)

        self.milestones_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_milestones()

    def _create_equipment_tab(self):
        """Create Equipment Tracking tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_("research_grants.tabs.equipment"))

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text=_("research_grants.buttons.add_equipment"), command=self._add_equipment).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("common.refresh"), command=self._load_equipment).pack(side=tk.LEFT, padx=5)

        # Equipment list
        list_frame = ttk.LabelFrame(tab, text=_("research_grants.frames.research_equipment"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Equipment Name', 'Project', 'Purchase Date', 'Cost', 'Location', 'Status')
        column_headers = {
            'ID': _("research_grants.columns.id"),
            'Equipment Name': _("research_grants.columns.equipment_name"),
            'Project': _("research_grants.columns.project"),
            'Purchase Date': _("research_grants.columns.purchase_date"),
            'Cost': _("research_grants.columns.cost"),
            'Location': _("research_grants.columns.location"),
            'Status': _("research_grants.columns.status")
        }
        self.equipment_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.equipment_tree.heading('#0', text='')
        self.equipment_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.equipment_tree.heading(col, text=column_headers.get(col, col))
            if col == 'ID':
                self.equipment_tree.column(col, width=50)
            elif col in ['Cost', 'Status']:
                self.equipment_tree.column(col, width=100)
            elif col == 'Equipment Name':
                self.equipment_tree.column(col, width=220)
            else:
                self.equipment_tree.column(col, width=130)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.equipment_tree.yview)
        self.equipment_tree.configure(yscrollcommand=scrollbar.set)

        self.equipment_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_equipment()

    def _create_irb_tab(self):
        """Create IRB/Ethics Reviews tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_("research_grants.tabs.irb_ethics"))

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text=_("research_grants.buttons.submit_irb"), command=self._submit_irb).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("research_grants.buttons.update_decision"), command=self._update_irb_decision).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("common.refresh"), command=self._load_irb).pack(side=tk.LEFT, padx=5)

        # IRB list
        list_frame = ttk.LabelFrame(tab, text=_("research_grants.frames.irb_applications"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Project', 'Protocol Number', 'Submission Date', 'Review Type', 'Decision', 'Status')
        column_headers = {
            'ID': _("research_grants.columns.id"),
            'Project': _("research_grants.columns.project"),
            'Protocol Number': _("research_grants.columns.protocol_number"),
            'Submission Date': _("research_grants.columns.submission_date"),
            'Review Type': _("research_grants.columns.review_type"),
            'Decision': _("research_grants.columns.decision"),
            'Status': _("research_grants.columns.status")
        }
        self.irb_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.irb_tree.heading('#0', text='')
        self.irb_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.irb_tree.heading(col, text=column_headers.get(col, col))
            if col == 'ID':
                self.irb_tree.column(col, width=50)
            elif col in ['Review Type', 'Decision', 'Status']:
                self.irb_tree.column(col, width=110)
            else:
                self.irb_tree.column(col, width=150)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.irb_tree.yview)
        self.irb_tree.configure(yscrollcommand=scrollbar.set)

        self.irb_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_irb()

    # Load methods
    def _load_projects(self):
        """Load all research projects"""
        try:
            self.projects_tree.delete(*self.projects_tree.get_children())

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT project_id, project_title, principal_investigator_id,
                           department, project_type, start_date, total_budget, status
                    FROM research_projects
                    ORDER BY created_at DESC
                    LIMIT 100
                ''')

                for row in cursor.fetchall():
                    values = (
                        row['project_id'],
                        row['project_title'],
                        row['principal_investigator_id'],
                        row['department'],
                        row['project_type'],
                        row['start_date'],
                        f"${row['total_budget']:,.2f}" if row['total_budget'] else '$0.00',
                        row['status']
                    )
                    self.projects_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror(_("common.error"), _("research_grants.errors.load_projects_failed").format(error=e))

    def _load_grants(self):
        """Load all grant applications"""
        try:
            self.grants_tree.delete(*self.grants_tree.get_children())

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT application_id, grant_name, funding_agency,
                           principal_investigator_id, requested_amount, awarded_amount,
                           decision_status, application_deadline
                    FROM grant_applications
                    ORDER BY submission_date DESC
                    LIMIT 100
                ''')

                for row in cursor.fetchall():
                    values = (
                        row['application_id'],
                        row['grant_name'],
                        row['funding_agency'],
                        row['principal_investigator_id'],
                        f"${row['requested_amount']:,.2f}",
                        f"${row['awarded_amount']:,.2f}" if row['awarded_amount'] else _("common.na"),
                        row['decision_status'],
                        row['application_deadline']
                    )
                    self.grants_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror(_("common.error"), _("research_grants.errors.load_grants_failed").format(error=e))

    def _load_publications(self):
        """Load all publications"""
        try:
            self.publications_tree.delete(*self.publications_tree.get_children())

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT publication_id, title, authors, publication_type,
                           journal_name,
                           CASE
                               WHEN publication_date IS NOT NULL THEN substr(publication_date, 1, 4)
                               ELSE 'N/A'
                           END as publication_year,
                           citation_count
                    FROM research_publications
                    ORDER BY publication_date DESC
                    LIMIT 100
                ''')

                for row in cursor.fetchall():
                    values = (
                        row['publication_id'],
                        row['title'],
                        row['authors'] or _("common.na"),
                        row['publication_type'],
                        row['journal_name'] or _("common.na"),
                        row['publication_year'] or _("common.na"),
                        row['citation_count'] or 0
                    )
                    self.publications_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror(_("common.error"), _("research_grants.errors.load_publications_failed").format(error=e))

    def _load_milestones(self):
        """Load all project milestones"""
        try:
            self.milestones_tree.delete(*self.milestones_tree.get_children())

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT milestone_id, project_id, milestone_description,
                           target_date as due_date, completion_date, status
                    FROM research_milestones
                    ORDER BY target_date
                    LIMIT 100
                ''')

                for row in cursor.fetchall():
                    values = (
                        row['milestone_id'],
                        row['project_id'],
                        row['milestone_description'] or _("common.na"),
                        row['due_date'],
                        row['completion_date'] or _("research_grants.status.not_completed"),
                        row['status']
                    )
                    self.milestones_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror(_("common.error"), _("research_grants.errors.load_milestones_failed").format(error=e))

    def _load_equipment(self):
        """Load all equipment"""
        try:
            self.equipment_tree.delete(*self.equipment_tree.get_children())

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT equipment_id, equipment_name, assigned_project_id as project_id,
                           purchase_date, purchase_cost as cost, current_location as location, status
                    FROM research_equipment
                    ORDER BY purchase_date DESC
                    LIMIT 100
                ''')

                for row in cursor.fetchall():
                    values = (
                        row['equipment_id'],
                        row['equipment_name'],
                        row['project_id'] or _("common.na"),
                        row['purchase_date'],
                        f"${row['cost']:,.2f}" if row['cost'] else _("common.na"),
                        row['location'] or _("common.na"),
                        row['status']
                    )
                    self.equipment_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror(_("common.error"), _("research_grants.errors.load_equipment_failed").format(error=e))

    def _load_irb(self):
        """Load all IRB applications"""
        try:
            self.irb_tree.delete(*self.irb_tree.get_children())

            with get_connection() as conn:
                # Check if table exists first
                cursor = conn.execute('''
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='irb_applications'
                ''')

                if not cursor.fetchone():
                    # Table doesn't exist - show message
                    print("ℹ️  IRB applications table not yet created")
                    return

                cursor = conn.execute('''
                    SELECT application_id, project_id, protocol_number,
                           submission_date, review_type, decision, status
                    FROM irb_applications
                    ORDER BY submission_date DESC
                    LIMIT 100
                ''')

                for row in cursor.fetchall():
                    values = (
                        row['application_id'],
                        row['project_id'],
                        row['protocol_number'] or _("research_grants.status.pending"),
                        row['submission_date'],
                        row['review_type'],
                        row['decision'] or _("research_grants.status.under_review"),
                        row['status']
                    )
                    self.irb_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror(_("common.error"), _("research_grants.errors.load_irb_failed").format(error=e))

    # Action methods (simplified dialogs for space)
    def _generate_pi_id(self):
        """Generate a random Principal Investigator ID."""
        digits = ''.join(random.choices(string.digits, k=6))
        return f"PI-{digits}"

    def _load_departments_list(self):
        """Load departments from DB for dropdown."""
        departments = []
        try:
            conn = get_connection()
            cursor = conn.cursor()
            # Try departments table first
            cursor.execute("SELECT name FROM departments WHERE is_active = 1 ORDER BY name")
            departments = [row[0] for row in cursor.fetchall()]
            # If empty, try distinct departments from existing projects
            if not departments:
                cursor.execute("SELECT DISTINCT department FROM research_projects WHERE department IS NOT NULL ORDER BY department")
                departments = [row[0] for row in cursor.fetchall()]
            conn.close()
        except Exception:
            pass
        # Always include common university departments as fallback
        defaults = [
            'Computer Science', 'Engineering', 'Mathematics', 'Physics', 'Chemistry',
            'Biology', 'Medicine', 'Psychology', 'Business', 'Economics',
            'Law', 'Education', 'Arts & Humanities', 'Social Sciences',
            'Environmental Science', 'Nursing', 'Architecture', 'Music',
            'Philosophy', 'History', 'Languages', 'Pharmacy'
        ]
        for d in defaults:
            if d not in departments:
                departments.append(d)
        departments.sort()
        return departments

    def _create_project(self):
        """Create a new research project"""
        dialog = tk.Toplevel(self.window)
        dialog.title(_("research_grants.dialogs.create_project.title"))
        dialog.geometry("550x520")
        dialog.transient(self.window)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("research_grants.dialogs.create_project.header"), font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        row = 0

        # Project Title
        ttk.Label(form_frame, text=_("research_grants.fields.project_title")).grid(row=row, column=0, sticky=tk.W, pady=5)
        title_entry = ttk.Entry(form_frame, width=35)
        title_entry.grid(row=row, column=1, pady=5, padx=(10, 0))
        row += 1

        # PI ID — auto-generated
        ttk.Label(form_frame, text=_("research_grants.fields.pi_id")).grid(row=row, column=0, sticky=tk.W, pady=5)
        pi_frame = ttk.Frame(form_frame)
        pi_frame.grid(row=row, column=1, pady=5, padx=(10, 0), sticky=tk.W)
        pi_var = tk.StringVar(value=self._generate_pi_id())
        pi_entry = ttk.Entry(pi_frame, textvariable=pi_var, width=20)
        pi_entry.pack(side=tk.LEFT)
        ttk.Button(pi_frame, text="Generate",
                  command=lambda: pi_var.set(self._generate_pi_id())).pack(side=tk.LEFT, padx=5)
        row += 1

        # Department — dropdown
        ttk.Label(form_frame, text=_("research_grants.fields.department")).grid(row=row, column=0, sticky=tk.W, pady=5)
        departments = self._load_departments_list()
        dept_var = tk.StringVar()
        dept_combo = ttk.Combobox(form_frame, textvariable=dept_var, values=departments, width=33)
        dept_combo.grid(row=row, column=1, pady=5, padx=(10, 0))
        if departments:
            dept_combo.current(0)
        row += 1

        # Project Type — dropdown
        ttk.Label(form_frame, text=_("research_grants.fields.project_type")).grid(row=row, column=0, sticky=tk.W, pady=5)
        project_types = [
            'Basic Research', 'Applied Research', 'Clinical Trial',
            'Experimental Development', 'Action Research', 'Case Study',
            'Longitudinal Study', 'Cross-Sectional Study', 'Systematic Review',
            'Meta-Analysis', 'Collaborative Research', 'Interdisciplinary',
            'Industry Partnership', 'Community-Based', 'Other'
        ]
        type_var = tk.StringVar()
        type_combo = ttk.Combobox(form_frame, textvariable=type_var, values=project_types,
                                  state='readonly', width=33)
        type_combo.grid(row=row, column=1, pady=5, padx=(10, 0))
        type_combo.current(0)
        row += 1

        # Start Date
        ttk.Label(form_frame, text=_("research_grants.fields.start_date")).grid(row=row, column=0, sticky=tk.W, pady=5)
        start_entry = ttk.Entry(form_frame, width=35)
        start_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        start_entry.grid(row=row, column=1, pady=5, padx=(10, 0))
        row += 1

        # Budget
        ttk.Label(form_frame, text=_("research_grants.fields.budget")).grid(row=row, column=0, sticky=tk.W, pady=5)
        budget_entry = ttk.Entry(form_frame, width=35)
        budget_entry.grid(row=row, column=1, pady=5, padx=(10, 0))
        row += 1

        # Description
        ttk.Label(form_frame, text=_("research_grants.fields.description")).grid(row=row, column=0, sticky=tk.NW, pady=5)
        desc_text = scrolledtext.ScrolledText(form_frame, width=33, height=5)
        desc_text.grid(row=row, column=1, pady=5, padx=(10, 0))

        def create():
            try:
                project_id = ResearchProjectManager.create_project(
                    project_title=title_entry.get(),
                    principal_investigator_id=pi_var.get(),
                    department=dept_var.get(),
                    project_type=type_var.get(),
                    start_date=start_entry.get(),
                    description=desc_text.get('1.0', tk.END).strip(),
                    total_budget=float(budget_entry.get() or 0)
                )

                log_activity('create', 'research_project', project_id=project_id,
                            user_id=self.auth.current_user.get('username'))

                messagebox.showinfo(_("common.success"), _("research_grants.messages.project_created").format(id=project_id))
                self._load_projects()
                dialog.destroy()
            except Exception as e:
                messagebox.showerror(_("common.error"), _("research_grants.errors.create_project_failed").format(error=e))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(15, 0))
        ttk.Button(btn_frame, text=_("common.create"), command=create).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _load_staff_list(self):
        """Load staff/admin/instructor users from DB for dropdown."""
        staff = []
        staff_id_map = {}
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, username, first_name, last_name, role
                FROM users
                WHERE role IN ('staff', 'admin', 'instructor')
                ORDER BY last_name, first_name
            ''')
            for row in cursor.fetchall():
                uid, uname, first, last, role = row
                display = f"{uname} - {first} {last} ({role})"
                staff.append(display)
                staff_id_map[display] = str(uname)
            conn.close()
        except Exception:
            pass
        return staff, staff_id_map

    def _add_team_member(self):
        """Add team member to project"""
        selection = self.projects_tree.selection()
        if not selection:
            messagebox.showwarning(_("common.warning"), _("research_grants.errors.select_project"))
            return

        item = self.projects_tree.item(selection[0])
        project_id = item['values'][0]

        dialog = tk.Toplevel(self.window)
        dialog.title(_("research_grants.dialogs.add_team_member.title"))
        dialog.geometry("500x300")
        dialog.transient(self.window)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("research_grants.dialogs.add_team_member.header").format(project_id=project_id),
                 font=('Arial', 12, 'bold')).pack(pady=(0, 15))

        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.X)

        # Staff member dropdown
        ttk.Label(form_frame, text=_("research_grants.fields.staff_id")).grid(row=0, column=0, sticky=tk.W, pady=8)
        staff_list, staff_id_map = self._load_staff_list()
        staff_var = tk.StringVar()
        staff_combo = ttk.Combobox(form_frame, textvariable=staff_var, values=staff_list,
                                   state='readonly', width=38)
        staff_combo.grid(row=0, column=1, pady=8, padx=(10, 0))
        if staff_list:
            staff_combo.current(0)

        # Role dropdown
        ttk.Label(form_frame, text=_("research_grants.fields.role")).grid(row=1, column=0, sticky=tk.W, pady=8)
        team_roles = [
            'Principal Investigator', 'Co-Investigator', 'Research Associate',
            'Research Assistant', 'Post-Doctoral Researcher', 'PhD Student',
            'Lab Technician', 'Data Analyst', 'Project Manager',
            'Statistician', 'Clinical Coordinator', 'Consultant', 'Other'
        ]
        role_var = tk.StringVar()
        role_combo = ttk.Combobox(form_frame, textvariable=role_var, values=team_roles,
                                  state='readonly', width=38)
        role_combo.grid(row=1, column=1, pady=8, padx=(10, 0))
        role_combo.current(0)

        def add():
            selected_staff = staff_var.get()
            selected_role = role_var.get()
            if not selected_staff:
                messagebox.showwarning(_("common.warning"), "Please select a staff member.")
                return
            if not selected_role:
                messagebox.showwarning(_("common.warning"), "Please select a role.")
                return

            staff_id = staff_id_map.get(selected_staff, selected_staff)

            try:
                member_id = ResearchProjectManager.add_team_member(
                    project_id=project_id,
                    staff_id=staff_id,
                    role=selected_role
                )

                log_activity('create', 'team_member', member_id=member_id,
                            user_id=self.auth.current_user.get('username'))

                messagebox.showinfo(_("common.success"), _("research_grants.messages.team_member_added"))
                dialog.destroy()
            except Exception as e:
                messagebox.showerror(_("common.error"), _("research_grants.errors.add_member_failed").format(error=e))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text=_("common.add"), command=add).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _load_available_grants(self):
        """Load existing grant names for dropdown."""
        grants = []
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT application_id, grant_name, funding_agency
                FROM grant_applications
                ORDER BY grant_name
            ''')
            for row in cursor.fetchall():
                grants.append(f"#{row[0]} - {row[1]} ({row[2]})")
            conn.close()
        except Exception:
            pass
        return grants

    def _load_projects_list(self):
        """Load research projects for dropdown."""
        projects = []
        project_id_map = {}
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT project_id, project_title, department
                FROM research_projects
                WHERE status = 'active'
                ORDER BY project_title
            ''')
            for row in cursor.fetchall():
                display = f"#{row[0]} - {row[1]} ({row[2]})"
                projects.append(display)
                project_id_map[display] = row[0]
            conn.close()
        except Exception:
            pass
        return projects, project_id_map

    def _submit_grant(self):
        """Submit grant application"""
        dialog = tk.Toplevel(self.window)
        dialog.title(_("research_grants.dialogs.submit_grant.title"))
        dialog.geometry("620x680")
        dialog.transient(self.window)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("research_grants.dialogs.submit_grant.header"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        row = 0

        # Grant Name — dropdown of existing grants + free text for new
        ttk.Label(form_frame, text=_("research_grants.fields.grant_name")).grid(row=row, column=0, sticky=tk.W, pady=5)
        existing_grants = self._load_available_grants()
        grant_name_var = tk.StringVar()
        grant_name_combo = ttk.Combobox(form_frame, textvariable=grant_name_var, width=40)
        # Allow free text for new grant names, but show existing ones
        common_grants = [
            'UKRI Future Leaders Fellowship', 'EPSRC Standard Grant',
            'AHRC Research Grant', 'BBSRC Responsive Mode', 'MRC Programme Grant',
            'NERC Standard Grant', 'ESRC Research Grant', 'Innovate UK Smart Grant',
            'Wellcome Trust Investigator Award', 'Leverhulme Trust Research Grant',
            'Royal Society University Research Fellowship', 'EU Horizon Europe',
            'NIH R01 Research Grant', 'NSF Standard Grant',
        ]
        grant_name_combo['values'] = common_grants
        grant_name_combo.grid(row=row, column=1, pady=5, padx=(10, 0))
        row += 1

        # Funding Agency — dropdown
        ttk.Label(form_frame, text=_("research_grants.fields.funding_agency")).grid(row=row, column=0, sticky=tk.W, pady=5)
        funding_agencies = [
            'UKRI', 'EPSRC', 'AHRC', 'BBSRC', 'MRC', 'NERC', 'ESRC', 'STFC',
            'Innovate UK', 'Wellcome Trust', 'Leverhulme Trust', 'Royal Society',
            'British Academy', 'Nuffield Foundation', 'European Commission',
            'NIH', 'NSF', 'Gates Foundation', 'Cancer Research UK',
            'British Heart Foundation', 'Alzheimer\'s Research UK',
            'Industry Partner', 'Internal University Fund', 'Other'
        ]
        agency_var = tk.StringVar()
        agency_combo = ttk.Combobox(form_frame, textvariable=agency_var,
                                    values=funding_agencies, width=40)
        agency_combo.grid(row=row, column=1, pady=5, padx=(10, 0))
        row += 1

        # PI — dropdown of staff
        ttk.Label(form_frame, text=_("research_grants.fields.pi_id")).grid(row=row, column=0, sticky=tk.W, pady=5)
        staff_list, staff_id_map = self._load_staff_list()
        pi_var = tk.StringVar()
        pi_combo = ttk.Combobox(form_frame, textvariable=pi_var, values=staff_list,
                                state='readonly', width=40)
        pi_combo.grid(row=row, column=1, pady=5, padx=(10, 0))
        if staff_list:
            pi_combo.current(0)
        row += 1

        # Co-Investigators — dropdown of staff (multi-select via repeated add)
        ttk.Label(form_frame, text=_("research_grants.fields.co_investigators")).grid(row=row, column=0, sticky=tk.W, pady=5)
        co_inv_frame = ttk.Frame(form_frame)
        co_inv_frame.grid(row=row, column=1, pady=5, padx=(10, 0), sticky=tk.W)
        co_inv_var = tk.StringVar()
        co_inv_combo = ttk.Combobox(co_inv_frame, textvariable=co_inv_var,
                                     values=staff_list, state='readonly', width=30)
        co_inv_combo.pack(side=tk.LEFT)
        co_inv_list_var = tk.StringVar(value="")

        def add_co_inv():
            selected = co_inv_var.get()
            if selected:
                sid = staff_id_map.get(selected, selected)
                current = co_inv_list_var.get()
                if sid not in current:
                    co_inv_list_var.set(f"{current}, {sid}" if current else sid)

        ttk.Button(co_inv_frame, text="Add", command=add_co_inv, width=5).pack(side=tk.LEFT, padx=3)
        row += 1

        # Show selected co-investigators
        ttk.Label(form_frame, text="Selected:").grid(row=row, column=0, sticky=tk.W, pady=2)
        co_inv_display = ttk.Label(form_frame, textvariable=co_inv_list_var, wraplength=350,
                                   font=('Arial', 8))
        co_inv_display.grid(row=row, column=1, sticky=tk.W, padx=(10, 0), pady=2)
        row += 1

        # Requested Amount
        ttk.Label(form_frame, text=_("research_grants.fields.requested_amount")).grid(row=row, column=0, sticky=tk.W, pady=5)
        amount_entry = ttk.Entry(form_frame, width=42)
        amount_entry.grid(row=row, column=1, pady=5, padx=(10, 0))
        row += 1

        # Application Deadline
        ttk.Label(form_frame, text=_("research_grants.fields.application_deadline")).grid(row=row, column=0, sticky=tk.W, pady=5)
        deadline_entry = ttk.Entry(form_frame, width=42)
        deadline_entry.grid(row=row, column=1, pady=5, padx=(10, 0))
        row += 1

        # Project — dropdown of available projects
        ttk.Label(form_frame, text=_("research_grants.fields.project_id_optional")).grid(row=row, column=0, sticky=tk.W, pady=5)
        projects_list, project_id_map = self._load_projects_list()
        project_var = tk.StringVar()
        project_combo = ttk.Combobox(form_frame, textvariable=project_var,
                                     values=['(None)'] + projects_list,
                                     state='readonly', width=40)
        project_combo.grid(row=row, column=1, pady=5, padx=(10, 0))
        project_combo.current(0)
        row += 1

        # Application Documents
        ttk.Label(form_frame, text=_("research_grants.fields.application_documents")).grid(
            row=row, column=0, sticky=tk.NW, pady=5)
        docs_text = scrolledtext.ScrolledText(form_frame, width=38, height=4)
        docs_text.grid(row=row, column=1, pady=5, padx=(10, 0))

        def submit():
            try:
                grant_name = grant_name_var.get().strip()
                agency = agency_var.get().strip()
                pi_selected = pi_var.get()
                pi_id = staff_id_map.get(pi_selected, pi_selected)
                amount_str = amount_entry.get().strip()
                deadline = deadline_entry.get().strip()

                if not grant_name or not agency or not pi_id or not amount_str or not deadline:
                    messagebox.showerror(_("common.error"),
                                       _("research_grants.errors.required_fields"))
                    return

                # Parse project_id (optional)
                project_id = None
                selected_project = project_var.get()
                if selected_project and selected_project != '(None)':
                    project_id = project_id_map.get(selected_project)

                # Submit the grant application
                application_id = GrantApplicationManager.submit_application(
                    grant_name=grant_name,
                    funding_agency=agency,
                    principal_investigator_id=pi_id,
                    requested_amount=float(amount_str),
                    application_deadline=deadline,
                    project_id=project_id
                )

                # Update additional fields
                with transaction() as conn:
                    conn.execute('''
                        UPDATE grant_applications
                        SET co_investigators = ?, submission_date = ?,
                            application_documents = ?
                        WHERE application_id = ?
                    ''', (co_inv_list_var.get(),
                          datetime.now().date().isoformat(),
                          docs_text.get('1.0', tk.END).strip(),
                          application_id))

                log_activity('create', 'grant_application', application_id=application_id,
                           user_id=self.auth.current_user.get('username'))

                messagebox.showinfo(_("common.success"),
                                  _("research_grants.messages.grant_submitted").format(id=application_id))
                self._load_grants()
                dialog.destroy()
            except ValueError:
                messagebox.showerror(_("common.error"),
                                   _("research_grants.errors.invalid_amount"))
            except Exception as e:
                messagebox.showerror(_("common.error"),
                                   _("research_grants.errors.submit_grant_failed").format(error=e))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(10, 0))
        ttk.Button(btn_frame, text=_("common.submit"), command=submit).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _update_grant_decision(self):
        """Update grant decision"""
        selection = self.grants_tree.selection()
        if not selection:
            messagebox.showwarning(_("common.warning"), _("research_grants.errors.select_grant"))
            return

        item = self.grants_tree.item(selection[0])
        application_id = item['values'][0]
        grant_name = item['values'][1]

        dialog = tk.Toplevel(self.window)
        dialog.title(_("research_grants.dialogs.update_grant_decision.title"))
        dialog.geometry("500x450")
        dialog.transient(self.window)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("research_grants.dialogs.update_grant_decision.header").format(
            grant_name=grant_name), font=('Arial', 12, 'bold')).pack(pady=(0, 20))

        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        # Decision status
        ttk.Label(form_frame, text=_("research_grants.fields.decision_status")).grid(
            row=0, column=0, sticky=tk.W, pady=5)
        decision_var = tk.StringVar()
        decision_combo = ttk.Combobox(form_frame, textvariable=decision_var, width=37,
                                     values=['Approved', 'Rejected', 'Under Review', 'Pending'],
                                     state='readonly')
        decision_combo.current(0)
        decision_combo.grid(row=0, column=1, pady=5, padx=(10, 0))

        # Awarded amount
        ttk.Label(form_frame, text=_("research_grants.fields.awarded_amount")).grid(
            row=1, column=0, sticky=tk.W, pady=5)
        awarded_entry = ttk.Entry(form_frame, width=40)
        awarded_entry.grid(row=1, column=1, pady=5, padx=(10, 0))

        # Grant period start
        ttk.Label(form_frame, text=_("research_grants.fields.grant_period_start")).grid(
            row=2, column=0, sticky=tk.W, pady=5)
        start_entry = ttk.Entry(form_frame, width=40)
        start_entry.insert(0, datetime.now().date().isoformat())
        start_entry.grid(row=2, column=1, pady=5, padx=(10, 0))

        # Grant period end
        ttk.Label(form_frame, text=_("research_grants.fields.grant_period_end")).grid(
            row=3, column=0, sticky=tk.W, pady=5)
        end_entry = ttk.Entry(form_frame, width=40)
        end_entry.grid(row=3, column=1, pady=5, padx=(10, 0))

        # Comments
        ttk.Label(form_frame, text=_("research_grants.fields.comments")).grid(
            row=4, column=0, sticky=tk.NW, pady=5)
        comments_text = scrolledtext.ScrolledText(form_frame, width=37, height=6)
        comments_text.grid(row=4, column=1, pady=5, padx=(10, 0))

        def update():
            try:
                awarded_amount = 0
                if awarded_entry.get().strip():
                    try:
                        awarded_amount = float(awarded_entry.get())
                    except ValueError:
                        messagebox.showerror(_("common.error"),
                                           _("research_grants.errors.invalid_amount"))
                        return

                # Update the grant decision
                GrantApplicationManager.update_decision(
                    application_id=application_id,
                    decision_status=decision_var.get(),
                    awarded_amount=awarded_amount,
                    grant_period_start=start_entry.get(),
                    grant_period_end=end_entry.get()
                )

                log_activity('update', 'grant_application', application_id=application_id,
                           user_id=self.auth.current_user.get('username'),
                           details={'decision': decision_var.get()})

                messagebox.showinfo(_("common.success"),
                                  _("research_grants.messages.grant_decision_updated"))
                self._load_grants()
                dialog.destroy()
            except Exception as e:
                messagebox.showerror(_("common.error"),
                                   _("research_grants.errors.update_decision_failed").format(error=e))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))
        ttk.Button(btn_frame, text=_("common.update"), command=update).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _add_publication(self):
        """Add publication"""
        dialog = tk.Toplevel(self.window)
        dialog.title(_("research_grants.dialogs.add_publication.title"))
        dialog.geometry("650x700")
        dialog.transient(self.window)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("research_grants.dialogs.add_publication.header"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        entries = {}
        fields = [
            (_("research_grants.fields.publication_title"), "title"),
            (_("research_grants.fields.authors"), "authors"),
            (_("research_grants.fields.publication_type"), "pub_type"),
            (_("research_grants.fields.journal_name"), "journal"),
            (_("research_grants.fields.conference_name"), "conference"),
            (_("research_grants.fields.publication_date"), "pub_date"),
            (_("research_grants.fields.doi"), "doi"),
            (_("research_grants.fields.url"), "url"),
            (_("research_grants.fields.project_id_optional"), "project_id"),
        ]

        for i, (label, field) in enumerate(fields):
            ttk.Label(form_frame, text=label).grid(row=i, column=0, sticky=tk.W, pady=5)
            entry = ttk.Entry(form_frame, width=45)
            entry.grid(row=i, column=1, pady=5, padx=(10, 0))
            entries[field] = entry

        # Peer reviewed checkbox
        is_peer_reviewed = tk.BooleanVar()
        ttk.Checkbutton(form_frame, text=_("research_grants.fields.peer_reviewed"),
                       variable=is_peer_reviewed).grid(row=len(fields), column=1, sticky=tk.W, pady=5, padx=(10, 0))

        # Abstract field
        ttk.Label(form_frame, text=_("research_grants.fields.abstract")).grid(
            row=len(fields) + 1, column=0, sticky=tk.NW, pady=5)
        abstract_text = scrolledtext.ScrolledText(form_frame, width=42, height=5)
        abstract_text.grid(row=len(fields) + 1, column=1, pady=5, padx=(10, 0))

        # Keywords field
        ttk.Label(form_frame, text=_("research_grants.fields.keywords")).grid(
            row=len(fields) + 2, column=0, sticky=tk.W, pady=5)
        keywords_entry = ttk.Entry(form_frame, width=45)
        keywords_entry.grid(row=len(fields) + 2, column=1, pady=5, padx=(10, 0))

        def add():
            try:
                # Validate required fields
                if not entries['title'].get() or not entries['authors'].get() or \
                   not entries['pub_type'].get():
                    messagebox.showerror(_("common.error"),
                                       _("research_grants.errors.required_fields"))
                    return

                # Parse project_id (optional)
                project_id = None
                if entries['project_id'].get().strip():
                    try:
                        project_id = int(entries['project_id'].get().strip())
                    except ValueError:
                        messagebox.showerror(_("common.error"),
                                           _("research_grants.errors.invalid_project_id"))
                        return

                # Record the publication
                publication_id = PublicationManager.record_publication(
                    title=entries['title'].get(),
                    authors=entries['authors'].get(),
                    publication_type=entries['pub_type'].get(),
                    project_id=project_id,
                    journal_name=entries['journal'].get(),
                    publication_date=entries['pub_date'].get(),
                    doi=entries['doi'].get()
                )

                # Update additional fields
                with transaction() as conn:
                    conn.execute('''
                        UPDATE research_publications
                        SET conference_name = ?, url = ?, abstract = ?,
                            keywords = ?, is_peer_reviewed = ?
                        WHERE publication_id = ?
                    ''', (entries['conference'].get(),
                          entries['url'].get(),
                          abstract_text.get('1.0', tk.END).strip(),
                          keywords_entry.get(),
                          1 if is_peer_reviewed.get() else 0,
                          publication_id))

                log_activity('create', 'publication', publication_id=publication_id,
                           user_id=self.auth.current_user.get('username'))

                messagebox.showinfo(_("common.success"),
                                  _("research_grants.messages.publication_added").format(id=publication_id))
                self._load_publications()
                dialog.destroy()
            except Exception as e:
                messagebox.showerror(_("common.error"),
                                   _("research_grants.errors.add_publication_failed").format(error=e))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))
        ttk.Button(btn_frame, text=_("common.add"), command=add).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _add_milestone(self):
        """Add project milestone"""
        dialog = tk.Toplevel(self.window)
        dialog.title(_("research_grants.dialogs.add_milestone.title"))
        dialog.geometry("550x450")
        dialog.transient(self.window)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("research_grants.dialogs.add_milestone.header"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        entries = {}
        fields = [
            (_("research_grants.fields.project_id"), "project_id"),
            (_("research_grants.fields.milestone_name"), "milestone_name"),
            (_("research_grants.fields.target_date"), "target_date"),
        ]

        for i, (label, field) in enumerate(fields):
            ttk.Label(form_frame, text=label).grid(row=i, column=0, sticky=tk.W, pady=5)
            entry = ttk.Entry(form_frame, width=40)
            entry.grid(row=i, column=1, pady=5, padx=(10, 0))
            entries[field] = entry

        # Description field
        ttk.Label(form_frame, text=_("research_grants.fields.description")).grid(
            row=len(fields), column=0, sticky=tk.NW, pady=5)
        desc_text = scrolledtext.ScrolledText(form_frame, width=37, height=6)
        desc_text.grid(row=len(fields), column=1, pady=5, padx=(10, 0))

        # Deliverables field
        ttk.Label(form_frame, text=_("research_grants.fields.deliverables")).grid(
            row=len(fields) + 1, column=0, sticky=tk.NW, pady=5)
        deliverables_text = scrolledtext.ScrolledText(form_frame, width=37, height=5)
        deliverables_text.grid(row=len(fields) + 1, column=1, pady=5, padx=(10, 0))

        def add():
            try:
                # Validate required fields
                if not entries['project_id'].get() or not entries['milestone_name'].get() or \
                   not entries['target_date'].get():
                    messagebox.showerror(_("common.error"),
                                       _("research_grants.errors.required_fields"))
                    return

                # Parse project_id
                try:
                    project_id = int(entries['project_id'].get())
                except ValueError:
                    messagebox.showerror(_("common.error"),
                                       _("research_grants.errors.invalid_project_id"))
                    return

                # Create the milestone
                milestone_id = MilestoneManager.create_milestone(
                    project_id=project_id,
                    milestone_name=entries['milestone_name'].get(),
                    target_date=entries['target_date'].get(),
                    description=desc_text.get('1.0', tk.END).strip()
                )

                # Update deliverables if provided
                if deliverables_text.get('1.0', tk.END).strip():
                    with transaction() as conn:
                        conn.execute('''
                            UPDATE research_milestones
                            SET deliverables = ?
                            WHERE milestone_id = ?
                        ''', (deliverables_text.get('1.0', tk.END).strip(), milestone_id))

                log_activity('create', 'milestone', milestone_id=milestone_id,
                           user_id=self.auth.current_user.get('username'))

                messagebox.showinfo(_("common.success"),
                                  _("research_grants.messages.milestone_added").format(id=milestone_id))
                self._load_milestones()
                dialog.destroy()
            except Exception as e:
                messagebox.showerror(_("common.error"),
                                   _("research_grants.errors.add_milestone_failed").format(error=e))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))
        ttk.Button(btn_frame, text=_("common.add"), command=add).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _update_milestone(self):
        """Update milestone status"""
        selection = self.milestones_tree.selection()
        if not selection:
            messagebox.showwarning(_("common.warning"), _("research_grants.errors.select_milestone"))
            return

        item = self.milestones_tree.item(selection[0])
        milestone_id = item['values'][0]
        milestone_name = item['values'][2]

        dialog = tk.Toplevel(self.window)
        dialog.title(_("research_grants.dialogs.update_milestone.title"))
        dialog.geometry("500x350")
        dialog.transient(self.window)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("research_grants.dialogs.update_milestone.header").format(
            milestone_name=milestone_name), font=('Arial', 12, 'bold')).pack(pady=(0, 20))

        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        # Status dropdown
        ttk.Label(form_frame, text=_("research_grants.fields.status")).grid(
            row=0, column=0, sticky=tk.W, pady=5)
        status_var = tk.StringVar()
        status_combo = ttk.Combobox(form_frame, textvariable=status_var, width=37,
                                    values=['Pending', 'In Progress', 'Completed', 'Delayed', 'Cancelled'],
                                    state='readonly')
        status_combo.current(0)
        status_combo.grid(row=0, column=1, pady=5, padx=(10, 0))

        # Completion date
        ttk.Label(form_frame, text=_("research_grants.fields.completion_date")).grid(
            row=1, column=0, sticky=tk.W, pady=5)
        completion_entry = ttk.Entry(form_frame, width=40)
        completion_entry.grid(row=1, column=1, pady=5, padx=(10, 0))

        # Notes field
        ttk.Label(form_frame, text=_("research_grants.fields.notes")).grid(
            row=2, column=0, sticky=tk.NW, pady=5)
        notes_text = scrolledtext.ScrolledText(form_frame, width=37, height=8)
        notes_text.grid(row=2, column=1, pady=5, padx=(10, 0))

        def update():
            try:
                # Update the milestone
                with transaction() as conn:
                    if status_var.get() == 'Completed' and completion_entry.get().strip():
                        conn.execute('''
                            UPDATE research_milestones
                            SET status = ?, completion_date = ?
                            WHERE milestone_id = ?
                        ''', (status_var.get(), completion_entry.get(), milestone_id))
                    else:
                        conn.execute('''
                            UPDATE research_milestones
                            SET status = ?
                            WHERE milestone_id = ?
                        ''', (status_var.get(), milestone_id))

                log_activity('update', 'milestone', milestone_id=milestone_id,
                           user_id=self.auth.current_user.get('username'),
                           details={'status': status_var.get()})

                messagebox.showinfo(_("common.success"),
                                  _("research_grants.messages.milestone_updated"))
                self._load_milestones()
                dialog.destroy()
            except Exception as e:
                messagebox.showerror(_("common.error"),
                                   _("research_grants.errors.update_milestone_failed").format(error=e))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))
        ttk.Button(btn_frame, text=_("common.update"), command=update).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _add_equipment(self):
        """Add equipment"""
        dialog = tk.Toplevel(self.window)
        dialog.title(_("research_grants.dialogs.add_equipment.title"))
        dialog.geometry("600x600")
        dialog.transient(self.window)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("research_grants.dialogs.add_equipment.header"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        entries = {}
        fields = [
            (_("research_grants.fields.equipment_name"), "equipment_name"),
            (_("research_grants.fields.equipment_type"), "equipment_type"),
            (_("research_grants.fields.model_number"), "model_number"),
            (_("research_grants.fields.serial_number"), "serial_number"),
            (_("research_grants.fields.purchase_date"), "purchase_date"),
            (_("research_grants.fields.purchase_cost"), "purchase_cost"),
            (_("research_grants.fields.current_location"), "location"),
            (_("research_grants.fields.assigned_project_id"), "project_id"),
        ]

        for i, (label, field) in enumerate(fields):
            ttk.Label(form_frame, text=label).grid(row=i, column=0, sticky=tk.W, pady=5)
            entry = ttk.Entry(form_frame, width=42)
            entry.grid(row=i, column=1, pady=5, padx=(10, 0))
            entries[field] = entry

        # Status dropdown
        ttk.Label(form_frame, text=_("research_grants.fields.status")).grid(
            row=len(fields), column=0, sticky=tk.W, pady=5)
        status_var = tk.StringVar(value='Available')
        status_combo = ttk.Combobox(form_frame, textvariable=status_var, width=40,
                                    values=['Available', 'In Use', 'Under Maintenance', 'Retired'],
                                    state='readonly')
        status_combo.grid(row=len(fields), column=1, pady=5, padx=(10, 0))

        # Maintenance schedule field
        ttk.Label(form_frame, text=_("research_grants.fields.maintenance_schedule")).grid(
            row=len(fields) + 1, column=0, sticky=tk.NW, pady=5)
        maintenance_text = scrolledtext.ScrolledText(form_frame, width=39, height=5)
        maintenance_text.grid(row=len(fields) + 1, column=1, pady=5, padx=(10, 0))

        def add():
            try:
                # Validate required fields
                if not entries['equipment_name'].get() or not entries['equipment_type'].get():
                    messagebox.showerror(_("common.error"),
                                       _("research_grants.errors.required_fields"))
                    return

                # Parse purchase cost
                purchase_cost = 0
                if entries['purchase_cost'].get().strip():
                    try:
                        purchase_cost = float(entries['purchase_cost'].get())
                    except ValueError:
                        messagebox.showerror(_("common.error"),
                                           _("research_grants.errors.invalid_cost"))
                        return

                # Parse project_id (optional)
                assigned_project_id = None
                if entries['project_id'].get().strip():
                    try:
                        assigned_project_id = int(entries['project_id'].get().strip())
                    except ValueError:
                        messagebox.showerror(_("common.error"),
                                           _("research_grants.errors.invalid_project_id"))
                        return

                # Register the equipment
                equipment_id = EquipmentManager.register_equipment(
                    equipment_name=entries['equipment_name'].get(),
                    equipment_type=entries['equipment_type'].get(),
                    serial_number=entries['serial_number'].get(),
                    purchase_cost=purchase_cost
                )

                # Update additional fields
                with transaction() as conn:
                    conn.execute('''
                        UPDATE research_equipment
                        SET model_number = ?, purchase_date = ?, current_location = ?,
                            assigned_project_id = ?, status = ?, maintenance_schedule = ?
                        WHERE equipment_id = ?
                    ''', (entries['model_number'].get(),
                          entries['purchase_date'].get(),
                          entries['location'].get(),
                          assigned_project_id,
                          status_var.get(),
                          maintenance_text.get('1.0', tk.END).strip(),
                          equipment_id))

                log_activity('create', 'equipment', equipment_id=equipment_id,
                           user_id=self.auth.current_user.get('username'))

                messagebox.showinfo(_("common.success"),
                                  _("research_grants.messages.equipment_added").format(id=equipment_id))
                self._load_equipment()
                dialog.destroy()
            except Exception as e:
                messagebox.showerror(_("common.error"),
                                   _("research_grants.errors.add_equipment_failed").format(error=e))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))
        ttk.Button(btn_frame, text=_("common.add"), command=add).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _submit_irb(self):
        """Submit IRB application"""
        dialog = tk.Toplevel(self.window)
        dialog.title(_("research_grants.dialogs.submit_irb.title"))
        dialog.geometry("600x600")
        dialog.transient(self.window)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("research_grants.dialogs.submit_irb.header"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        entries = {}
        fields = [
            (_("research_grants.fields.project_id"), "project_id"),
            (_("research_grants.fields.protocol_number"), "protocol_number"),
            (_("research_grants.fields.submission_date"), "submission_date"),
        ]

        for i, (label, field) in enumerate(fields):
            ttk.Label(form_frame, text=label).grid(row=i, column=0, sticky=tk.W, pady=5)
            entry = ttk.Entry(form_frame, width=42)
            if field == 'submission_date':
                entry.insert(0, datetime.now().date().isoformat())
            entry.grid(row=i, column=1, pady=5, padx=(10, 0))
            entries[field] = entry

        # Review type dropdown
        ttk.Label(form_frame, text=_("research_grants.fields.review_type")).grid(
            row=len(fields), column=0, sticky=tk.W, pady=5)
        review_type_var = tk.StringVar()
        review_type_combo = ttk.Combobox(form_frame, textvariable=review_type_var, width=40,
                                         values=['Expedited', 'Full Board', 'Exempt', 'Continuation'],
                                         state='readonly')
        review_type_combo.current(0)
        review_type_combo.grid(row=len(fields), column=1, pady=5, padx=(10, 0))

        # Study description
        ttk.Label(form_frame, text=_("research_grants.fields.study_description")).grid(
            row=len(fields) + 1, column=0, sticky=tk.NW, pady=5)
        study_desc_text = scrolledtext.ScrolledText(form_frame, width=39, height=6)
        study_desc_text.grid(row=len(fields) + 1, column=1, pady=5, padx=(10, 0))

        # Risk assessment
        ttk.Label(form_frame, text=_("research_grants.fields.risk_assessment")).grid(
            row=len(fields) + 2, column=0, sticky=tk.NW, pady=5)
        risk_text = scrolledtext.ScrolledText(form_frame, width=39, height=5)
        risk_text.grid(row=len(fields) + 2, column=1, pady=5, padx=(10, 0))

        def submit():
            try:
                # Validate required fields
                if not entries['project_id'].get() or not entries['submission_date'].get():
                    messagebox.showerror(_("common.error"),
                                       _("research_grants.errors.required_fields"))
                    return

                # Parse project_id
                try:
                    project_id = int(entries['project_id'].get())
                except ValueError:
                    messagebox.showerror(_("common.error"),
                                       _("research_grants.errors.invalid_project_id"))
                    return

                # Create irb_applications table if it doesn't exist
                with transaction() as conn:
                    conn.execute('''
                        CREATE TABLE IF NOT EXISTS irb_applications (
                            application_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            project_id INTEGER NOT NULL,
                            protocol_number TEXT,
                            submission_date TEXT NOT NULL,
                            review_type TEXT NOT NULL,
                            decision TEXT DEFAULT 'Pending',
                            decision_date TEXT,
                            status TEXT DEFAULT 'Submitted',
                            study_description TEXT,
                            risk_assessment TEXT,
                            reviewer_comments TEXT,
                            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (project_id) REFERENCES research_projects (project_id)
                        )
                    ''')

                    # Submit the IRB application
                    cursor = conn.execute('''
                        INSERT INTO irb_applications (
                            project_id, protocol_number, submission_date, review_type,
                            study_description, risk_assessment
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    ''', (project_id,
                          entries['protocol_number'].get(),
                          entries['submission_date'].get(),
                          review_type_var.get(),
                          study_desc_text.get('1.0', tk.END).strip(),
                          risk_text.get('1.0', tk.END).strip()))

                    application_id = cursor.lastrowid

                log_activity('create', 'irb_application', application_id=application_id,
                           user_id=self.auth.current_user.get('username'))

                messagebox.showinfo(_("common.success"),
                                  _("research_grants.messages.irb_submitted").format(id=application_id))
                self._load_irb()
                dialog.destroy()
            except Exception as e:
                messagebox.showerror(_("common.error"),
                                   _("research_grants.errors.submit_irb_failed").format(error=e))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))
        ttk.Button(btn_frame, text=_("common.submit"), command=submit).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _update_irb_decision(self):
        """Update IRB decision"""
        selection = self.irb_tree.selection()
        if not selection:
            messagebox.showwarning(_("common.warning"), _("research_grants.errors.select_irb"))
            return

        item = self.irb_tree.item(selection[0])
        application_id = item['values'][0]
        protocol_number = item['values'][2]

        dialog = tk.Toplevel(self.window)
        dialog.title(_("research_grants.dialogs.update_irb_decision.title"))
        dialog.geometry("550x450")
        dialog.transient(self.window)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("research_grants.dialogs.update_irb_decision.header").format(
            protocol=protocol_number), font=('Arial', 12, 'bold')).pack(pady=(0, 20))

        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        # Decision dropdown
        ttk.Label(form_frame, text=_("research_grants.fields.decision")).grid(
            row=0, column=0, sticky=tk.W, pady=5)
        decision_var = tk.StringVar()
        decision_combo = ttk.Combobox(form_frame, textvariable=decision_var, width=37,
                                     values=['Approved', 'Approved with Conditions', 'Deferred',
                                            'Disapproved', 'Pending'],
                                     state='readonly')
        decision_combo.current(0)
        decision_combo.grid(row=0, column=1, pady=5, padx=(10, 0))

        # Status dropdown
        ttk.Label(form_frame, text=_("research_grants.fields.status")).grid(
            row=1, column=0, sticky=tk.W, pady=5)
        status_var = tk.StringVar()
        status_combo = ttk.Combobox(form_frame, textvariable=status_var, width=37,
                                   values=['Submitted', 'Under Review', 'Approved', 'Closed'],
                                   state='readonly')
        status_combo.current(1)
        status_combo.grid(row=1, column=1, pady=5, padx=(10, 0))

        # Decision date
        ttk.Label(form_frame, text=_("research_grants.fields.decision_date")).grid(
            row=2, column=0, sticky=tk.W, pady=5)
        date_entry = ttk.Entry(form_frame, width=40)
        date_entry.insert(0, datetime.now().date().isoformat())
        date_entry.grid(row=2, column=1, pady=5, padx=(10, 0))

        # Reviewer comments
        ttk.Label(form_frame, text=_("research_grants.fields.reviewer_comments")).grid(
            row=3, column=0, sticky=tk.NW, pady=5)
        comments_text = scrolledtext.ScrolledText(form_frame, width=37, height=8)
        comments_text.grid(row=3, column=1, pady=5, padx=(10, 0))

        def update():
            try:
                # Update the IRB decision
                with transaction() as conn:
                    conn.execute('''
                        UPDATE irb_applications
                        SET decision = ?, status = ?, decision_date = ?,
                            reviewer_comments = ?
                        WHERE application_id = ?
                    ''', (decision_var.get(),
                          status_var.get(),
                          date_entry.get(),
                          comments_text.get('1.0', tk.END).strip(),
                          application_id))

                log_activity('update', 'irb_application', application_id=application_id,
                           user_id=self.auth.current_user.get('username'),
                           details={'decision': decision_var.get()})

                messagebox.showinfo(_("common.success"),
                                  _("research_grants.messages.irb_decision_updated"))
                self._load_irb()
                dialog.destroy()
            except Exception as e:
                messagebox.showerror(_("common.error"),
                                   _("research_grants.errors.update_irb_failed").format(error=e))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))
        ttk.Button(btn_frame, text=_("common.update"), command=update).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _on_language_change(self):
        """Handle language change request"""
        old_lang = get_current_language()
        show_gui_language_selector(self.window)
        new_lang = get_current_language()

        if old_lang != new_lang:
            messagebox.showinfo(
                _("research_grants.language.changed_title"),
                _("research_grants.language.restart_for_full_effect")
            )
            self._refresh_ui_language()

    def _refresh_ui_language(self):
        """Refresh all UI text elements with current language translations"""
        try:
            # Update window title
            self.window.title(_("research_grants.title"))

            # Note: For a full refresh, the window would need to be recreated
            # This is a simplified version that updates what's easily accessible

        except Exception as e:
            print(f"Error refreshing UI language: {e}")


# Launcher function
def launch_research_grants_gui(root, auth):
    """Launch the Research & Grants Management GUI"""
    try:
        ResearchGrantsGUI(root, auth)
    except Exception as e:
        messagebox.showerror(_("common.error"), _("research_grants.errors.launch_failed").format(error=e))
        print(f"❌ Research & Grants GUI error: {e}")


__all__ = ['ResearchGrantsGUI', 'launch_research_grants_gui']
