"""
Research & Grants Management GUI

Comprehensive Tkinter interface for managing research projects, grant applications,
publications, milestones, equipment tracking, and IRB/ethics reviews.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
from typing import Optional

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
    def _create_project(self):
        """Create a new research project"""
        # Simplified inline dialog
        dialog = tk.Toplevel(self.window)
        dialog.title(_("research_grants.dialogs.create_project.title"))
        dialog.geometry("500x500")
        dialog.transient(self.window)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("research_grants.dialogs.create_project.header"), font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        entries = {}
        fields = [
            (_("research_grants.fields.project_title"), "title"),
            (_("research_grants.fields.pi_id"), "pi"),
            (_("research_grants.fields.department"), "dept"),
            (_("research_grants.fields.project_type"), "type"),
            (_("research_grants.fields.start_date"), "start"),
            (_("research_grants.fields.budget"), "budget"),
        ]

        for i, (label, field) in enumerate(fields):
            ttk.Label(form_frame, text=label).grid(row=i, column=0, sticky=tk.W, pady=5)
            entry = ttk.Entry(form_frame, width=35)
            entry.grid(row=i, column=1, pady=5, padx=(10, 0))
            entries[field] = entry

        ttk.Label(form_frame, text=_("research_grants.fields.description")).grid(row=len(fields), column=0, sticky=tk.NW, pady=5)
        desc_text = scrolledtext.ScrolledText(form_frame, width=33, height=6)
        desc_text.grid(row=len(fields), column=1, pady=5, padx=(10, 0))

        def create():
            try:
                project_id = ResearchProjectManager.create_project(
                    project_title=entries['title'].get(),
                    principal_investigator_id=entries['pi'].get(),
                    department=entries['dept'].get(),
                    project_type=entries['type'].get(),
                    start_date=entries['start'].get(),
                    description=desc_text.get('1.0', tk.END).strip(),
                    total_budget=float(entries['budget'].get() or 0)
                )

                log_activity('create', 'research_project', project_id=project_id,
                            user_id=self.auth.current_user.get('username'))

                messagebox.showinfo(_("common.success"), _("research_grants.messages.project_created").format(id=project_id))
                self._load_projects()
                dialog.destroy()
            except Exception as e:
                messagebox.showerror(_("common.error"), _("research_grants.errors.create_project_failed").format(error=e))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))
        ttk.Button(btn_frame, text=_("common.create"), command=create).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _add_team_member(self):
        """Add team member to project"""
        selection = self.projects_tree.selection()
        if not selection:
            messagebox.showwarning(_("common.warning"), _("research_grants.errors.select_project"))
            return

        item = self.projects_tree.item(selection[0])
        project_id = item['values'][0]

        # Simple dialog
        dialog = tk.Toplevel(self.window)
        dialog.title(_("research_grants.dialogs.add_team_member.title"))
        dialog.geometry("400x250")
        dialog.transient(self.window)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("research_grants.dialogs.add_team_member.header").format(project_id=project_id),
                 font=('Arial', 12, 'bold')).pack(pady=(0, 20))

        ttk.Label(main_frame, text=_("research_grants.fields.staff_id")).pack(pady=5)
        staff_entry = ttk.Entry(main_frame, width=30)
        staff_entry.pack(pady=5)

        ttk.Label(main_frame, text=_("research_grants.fields.role")).pack(pady=5)
        role_entry = ttk.Entry(main_frame, width=30)
        role_entry.pack(pady=5)

        def add():
            try:
                member_id = ResearchProjectManager.add_team_member(
                    project_id=project_id,
                    staff_id=staff_entry.get(),
                    role=role_entry.get()
                )

                log_activity('create', 'team_member', member_id=member_id,
                            user_id=self.auth.current_user.get('username'))

                messagebox.showinfo(_("common.success"), _("research_grants.messages.team_member_added"))
                dialog.destroy()
            except Exception as e:
                messagebox.showerror(_("common.error"), _("research_grants.errors.add_member_failed").format(error=e))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text=_("common.add"), command=add).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _submit_grant(self):
        """Submit grant application"""
        dialog = tk.Toplevel(self.window)
        dialog.title(_("research_grants.dialogs.submit_grant.title"))
        dialog.geometry("600x650")
        dialog.transient(self.window)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_("research_grants.dialogs.submit_grant.header"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        entries = {}
        fields = [
            (_("research_grants.fields.grant_name"), "grant_name"),
            (_("research_grants.fields.funding_agency"), "agency"),
            (_("research_grants.fields.pi_id"), "pi_id"),
            (_("research_grants.fields.co_investigators"), "co_inv"),
            (_("research_grants.fields.requested_amount"), "amount"),
            (_("research_grants.fields.application_deadline"), "deadline"),
            (_("research_grants.fields.project_id_optional"), "project_id"),
        ]

        for i, (label, field) in enumerate(fields):
            ttk.Label(form_frame, text=label).grid(row=i, column=0, sticky=tk.W, pady=5)
            entry = ttk.Entry(form_frame, width=40)
            entry.grid(row=i, column=1, pady=5, padx=(10, 0))
            entries[field] = entry

        # Application documents field
        ttk.Label(form_frame, text=_("research_grants.fields.application_documents")).grid(
            row=len(fields), column=0, sticky=tk.NW, pady=5)
        docs_text = scrolledtext.ScrolledText(form_frame, width=37, height=5)
        docs_text.grid(row=len(fields), column=1, pady=5, padx=(10, 0))

        def submit():
            try:
                # Validate required fields
                if not entries['grant_name'].get() or not entries['agency'].get() or \
                   not entries['pi_id'].get() or not entries['amount'].get() or \
                   not entries['deadline'].get():
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

                # Submit the grant application
                application_id = GrantApplicationManager.submit_application(
                    grant_name=entries['grant_name'].get(),
                    funding_agency=entries['agency'].get(),
                    principal_investigator_id=entries['pi_id'].get(),
                    requested_amount=float(entries['amount'].get()),
                    application_deadline=entries['deadline'].get(),
                    project_id=project_id
                )

                # Update additional fields
                with transaction() as conn:
                    conn.execute('''
                        UPDATE grant_applications
                        SET co_investigators = ?, submission_date = ?,
                            application_documents = ?
                        WHERE application_id = ?
                    ''', (entries['co_inv'].get(),
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
        btn_frame.pack(pady=(20, 0))
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
