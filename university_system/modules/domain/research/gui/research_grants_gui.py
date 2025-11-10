"""
Research & Grants Management GUI

Comprehensive Tkinter interface for managing research projects, grant applications,
publications, milestones, equipment tracking, and IRB/ethics reviews.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
from typing import Optional

from university_system.infrastructure.database.db import get_connection, transaction
from university_system.infrastructure.shared_context import get_auth
from university_system.modules.shared.utils.activity_logger import log_activity
from university_system.modules.domain.research.services.research_grants_core import (
    ResearchProjectManager,
    GrantApplicationManager,
    PublicationManager,
    MilestoneManager,
    EquipmentManager,
    EthicsReviewManager
)


class ResearchGrantsGUI:
    """Research & Grants Management GUI Application"""

    def __init__(self, root, auth):
        """Initialize the Research & Grants GUI"""
        self.root = root
        self.auth = auth

        if not self.auth or not hasattr(self.auth, 'current_user') or not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to access Research & Grants.")
            return

        self.window = tk.Toplevel(root)
        self.window.title("Research & Grants Management")
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
            from university_system.infrastructure.database.schemas import init_research_grants_system_db
            init_research_grants_system_db()
        except ImportError as e:
            print(f"⚠️  Warning: Could not import database schemas: {e}")
        except Exception as e:
            print(f"⚠️  Warning: Database initialization error: {e}")
            messagebox.showwarning("Warning", f"Database initialization issue: {e}")

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
            text="Research & Grants Management",
            font=('Arial', 18, 'bold')
        ).pack(side=tk.LEFT)

        user_label = ttk.Label(
            header_frame,
            text=f"User: {self.auth.current_user.get('username', 'Unknown')}",
            font=('Arial', 10)
        )
        user_label.pack(side=tk.RIGHT)

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
            text="Close",
            command=self.window.destroy
        ).pack(pady=(10, 0))

    def _create_projects_tab(self):
        """Create Research Projects tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="Research Projects")

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text="Create Project", command=self._create_project).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Add Team Member", command=self._add_team_member).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self._load_projects).pack(side=tk.LEFT, padx=5)

        # Projects list
        list_frame = ttk.LabelFrame(tab, text="Active Research Projects", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Title', 'PI', 'Department', 'Type', 'Start Date', 'Budget', 'Status')
        self.projects_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.projects_tree.heading('#0', text='')
        self.projects_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.projects_tree.heading(col, text=col)
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
        self.notebook.add(tab, text="Grant Applications")

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text="Submit Application", command=self._submit_grant).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Update Decision", command=self._update_grant_decision).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self._load_grants).pack(side=tk.LEFT, padx=5)

        # Grants list
        list_frame = ttk.LabelFrame(tab, text="Grant Applications", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Grant Name', 'Agency', 'PI', 'Requested', 'Awarded', 'Status', 'Deadline')
        self.grants_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.grants_tree.heading('#0', text='')
        self.grants_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.grants_tree.heading(col, text=col)
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
        self.notebook.add(tab, text="Publications")

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text="Add Publication", command=self._add_publication).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self._load_publications).pack(side=tk.LEFT, padx=5)

        # Publications list
        list_frame = ttk.LabelFrame(tab, text="Research Publications", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Title', 'Authors', 'Publication Type', 'Journal', 'Year', 'Citations')
        self.publications_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.publications_tree.heading('#0', text='')
        self.publications_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.publications_tree.heading(col, text=col)
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
        self.notebook.add(tab, text="Milestones")

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text="Add Milestone", command=self._add_milestone).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Update Status", command=self._update_milestone).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self._load_milestones).pack(side=tk.LEFT, padx=5)

        # Milestones list
        list_frame = ttk.LabelFrame(tab, text="Project Milestones", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Project', 'Milestone', 'Due Date', 'Completed', 'Status')
        self.milestones_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.milestones_tree.heading('#0', text='')
        self.milestones_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.milestones_tree.heading(col, text=col)
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
        self.notebook.add(tab, text="Equipment")

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text="Add Equipment", command=self._add_equipment).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self._load_equipment).pack(side=tk.LEFT, padx=5)

        # Equipment list
        list_frame = ttk.LabelFrame(tab, text="Research Equipment", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Equipment Name', 'Project', 'Purchase Date', 'Cost', 'Location', 'Status')
        self.equipment_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.equipment_tree.heading('#0', text='')
        self.equipment_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.equipment_tree.heading(col, text=col)
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
        self.notebook.add(tab, text="IRB/Ethics")

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text="Submit IRB Application", command=self._submit_irb).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Update Decision", command=self._update_irb_decision).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self._load_irb).pack(side=tk.LEFT, padx=5)

        # IRB list
        list_frame = ttk.LabelFrame(tab, text="IRB/Ethics Applications", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Project', 'Protocol Number', 'Submission Date', 'Review Type', 'Decision', 'Status')
        self.irb_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.irb_tree.heading('#0', text='')
        self.irb_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.irb_tree.heading(col, text=col)
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
            messagebox.showerror("Error", f"Failed to load projects: {e}")

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
                        f"${row['awarded_amount']:,.2f}" if row['awarded_amount'] else 'N/A',
                        row['decision_status'],
                        row['application_deadline']
                    )
                    self.grants_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load grants: {e}")

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
                        row['authors'] or 'N/A',
                        row['publication_type'],
                        row['journal_name'] or 'N/A',
                        row['publication_year'] or 'N/A',
                        row['citation_count'] or 0
                    )
                    self.publications_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load publications: {e}")

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
                        row['milestone_description'] or 'N/A',
                        row['due_date'],
                        row['completion_date'] or 'Not completed',
                        row['status']
                    )
                    self.milestones_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load milestones: {e}")

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
                        row['project_id'] or 'N/A',
                        row['purchase_date'],
                        f"${row['cost']:,.2f}" if row['cost'] else 'N/A',
                        row['location'] or 'N/A',
                        row['status']
                    )
                    self.equipment_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load equipment: {e}")

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
                        row['protocol_number'] or 'Pending',
                        row['submission_date'],
                        row['review_type'],
                        row['decision'] or 'Under Review',
                        row['status']
                    )
                    self.irb_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load IRB applications: {e}")

    # Action methods (simplified dialogs for space)
    def _create_project(self):
        """Create a new research project"""
        # Simplified inline dialog
        dialog = tk.Toplevel(self.window)
        dialog.title("Create Research Project")
        dialog.geometry("500x500")
        dialog.transient(self.window)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Create Research Project", font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        entries = {}
        fields = [
            ("Project Title:", "title"),
            ("PI ID:", "pi"),
            ("Department:", "dept"),
            ("Project Type:", "type"),
            ("Start Date (YYYY-MM-DD):", "start"),
            ("Budget:", "budget"),
        ]

        for i, (label, field) in enumerate(fields):
            ttk.Label(form_frame, text=label).grid(row=i, column=0, sticky=tk.W, pady=5)
            entry = ttk.Entry(form_frame, width=35)
            entry.grid(row=i, column=1, pady=5, padx=(10, 0))
            entries[field] = entry

        ttk.Label(form_frame, text="Description:").grid(row=len(fields), column=0, sticky=tk.NW, pady=5)
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

                messagebox.showinfo("Success", f"Project created (ID: {project_id})")
                self._load_projects()
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create project: {e}")

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))
        ttk.Button(btn_frame, text="Create", command=create).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _add_team_member(self):
        """Add team member to project"""
        selection = self.projects_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a project")
            return

        item = self.projects_tree.item(selection[0])
        project_id = item['values'][0]

        # Simple dialog
        dialog = tk.Toplevel(self.window)
        dialog.title("Add Team Member")
        dialog.geometry("400x250")
        dialog.transient(self.window)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=f"Add Team Member - Project {project_id}",
                 font=('Arial', 12, 'bold')).pack(pady=(0, 20))

        ttk.Label(main_frame, text="Staff ID:").pack(pady=5)
        staff_entry = ttk.Entry(main_frame, width=30)
        staff_entry.pack(pady=5)

        ttk.Label(main_frame, text="Role:").pack(pady=5)
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

                messagebox.showinfo("Success", "Team member added")
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add member: {e}")

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text="Add", command=add).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _submit_grant(self):
        """Submit grant application"""
        # Simplified implementation
        messagebox.showinfo("Info", "Grant submission dialog - implement as needed")

    def _update_grant_decision(self):
        """Update grant decision"""
        messagebox.showinfo("Info", "Grant decision update dialog - implement as needed")

    def _add_publication(self):
        """Add publication"""
        messagebox.showinfo("Info", "Add publication dialog - implement as needed")

    def _add_milestone(self):
        """Add project milestone"""
        messagebox.showinfo("Info", "Add milestone dialog - implement as needed")

    def _update_milestone(self):
        """Update milestone status"""
        messagebox.showinfo("Info", "Update milestone dialog - implement as needed")

    def _add_equipment(self):
        """Add equipment"""
        messagebox.showinfo("Info", "Add equipment dialog - implement as needed")

    def _submit_irb(self):
        """Submit IRB application"""
        messagebox.showinfo("Info", "IRB submission dialog - implement as needed")

    def _update_irb_decision(self):
        """Update IRB decision"""
        messagebox.showinfo("Info", "IRB decision update dialog - implement as needed")


# Launcher function
def launch_research_grants_gui(root, auth):
    """Launch the Research & Grants Management GUI"""
    try:
        ResearchGrantsGUI(root, auth)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to launch Research & Grants GUI: {e}")
        print(f"❌ Research & Grants GUI error: {e}")


__all__ = ['ResearchGrantsGUI', 'launch_research_grants_gui']
